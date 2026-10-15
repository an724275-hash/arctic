const base = (import.meta.env?.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
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
  try { if (value) sessionStorage.setItem(sessionKey, JSON.stringify(value)); else sessionStorage.removeItem(sessionKey); } catch { /* без хранилища */ }
}

function sameAccount(expected) {
  if (!expected || !session) return expected === session;
  return expected.user?.id && session.user?.id ? expected.user.id === session.user.id : expected.access_token === session.access_token;
}

function accountChanged() {
  return new ApiError('Аккаунт изменился. Повтори действие.', 409);
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
  const original = session;
  let pending = refreshPending;
  if (!pending || pending.token !== original.refresh_token) {
    pending = {token:original.refresh_token,promise:null};
    refreshPending = pending;
    pending.promise = (async () => {
      try {
        const response = await fetch(`${base}/auth/refresh`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: original.refresh_token }), signal: AbortSignal.timeout(20000),
        });
        if (!response.ok) {
          if (response.status === 401 || response.status === 403) return false;
          throw new ApiError('Не удалось продлить сессию. Проверь подключение и повтори.', response.status);
        }
        const renewed = await response.json();
        if (!sameAccount(original) || session.refresh_token !== original.refresh_token) return false;
        setSession(renewed); return true;
      } catch (error) {
        if (error instanceof ApiError) throw error;
        throw new ApiError('Не удалось продлить сессию. Проверь подключение и повтори.', 0);
      } finally { if (refreshPending === pending) refreshPending = null; }
    })();
  }
  return pending.promise;
}

export async function request(path, { method = 'GET', body, auth = true, blob = false, retry = true } = {}) {
  const original = session;
  const headers = {};
  if (auth && session?.access_token) headers.Authorization = `Bearer ${session.access_token}`;
  const multipart = body instanceof FormData;
  if (body !== undefined && !multipart) headers['Content-Type'] = 'application/json';
  let response;
  try {
    response = await fetch(`${base}${path}`, {
      method, headers, body: body === undefined ? undefined : multipart ? body : JSON.stringify(body),
      signal: AbortSignal.timeout(multipart ? 120000 : path==='/assistant/ask'?45000:25000),
    });
  } catch (error) {
    throw new ApiError(error.name === 'TimeoutError' ? 'Сервер долго отвечает. Проверь соединение и повтори.' : 'Нет связи с сервером. Проверь подключение и повтори.', 0);
  }
  if (auth && !sameAccount(original)) throw accountChanged();
  if (response.status === 401 && auth) {
    if (retry && await refresh()) return request(path, { method, body, auth, blob, retry: false });
    if (!sameAccount(original) || session?.access_token !== original?.access_token) throw accountChanged();
    setSession(null);
    window.dispatchEvent(new CustomEvent('session-expired'));
    throw new ApiError('Сессия закончилась. Войди снова, чтобы продолжить.', 401);
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    if (auth && !sameAccount(original)) throw accountChanged();
    throw new ApiError(errorMessage(data, response.status), response.status, data?.detail);
  }
  if (response.status === 204) return null;
  const data = blob ? await response.blob() : await response.json();
  if (auth && !sameAccount(original)) throw accountChanged();
  return data;
}

export async function download(path, filename) {
  const blob = await request(path, { blob: true });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
