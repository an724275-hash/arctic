import {escapeHtml as e, icon} from './ui.js';
import {externalResource} from './media.js';

export const documentTypes = {
  regulation: 'Положение', research: 'Оформление исследования',
  presentation: 'Оформление презентации', consent: 'Согласие представителя', other: 'Другой документ',
};

export function documentResource(item) {
  const url = externalResource(item?.extra?.resource_url);
  if (!url) return '';
  return `<a class="text-link" aria-label="Открыть документ: ${e(item.title)}" href="${e(url)}" target="_blank" rel="noopener noreferrer">Открыть документ ${icon('file')}</a>`;
}

export function participationDocuments(content) {
  const rows = content.filter(item => item.kind === 'document' && item.published
    && !item.extra?.draft && !item.slug.includes('draft'));
  if (!rows.length) return '';
  return `<section class="public-section"><h2>Документы организатора</h2><div class="published-list">${rows.map(item => `<article class="article-row"><div><h3>${e(item.title)}</h3><p>${e(item.excerpt || '')}</p>${documentResource(item) || `<a class="text-link" href="/materials/${encodeURIComponent(item.slug)}" data-content="${e(item.slug)}">Читать документ ${icon('arrow')}</a>`}</div></article>`).join('')}</div></section>`;
}

export function contestRegulation(content) {
  const candidates = content.filter(item => ['document', 'page'].includes(item.kind) && (item.extra?.document_type === 'regulation'
    || /rules|regulation|polozhenie/.test(item.slug)));
  return candidates.find(item => !item.extra?.draft && !item.slug.includes('draft')) || candidates[0];
}
