import {escapeHtml as e, heading, icon} from './ui.js';
import './media.css';

export function externalResource(value){
  try{const url=new URL(value);return url.protocol==='https:'&&!url.username&&!url.password?url.href:'';}catch{return '';}
}
function mediaItem(item){
  const resource=externalResource(item.extra?.resource_url);
  const raw=item.extra?.image||item.image_url||'';
  const photo=raw.startsWith('/assets/')&&!raw.includes('..')?raw:externalResource(raw);
  return `<article class="media-item">${photo?`<img src="${e(photo)}" alt="${e(item.title)}" loading="lazy" decoding="async" width="1280" height="720">`:''}<div><h3>${e(item.title)}</h3>${item.extra?.year?`<p class="form-caption">${e(item.extra.year)}</p>`:''}<p>${e(item.excerpt||item.body)}</p>${item.extra?.caption?`<p class="form-caption">${e(item.extra.caption)}</p>`:''}${resource?`<a class="text-link" href="${e(resource)}" target="_blank" rel="noopener noreferrer">Открыть материал ${icon('arrow')}</a>`:`<a class="text-link" href="/materials/${encodeURIComponent(item.slug)}" data-content="${e(item.slug)}">Подробнее ${icon('arrow')}</a>`}</div></article>`;
}
export function mediaView(s){
  const rows=s.content.filter(x=>x.kind==='media'),gallery=rows.filter(x=>!x.extra?.archive),archive=rows.filter(x=>x.extra?.archive);
  return `<div class="public-page">${heading('Медиатека','Фото, видео и материалы исследований об Арктике.')}<section class="public-section"><h2>Фото и видео</h2>${gallery.length?`<div class="media-grid">${gallery.map(mediaItem).join('')}</div>`:'<p>Организатор ещё не опубликовал материалы экспедиций. Пока можно изучить статьи об Арктике.</p><a class="text-link" href="/materials" data-route="materials">Открыть статьи</a>'}</section><section class="public-section"><h2>Работы прошлых лет</h2>${archive.length?`<div class="media-grid">${archive.map(mediaItem).join('')}</div>`:'<p>Архив появится после публикации работ организатором.</p>'}</section></div>`;
}
