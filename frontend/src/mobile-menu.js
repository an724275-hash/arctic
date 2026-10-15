import {icon, escapeHtml as e} from './ui.js';
import {routeUrl} from './routes.js';
import './mobile-menu.css';

export function mobileMenu(state) {
  const groups = [
    ['Конкурс', [
      ['home', 'Главная', 'home'], ['about', 'О конкурсе', 'compass'],
      ['participation', 'Как участвовать', 'check'], ['rules', 'Положение', 'shield'],
      ['news', 'Новости', 'file'],
    ]],
    ['Открывай Север', [
      ['preparation', 'Подготовка к конкурсу', 'mountain'],
      ['materials', 'Статьи об Арктике', 'book'], ['media', 'Медиатека', 'image'],
    ]],
    ['Помощь и связь', [
      ['help', 'Помощь', 'info'], ['contacts', 'Связь с организатором', 'message'],
      ['partners', 'Партнёрам', 'users'],
    ]],
  ];
  const account = [['dashboard', state.user ? 'Личный кабинет' : 'Войти', 'user']];
  if (state.user) {
    account.push(['profile', 'Настройки профиля', 'settings']);
    if (state.user.role !== 'partner') account.push(['awards', 'Мои документы', 'file']);
    account.push(['notifications', 'Уведомления', 'bell']);
  }
  groups.unshift(['Аккаунт', account]);
  return `<div class="mobile-menu-heading"><h2 id="dialog-title">Меню</h2><button type="button" class="round-icon" data-action="close" aria-label="Закрыть меню">${icon('close')}</button></div><nav class="mobile-menu-body" aria-label="Разделы сайта">${groups.map(([title, items], index) => `<section class="menu-section" aria-labelledby="menu-group-${index}"><h3 id="menu-group-${index}">${title}</h3>${items.map(([route, label, symbol]) => {
    const current = state.route === route || route === 'materials' && state.route === 'article';
    return `<a href="${routeUrl(route)}" data-route="${route}" ${current ? 'aria-current="page"' : ''}>${icon(symbol)}<span>${e(label)}</span>${current ? '<small>Открыто</small>' : ''}</a>`;
  }).join('')}</section>`).join('')}${state.user ? `<button class="menu-logout" data-action="logout">${icon('back')}<span>Выйти из аккаунта</span></button>` : ''}</nav>`;
}
