const base = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
const sessionKey = 'arctic-session';
let session;
try { session = JSON.parse(sessionStorage.getItem(sessionKey) || 'null'); } catch { session = null; }
let refreshPending;

export class ApiError extends Error {
  constructor(message, status, details) { super(message); this.name = 'ApiError'; this.status = status; this.details = details; }
}

export function getSession() { return session; }
export function setSession(value) {
  session = value;
  try { if (value) sessionStorage.setItem(sessionKey, JSON.stringify(value)); else sessionStorage.removeItem(sessionKey); } catch { /* В приватном режиме сессия живёт до перезагрузки. */ }
}

function errorMessage(data, status) {
  if (typeof data?.detail === 'string') return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map(item => String(item.msg || 'Проверьте поле').replace(/^Value error, /, '')).join('. ');
  if (status === 429) return 'Слишком много запросов. Подожди немного и повтори.';
  if (status >= 500) return 'Сервис временно недоступен. Попробуй ещё раз.';
  return 'Не удалось выполнить запрос. Попробуй ещё раз.';
}

async function refresh() {
  if (!session?.refresh_token) return false;
  if (!refreshPending) refreshPending = (async () => {
    try {
      const response = await fetch(`${base}/auth/refresh`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: session.refresh_token }), signal: AbortSignal.timeout(20000),
      });
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) return false;
        throw new ApiError('Не удалось продлить сессию. Проверь подключение и повтори.', response.status);
      }
      setSession(await response.json()); return true;
    } finally { refreshPending = null; }
  })();
  return refreshPending;
}

export async function request(path, { method = 'GET', body, auth = true, blob = false, retry = true } = {}) {
  const headers = {};
  if (auth && session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
  const multipart = body instanceof FormData;
  if (body !== undefined && !multipart) headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(`${base}${path}`, {
      method, headers, body: body === undefined ? undefined : multipart ? body : JSON.stringify(body),
      signal: AbortSignal.timeout(multipart ? 120000 : 25000),
    });
  } catch (error) {
    throw new ApiError(error.name === 'TimeoutError' ? 'Сервер долго отвечает. Проверь соединение и повтори.' : 'Нет связи с сервером. Проверь подключение и повтори.', 0);
  }
  if (response.status === 401 && auth) {
    if (retry && await refresh()) return request(path, { method, body, auth, blob, retry: false });
    setSession(null);
    window.dispatchEvent(new CustomEvent('session-expired'));
    throw new ApiError('Сессия закончилась. Войди снова, чтобы продолжить.', 401);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new ApiError(errorMessage(data, response.status), response.status, data?.detail);
  }
  if (response.status === 204) return null;
  return blob ? response.blob() : response.json();
}

export async function download(path, filename) {
  const blob = await request(path, { blob: true });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
