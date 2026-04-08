const fs = require('fs');
const { performance } = require('perf_hooks');

const env = Object.fromEntries(
  fs.readFileSync('/tmp/aicomm_loadtest/context.env', 'utf8')
    .trim()
    .split('\n')
    .map((line) => {
      const idx = line.indexOf('=');
      return [line.slice(0, idx), line.slice(idx + 1)];
    })
);

const BASE = env.BASE;
const CHAT_ID = env.CHAT_ID;
const TOKEN = env.TOKEN;
const NOTIFY_TOKEN = env.NOTIFY_TOKEN;

const WS_CLIENTS = 20;
const SEND_COUNT = 200;
const OPEN_TIMEOUT_MS = 10000;
const DRAIN_TIMEOUT_MS = 15000;

const runId = `LT-${Date.now()}`;
const wsUrl = `ws://127.0.0.1:6687/ws?token=${encodeURIComponent(NOTIFY_TOKEN)}`;

const sendAt = new Map();
const firstRecvAt = new Map();
const pendingRecvAt = new Map();
let newMessageEvents = 0;
let parseErrors = 0;

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
    opens.push(new Promise((resolve, reject) => {
      const t = setTimeout(() => reject(new Error(`ws open timeout idx=${i}`)), OPEN_TIMEOUT_MS);
      ws.onopen = () => {
        clearTimeout(t);
        resolve();
      };
      ws.onerror = (e) => {
        clearTimeout(t);
        reject(new Error(`ws error idx=${i}: ${e?.message || 'unknown'}`));
      };
      ws.onmessage = (evt) => {
        try {
          const obj = JSON.parse(evt.data);
          if (obj?.event === 'NewMessage' && obj?.content && obj.content.startsWith(runId)) {
            newMessageEvents += 1;
            const msgId = String(obj.id);
            const now = performance.now();
            if (!firstRecvAt.has(msgId)) {
              if (sendAt.has(msgId)) {
                firstRecvAt.set(msgId, now);
              } else if (!pendingRecvAt.has(msgId)) {
                pendingRecvAt.set(msgId, now);
              }
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
  for (let i = 0; i < SEND_COUNT; i++) {
    const content = `${runId}-msg-${i}`;
    const t0 = performance.now();
    const res = await fetch(`${BASE}/api/chats/${CHAT_ID}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${TOKEN}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ content, files: [] }),
    });
    if (!res.ok) {
      throw new Error(`send failed status=${res.status} idx=${i}`);
    }
    const json = await res.json();
    const msgId = String(json.id);
    sendAt.set(msgId, t0);
    if (!firstRecvAt.has(msgId) && pendingRecvAt.has(msgId)) {
      firstRecvAt.set(msgId, pendingRecvAt.get(msgId));
      pendingRecvAt.delete(msgId);
    }
  }
}

(async () => {
  const tStart = Date.now();
  const sockets = await openClients();
  await sendMessages();

  const drainStart = Date.now();
  while (Date.now() - drainStart < DRAIN_TIMEOUT_MS) {
    if (firstRecvAt.size >= SEND_COUNT) break;
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

  const summary = {
    runId,
    startedAt: new Date(tStart).toISOString(),
    wsClients: WS_CLIENTS,
    sendCount: SEND_COUNT,
    firstDeliveryReceived: latencies.length,
    firstDeliverySuccessRate: SEND_COUNT ? latencies.length / SEND_COUNT : 0,
    wsFanoutEventsReceived: newMessageEvents,
    wsFanoutExpected: WS_CLIENTS * SEND_COUNT,
    wsFanoutDeliveryRatio: WS_CLIENTS * SEND_COUNT ? newMessageEvents / (WS_CLIENTS * SEND_COUNT) : 0,
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

  fs.writeFileSync('/tmp/aicomm_loadtest/ws_summary.json', JSON.stringify(summary, null, 2));
  console.log(JSON.stringify(summary, null, 2));
})().catch((err) => {
  const failure = { error: String(err) };
  fs.writeFileSync('/tmp/aicomm_loadtest/ws_summary.json', JSON.stringify(failure, null, 2));
  console.error(err);
  process.exit(1);
});
