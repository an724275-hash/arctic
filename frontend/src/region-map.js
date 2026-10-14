import regions from './region-map-data.json';
import {escapeHtml as e} from './ui.js';
import './region-map.css';

const aliases = {
  'горно алтай': 'алтай', 'алтайская республика': 'алтай', 'саха': 'саха якутия',
  'якутия': 'саха якутия', 'северная осетия алания': 'северная осетия', 'кемеровская кузбасс': 'кемеровская',
  'ханты мансийский югра': 'ханты мансийский',
  'кабардино балкарская': 'кабардино балкария', 'карачаево черкесская': 'карачаево черкесия',
  'удмуртская': 'удмуртия', 'чеченская': 'чечня', 'чувашская': 'чувашия',
};
function key(value) {
  const clean = String(value || '').toLowerCase().replaceAll('ё', 'е')
    .replace(/республика|автономный|автономная|автономное|область|край|округ/gu, '')
    .replace(/[^а-яa-z0-9]+/gu, ' ').trim().replace(/\s+/gu, ' ');
  return aliases[clean] || clean;
}

export function regionMap(rows) {
  const counts = new Map();
  for (const row of rows) counts.set(key(row.label), (counts.get(key(row.label)) || 0) + row.count);
  const maximum = Math.max(1, ...rows.map(row => row.count));
  const known = new Set(regions.map(region => key(region.name)));
  const unplaced = rows.filter(row => !known.has(key(row.label)));
  return `<figure class="region-map"><svg viewBox="0 0 790 360" role="img" aria-labelledby="region-map-title region-map-description"><title id="region-map-title">Участники по регионам</title><desc id="region-map-description">Чем темнее регион, тем больше участников. Точные числа доступны в таблице ниже.</desc>${regions.map(region => {
    const count = counts.get(key(region.name)) || 0;
    const tone = count ? 1 + Math.min(3, Math.floor(count / maximum * 3)) : 0;
    return `<path d="${region.path}" class="region-tone-${tone}"><title>${e(region.name)}: ${count}</title></path>`;
  }).join('')}</svg><figcaption><span class="region-map-legend"><i></i> Меньше участников <i></i> Больше участников</span><span>Числа относятся к региону, указанному в профиле.</span></figcaption></figure>${unplaced.length ? `<p class="form-caption">Не нанесены на карту: ${unplaced.map(row => `${e(row.label || 'Регион не указан')} (${row.count})`).join(', ')}. Эти участники включены в общую статистику.</p>` : ''}<details class="chart-table"><summary>Точные данные по регионам</summary><table><thead><tr><th>Регион</th><th>Участников</th></tr></thead><tbody>${rows.length ? rows.map(row => `<tr><td>${e(row.label || 'Не указан')}</td><td>${row.count}</td></tr>`).join('') : '<tr><td colspan="2">Участников пока нет</td></tr>'}</tbody></table></details>`;
}
