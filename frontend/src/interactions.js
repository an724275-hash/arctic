const feedback = new WeakMap();
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

export function installInteractionMotion() {
  const play = event => {
    if (reducedMotion.matches) return;
    if (event.type === 'keydown' && (event.repeat || !['Enter', ' '].includes(event.key))) return;
    const control = event.target.closest('button,a[data-route],a[data-article],summary');
    if (!control || control.disabled || control.matches('.answer,[data-question]')) return;
    const target = control.querySelector('.icon');
    if (!target || typeof target.animate !== 'function') return;
    feedback.get(target)?.cancel();
    const animation = target.animate([
      {transform:'scale(1)', opacity:1},
      {transform:'scale(.8)', opacity:.6, offset:.3},
      {transform:'scale(1.08)', opacity:1, offset:.7},
      {transform:'scale(1)', opacity:1},
    ], {duration:280, easing:'ease-out'});
    feedback.set(target, animation);
  };
  document.addEventListener('pointerdown', play, {passive:true});
  document.addEventListener('keydown', play);
}
