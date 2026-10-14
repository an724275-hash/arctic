// Музыка запускается только после явного нажатия пользователя.
let enabled = false;
let context;
const music = new Audio('/assets/northern-light.wav');
music.loop = true;
music.volume = 0.22;
music.preload = 'none';
const speaker = '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 5 6 9H3v6h3l5 4V5Z"/><path d="M15 8a6 6 0 0 1 0 8M18 5a10 10 0 0 1 0 14"/></svg>';
export function soundButton(placement = 'header') {
  return `<button type="button" class="sound-toggle ${placement === 'hero' ? 'sound-hero' : ''} ${enabled ? 'sound-on' : ''}" data-action="sound-toggle" aria-pressed="${enabled}" aria-label="${enabled ? 'Выключить музыку' : 'Включить музыку'}" title="Спокойная музыка и звуки действий">${speaker}<span>${enabled ? 'Звук включён' : 'Включить звук'}</span></button>`;
}
export async function toggleSound() {
  if (enabled) { music.pause(); enabled = false; }
  else {
    await music.play();
    enabled = true;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) { context ||= new AudioContext(); await context.resume(); }
  }
  document.querySelectorAll('.sound-toggle').forEach(button => { button.outerHTML = soundButton(button.classList.contains('sound-hero') ? 'hero' : 'header'); });
}
export function playCue(kind = 'complete') {
  if (!enabled || !context || context.state !== 'running') return;
  const notes = { welcome: [523.25, 783.99], submitted: [587.33, 880], complete: [523.25, 659.25, 783.99] }[kind];
  if (!notes) return;
  notes.forEach((frequency, index) => {
    const start = context.currentTime + index * .14;
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.type = 'sine';
    oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(0,start);
    gain.gain.linearRampToValueAtTime(.028,start + .012);
    gain.gain.exponentialRampToValueAtTime(.0001,start + .28);
    oscillator.connect(gain); gain.connect(context.destination);
    oscillator.start(start); oscillator.stop(start + .3);
  });
}
document.addEventListener('visibilitychange', () => {
  if (document.hidden) music.pause();
  else if (enabled) void music.play().catch(() => { enabled = false; document.querySelectorAll('.sound-toggle').forEach(button => { button.outerHTML = soundButton(button.classList.contains('sound-hero') ? 'hero' : 'header'); }); });
});
