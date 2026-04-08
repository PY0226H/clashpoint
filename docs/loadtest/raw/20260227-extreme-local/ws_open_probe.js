const fs = require('fs');
const env = Object.fromEntries(
  fs.readFileSync('/tmp/aicomm_loadtest_ext/context.env', 'utf8').trim().split('\n').map((line) => {
    const i = line.indexOf('=');
    return [line.slice(0, i), line.slice(i + 1)];
  })
);

const NOTIFY_TOKEN = env.NOTIFY_TOKEN;
const wsUrl = `ws://127.0.0.1:6687/ws?token=${encodeURIComponent(NOTIFY_TOKEN)}`;
const TARGET = Number(process.argv[2] || 400);
const TIMEOUT = Number(process.argv[3] || 15000);

let openOk = 0;
let failTimeout = 0;
let failError = 0;
let closeBeforeOpen = 0;

async function main() {
  const tasks = [];
  const sockets = [];
  for (let i = 0; i < TARGET; i++) {
    const ws = new WebSocket(wsUrl);
    sockets.push(ws);
    tasks.push(new Promise((resolve) => {
      let opened = false;
      const t = setTimeout(() => {
        if (!opened) {
          failTimeout += 1;
          try { ws.close(); } catch (_) {}
          resolve();
        }
      }, TIMEOUT);

      ws.onopen = () => {
        if (opened) return;
        opened = true;
        clearTimeout(t);
        openOk += 1;
        resolve();
      };

      ws.onerror = () => {
        if (opened) return;
        clearTimeout(t);
        failError += 1;
        resolve();
      };

      ws.onclose = () => {
        if (!opened) closeBeforeOpen += 1;
      };
    }));
  }
  await Promise.all(tasks);
  const out = { target: TARGET, openOk, failTimeout, failError, closeBeforeOpen };
  console.log(JSON.stringify(out));
  for (const ws of sockets) {
    try { ws.close(); } catch (_) {}
  }
}

main().catch((e) => {
  console.error(JSON.stringify({ error: String(e) }));
  process.exit(1);
});
