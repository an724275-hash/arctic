import {icon, escapeHtml as e} from './ui.js';
import {routeUrl} from './routes.js';

export function mobileMenu(state) {
  const items = [
    ['home', 'Главная', 'home'],
    ['about', 'О конкурсе', 'compass'],
    ['participation', 'Как участвовать', 'check'],
    ['materials', 'Открывай Север', 'book'],
    ['preparation', 'Подготовка к конкурсу', 'mountain'],
    ['news', 'Новости', 'file'],
    ['media', 'Медиатека', 'image'],
    ['rules', 'Положение', 'shield'],
    ['help', 'Помощь', 'info'],
    ['partners', 'Партнёрам', 'users'],
    ['contacts', 'Связь с организатором', 'message'],
  ];
  if (state.user) {
    items.push(['profile', 'Настройки профиля', 'settings']);
    if (state.user.role !== 'partner') items.push(['awards', 'Мои документы', 'file']);
    items.push(['notifications', 'Уведомления', 'bell']);
  }
  items.push(['dashboard', state.user ? 'Личный кабинет' : 'Войти', 'user']);
  return `<nav class="menu-links" aria-label="Разделы сайта">${items.map(([route, label, symbol]) => {
    const current = state.route === route || route === 'materials' && state.route === 'article';
    return `<a href="${routeUrl(route)}" data-route="${route}" ${current ? 'aria-current="page"' : ''}>${icon(symbol)}<span>${e(label)}</span></a>`;
  }).join('')}${state.user ? `<button class="link-button" data-action="logout">${icon('back')}<span>Выйти из аккаунта</span></button>` : ''}</nav>`;
}
