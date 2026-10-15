export function createQuizClock(now = () => performance.now()) {
  let attemptId;
  let deadline = 0;

  function sync(attempt, requestStarted = now()) {
    const received = now();
    const remaining = Date.parse(attempt.expires_at) - Date.parse(attempt.server_now);
    const duration = Number.isFinite(remaining) ? remaining : Math.max(0, Number(attempt.seconds_remaining) || 0) * 1000;
    const latency = Math.max(0, received - requestStarted) / 2;
    const next = attempt.status === 'active' ? received + Math.max(0, duration - latency) : received;
    deadline = attempt.id === attemptId ? Math.min(deadline, next) : next;
    attemptId = attempt.id;
    return deadline;
  }

  return {sync, get deadline() { return deadline; }};
}
