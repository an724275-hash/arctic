import {escapeHtml as e} from './ui.js';
import './public-criteria.css';

const number = value => Number(value).toLocaleString('ru-RU', {maximumFractionDigits: 2});

export function publicCriteria(criteria = []) {
  if (!criteria.length) return '';
  return `<section class="public-section"><h2 id="public-criteria-title">Как оценивают работу</h2><p>Эксперт оценивает проект по критериям ниже. Итог учитывает вес каждого критерия. Баллы и комментарии станут доступны после публикации результатов.</p><table class="public-criteria" aria-labelledby="public-criteria-title"><thead><tr><th scope="col">Критерий</th><th scope="col">Максимум</th><th scope="col">Вес</th></tr></thead><tbody>${criteria.map(item => `<tr><th scope="row">${e(item.name)}${item.description && !item.description.startsWith('Демонстрационный') ? `<span>${e(item.description)}</span>` : ''}</th><td>${number(item.max_score)}</td><td>${number(item.weight)}</td></tr>`).join('')}</tbody></table><p class="form-caption">Вес показывает вклад критерия в итоговую оценку. Итог приводится к шкале от 0 до 100.</p></section>`;
}
