const escapeHtml = (text = '') => String(text).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));
function icon(name, className = 'icon') {
  const paths = {
    arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>', back: '<path d="M19 12H5m6-6-6 6 6 6"/>',
    check: '<path d="m5 12 4 4L19 6"/>', clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    book: '<path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Zm0 0v15"/>',
    mountain: '<path d="m2 20 7-14 4 7 3-5 6 12H2Zm4-8 3 2 3-2"/>',
    compass: '<circle cx="12" cy="12" r="9"/><path d="m16 8-2 6-6 2 2-6 6-2Z"/>',
    folder: '<path d="M3 6a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v10H3V6Z"/>',
    file: '<path d="M6 3h8l4 4v14H6V3Zm8 0v5h4M9 12h6m-6 4h6"/>',
    upload: '<path d="M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6"/>',
    user: '<circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/>',
    menu: '<path d="M5 7h14M5 12h14M5 17h14"/>', close: '<path d="m6 6 12 12M6 18 18 6"/>',
    info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v6m0-10v.1"/>',
    home: '<path d="m3 10 9-7 9 7v11H3V10Zm6 11v-7h6v7"/>',
    leaf: '<path d="M5 19C-1 5 11 2 21 3c0 11-6 20-16 16Zm0 0L16 8"/>',
    shield: '<path d="m12 2 8 4v7c0 5-8 9-8 9s-8-4-8-9V6l8-4Z"/><path d="m8 12 3 3 5-6"/>',
  };
  return `<svg class="${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths[name] || paths.compass}</svg>`;
}
function mark(className = 'brand-mark') {
  return `<svg class="${className}" viewBox="0 0 48 48" fill="none" aria-hidden="true"><path d="M24 3 40 13v21L24 45 8 34V13L24 3Z" stroke="currentColor" stroke-width="1.7"/><path d="m13 31 11-18 11 18H13Z" fill="currentColor"/><path d="m19 22 5 3 5-3" stroke="#fff" stroke-width="1.6"/><path d="M24 3v7m0 28v7M8 13l6 4m20 14 6 3M8 34l6-3m20-14 6-4" stroke="currentColor" stroke-width="1.4"/></svg>`;
}
function orbit(className = 'orbit-art') {
  return `<svg class="${className}" viewBox="0 0 300 300" fill="none" stroke="currentColor" aria-hidden="true"><circle cx="150" cy="150" r="145"/><circle cx="150" cy="150" r="119"/><circle cx="150" cy="150" r="85"/><circle cx="150" cy="150" r="50"/><path d="M5 150h290M150 5v290M48 48l204 204M48 252 252 48" opacity=".4"/><path d="m94 119 18-25 14 13 15-30 23 7 7 24 32 9 7 24-20 21 10 22-26 29-25-9-15 17-12-24-25-11 5-32-20-20 12-15Z" fill="currentColor" fill-opacity=".12"/><circle cx="150" cy="150" r="6" fill="currentColor"/></svg>`;
}
function ornament() {
  let bands = '';
  for (let x = 0; x < 960; x += 48) bands += `<path d="M${x} 12h48m-24-9 9 9-9 9-9-9 9-9Z"/><path d="M${x + 4} 12c0-6 8-8 11-8-1 6-6 8-11 8Zm29 0c0 6 8 8 11 8-1-6-6-8-11-8Z" fill="currentColor" stroke="none"/>`;
  return `<div class="ornament" aria-hidden="true"><svg viewBox="0 0 960 24" fill="none" stroke="currentColor" stroke-width="1.2">${bands}</svg></div>`;
}
function button(label, action, variant = '', symbol = 'arrow', attrs = '') {
  return `<button type="button" class="button ${variant}" ${action} ${attrs}><span>${label}</span>${symbol ? icon(symbol) : ''}</button>`;
}
const go = (name) => `data-route="${name}"`;
const act = (name) => `data-action="${name}"`;

function heading(title, subtitle, symbol = 'compass') {
  return `<div class="page-heading"><div><h1 tabindex="-1">${title}</h1><p>${subtitle}</p></div><div class="view-header-icon">${icon(symbol)}</div></div>`;
}

function home() {
  const stages = [['01','Исследуй','Познакомься с природой и культурой северных территорий.'],['02','Проверь себя','Пройди тест и получи первый результат.'],['03','Создай проект','Выбери тему, собери материалы и предложи свою идею.'],['04','Поделись открытием','Отправь работу на оценку и подготовь её защиту.']];
  return `<section class="hero" id="about"><div class="hero-copy"><span class="eyebrow"><span class="dot"></span>Удивительная и неизведанная Арктика</span><h1 tabindex="-1">Открой свою<br>Арктику.</h1><p class="intro">Там, где заканчиваются знакомые маршруты, начинаются твои открытия. Исследуй Север и создай собственный проект.</p><div class="hero-actions">${button('Начать экспедицию', go('dashboard'))}<a class="button ghost" href="#route" data-anchor="route">Как всё устроено ${icon('arrow')}</a></div><div class="hero-footnote">${orbit('mini-orbit')}<p>Школьный конкурс о природе,<br>людях и будущем Арктики.</p></div></div><div class="hero-art"><img class="hero-image" src="assets/arctic-coast.webp" alt="Художественный образ арктического залива: белые льдины, синий океан и зелёная тундра"><span class="photo-label">${icon('mountain')}Север. Территория открытий.</span>${mark('compass')}<a href="#library" data-anchor="library" class="expedition-card"><div><div class="number">ПОЛЕВОЙ АТЛАС / 01</div><h2>Большой мир<br>за полярным кругом</h2></div><span class="round-icon">${icon('arrow')}</span></a></div></section>${ornament()}<section class="route" id="route"><div class="route-top"><h2>Твой маршрут к открытию</h2><span>От первого вопроса — к своей идее</span></div><div class="route-steps">${stages.map(([n,t,p]) => `<div class="route-step"><span class="route-number">${n}</span><h3>${t}</h3><p>${p}</p></div>`).join('')}</div></section><section class="spaced" id="library"><div class="section-head"><h2 class="section-title">Север ближе,<br>чем кажется</h2><p>Прежде чем отправиться в путь, загляни в наш полевой атлас. У каждого открытия есть начало.</p></div><div class="atlas-grid"><article class="atlas-story"><span class="eyebrow">Полевые заметки</span><h3>Хрупкая природа.<br>Большие вопросы.</h3><p>Что делает Арктику особенной — и как исследовать её бережно?</p><button type="button" class="text-link link-button" data-article="nature">Открыть заметку ${icon('arrow')}</button>${orbit()}</article><div class="article-list">${[['01','nature','Природа без границ','Лёд, океан и жизнь на Севере'],['02','culture','Север — это ещё и люди','Культура, ремёсла, связь с местом'],['03','idea','С чего начинается проект','Наблюдение, вопрос и твоя идея']].map(([n,k,t,p]) => `<a class="article-row" href="#${k}" data-article="${k}"><span class="index">${n}</span><div><h3>${t}</h3><p>${p}</p></div>${icon('arrow')}</a>`).join('')}</div></div></section>`;
}

export { escapeHtml, icon, mark, orbit, ornament, button, heading, home, go, act };
