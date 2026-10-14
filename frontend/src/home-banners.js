import {escapeHtml as e, icon} from './ui.js';
import {externalResource} from './media.js';
import './home-banners.css';

export const bannerDestinations = {
  participation: 'Как участвовать', dashboard: 'Мой кабинет', project: 'Подать проект',
  preparation: 'Подготовка к конкурсу', materials: 'Открывай Север',
  media: 'Фото и видео', rules: 'Положение', contacts: 'Контакты', partners: 'Партнёрам',
};

export function homeBanners(content) {
  const banners = content.filter(item => item.kind === 'banner' && item.published).slice(0, 3);
  if (!banners.length) return '';
  return `<section class="home-banners" aria-label="Объявления организатора">${banners.map(item => {
    const route = Object.hasOwn(bannerDestinations, item.extra?.cta_route) ? item.extra.cta_route : '';
    const external = externalResource(item.extra?.resource_url);
    const raw = item.extra?.image || item.image_url || '';
    const photo = raw.startsWith('/assets/') && !raw.includes('..') ? raw : externalResource(raw);
    const label = item.extra?.cta_label || bannerDestinations[route] || 'Подробнее';
    const action = route ? `<a class="text-link" href="/#${route}" data-route="${route}">${e(label)} ${icon('arrow')}</a>`
      : external ? `<a class="text-link" href="${e(external)}" target="_blank" rel="noopener noreferrer">${e(label)} ${icon('arrow')}</a>` : '';
    return `<article class="home-banner">${photo ? `<img src="${e(photo)}" alt="" loading="lazy" decoding="async" width="640" height="360">` : ''}<div><h2>${e(item.title)}</h2><p>${e(item.excerpt || item.body)}</p>${action}</div></article>`;
  }).join('')}</section>`;
}
