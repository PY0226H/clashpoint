const fs = require('fs');
const { performance } = require('perf_hooks');

const env = Object.fromEntries(
  fs.readFileSync('/tmp/aicomm_loadtest_ext/context.env', 'utf8').trim().split('\n').map((line) => {
    const i = line.indexOf('=');
    return [line.slice(0, i), line.slice(i + 1)];
  })
);

const BASE = env.BASE;
const CHAT_ID = env.CHAT_ID;
const TOKEN = env.TOKEN;
const NOTIFY_TOKEN = env.NOTIFY_TOKEN;

const WS_CLIENTS = Number(process.argv[2] || 20);
const SEND_COUNT = Number(process.argv[3] || 200);
const OPEN_TIMEOUT_MS = Number(process.argv[4] || 15000);
const DRAIN_TIMEOUT_MS = Number(process.argv[5] || 20000);

const runId = `WSEXT-${Date.now()}-${WS_CLIENTS}-${SEND_COUNT}`;
const wsUrl = `ws://127.0.0.1:6687/ws?token=${encodeURIComponent(NOTIFY_TOKEN)}`;

const sendAt = new Map();
const firstRecvAt = new Map();
const pendingRecvAt = new Map();
let newMessageEvents = 0;
let parseErrors = 0;
let openOk = 0;
let openFail = 0;

function percentile(arr, p) {
  if (!arr.length) return null;
  const sorted = [...arr].sort((a, b) => a - b);
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, Math.min(idx, sorted.length - 1))];
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function openClients() {
  const sockets = [];
  const opens = [];
  for (let i = 0; i < WS_CLIENTS; i++) {
    const ws = new WebSocket(wsUrl);
    sockets.push(ws);
    opens.push(new Promise((resolve) => {
      const t = setTimeout(() => {
        openFail += 1;
        try { ws.close(); } catch (_) {}
        resolve();
      }, OPEN_TIMEOUT_MS);

      ws.onopen = () => {
        clearTimeout(t);
        openOk += 1;
        resolve();
      };
      ws.onerror = () => {
        clearTimeout(t);
        openFail += 1;
        resolve();
      };
      ws.onmessage = (evt) => {
        try {
          const obj = JSON.parse(evt.data);
          if (obj?.event === 'NewMessage' && obj?.content && obj.content.startsWith(runId)) {
            newMessageEvents += 1;
            const msgId = String(obj.id);
            const now = performance.now();
            if (!firstRecvAt.has(msgId)) {
              if (sendAt.has(msgId)) firstRecvAt.set(msgId, now);
              else if (!pendingRecvAt.has(msgId)) pendingRecvAt.set(msgId, now);
            }
          }
        } catch (_) {
          parseErrors += 1;
        }
      };
    }));
  }
  await Promise.all(opens);
  return sockets;
}

async function sendMessages() {
  let sendFailed = 0;
  for (let i = 0; i < SEND_COUNT; i++) {
    const content = `${runId}-msg-${i}`;
    const t0 = performance.now();
    try {
      const res = await fetch(`${BASE}/api/chats/${CHAT_ID}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${TOKEN}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, files: [] }),
      });
      if (!res.ok) {
        sendFailed += 1;
        continue;
      }
      const json = await res.json();
      const msgId = String(json.id);
      sendAt.set(msgId, t0);
      if (!firstRecvAt.has(msgId) && pendingRecvAt.has(msgId)) {
        firstRecvAt.set(msgId, pendingRecvAt.get(msgId));
        pendingRecvAt.delete(msgId);
      }
    } catch (_) {
      sendFailed += 1;
    }
  }
  return sendFailed;
}

(async () => {
  const tStart = Date.now();
  const sockets = await openClients();
  const sendFailed = await sendMessages();

  const drainStart = Date.now();
  while (Date.now() - drainStart < DRAIN_TIMEOUT_MS) {
    if (firstRecvAt.size >= sendAt.size) break;
    await sleep(100);
  }

  for (const ws of sockets) {
    try { ws.close(); } catch (_) {}
  }

  const latencies = [];
  for (const [id, t0] of sendAt.entries()) {
    const t1 = firstRecvAt.get(id);
    if (typeof t1 === 'number') latencies.push(t1 - t0);
  }

  const fanoutExpected = openOk * sendAt.size;
  const summary = {
    runId,
    wsClientsTarget: WS_CLIENTS,
    wsOpenOk: openOk,
    wsOpenFail: openFail,
    sendCountTarget: SEND_COUNT,
    sendOk: sendAt.size,
    sendFailed,
    firstDeliveryReceived: latencies.length,
    firstDeliverySuccessRate: sendAt.size ? latencies.length / sendAt.size : 0,
    wsFanoutEventsReceived: newMessageEvents,
    wsFanoutExpected: fanoutExpected,
    wsFanoutDeliveryRatio: fanoutExpected ? newMessageEvents / fanoutExpected : 0,
    firstDeliveryLatencyMs: {
      p50: percentile(latencies, 50),
      p95: percentile(latencies, 95),
      p99: percentile(latencies, 99),
      max: latencies.length ? Math.max(...latencies) : null,
      min: latencies.length ? Math.min(...latencies) : null,
      avg: latencies.length ? latencies.reduce((a, b) => a + b, 0) / latencies.length : null,
    },
    parseErrors,
    durationSec: (Date.now() - tStart) / 1000,
  };

  console.log(JSON.stringify(summary));
})().catch((err) => {
  console.error(JSON.stringify({ error: String(err) }));
  process.exit(1);
});
