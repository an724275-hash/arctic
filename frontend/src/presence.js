import {request} from './api.js';

let latest;
let refreshedAt = 0;
let pending = false;
let sessionId;

export function presenceLabel() {
  return '<span class="online-presence" data-online-count hidden role="img"><span class="presence-dot" aria-hidden="true"></span><span data-presence-value aria-hidden="true"></span></span>';
}

export function syncPresence() {
  const node = document.querySelector('[data-online-count]');
  if (!node) return;
  const fresh = Number.isInteger(latest) && Date.now() - refreshedAt < 120000;
  node.hidden = !fresh;
  if (fresh) {
    const label = `Сейчас на сайте: ${latest.toLocaleString('ru-RU')}. Активные сессии за последние две минуты.`;
    node.querySelector('[data-presence-value]').textContent = latest.toLocaleString('ru-RU');
    node.title = label;
    node.setAttribute('aria-label', label);
  }
}

async function heartbeat() {
  if (pending || document.hidden || !navigator.onLine) return;
  if (Date.now() - refreshedAt < 45000) { syncPresence(); return; }
  pending = true;
  try {
    const reply = await request('/public/presence', {
      method: 'POST', auth: false, body: {session_id: sessionId},
    });
    if (Number.isInteger(reply.active_sessions) && reply.active_sessions >= 0) {
      latest = reply.active_sessions;
      refreshedAt = Date.now();
    }
  } catch { /* без счётчика */ }
  finally { pending = false; syncPresence(); }
}

export function installPresence() {
  try {
    sessionId = sessionStorage.getItem('arctic-presence');
    if (!/^[0-9a-f-]{36}$/i.test(sessionId || '')) {
      sessionId = crypto.randomUUID();
      sessionStorage.setItem('arctic-presence', sessionId);
    }
  } catch { sessionId = crypto.randomUUID(); }
  void heartbeat();
  setInterval(() => void heartbeat(), 60000);
  document.addEventListener('visibilitychange', () => void heartbeat());
  window.addEventListener('online', () => void heartbeat());
}
