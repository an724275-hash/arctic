import { escapeHtml as e, icon } from './ui.js';

export const projectStatusNames = {
  draft: 'Черновик', submitted: 'На проверке', admitted: 'Допущен к конкурсу',
  rejected: 'Нужны изменения', reviewing: 'На экспертизе', evaluated: 'Оценён',
};

export function reviewCards(reviews, { empty = 'Рецензий пока нет.', ownExpertId } = {}) {
  if (!reviews.length) return `<p class="role-empty">${e(empty)}</p>`;
  return `<div class="review-cards">${reviews.map((review, index) => `
    <article class="review-card">
      <div class="review-card-heading"><div><h3>${review.expert_id === ownExpertId ? 'Твоя рецензия' : `Рецензия ${index + 1}`}</h3><p>${new Date(review.submitted_at).toLocaleString('ru-RU')}</p></div><strong>${Number(review.weighted_score).toLocaleString('ru-RU', { maximumFractionDigits: 2 })}<small> из 100</small></strong></div>
      <dl class="score-breakdown">${review.criteria_snapshot.map(criterion => `<div><dt>${e(criterion.name)}<small>Вес ${e(criterion.weight)}</small></dt><dd>${e(review.scores[criterion.id])} / ${e(criterion.max_score)}</dd></div>`).join('')}</dl>
      <p class="review-comment">${e(review.comment)}</p>
    </article>`).join('')}</div>`;
}

export function defensesPanel(defenses, projectId) {
  const matching = projectId ? defenses.filter(item => item.project_id === projectId) : defenses;
  if (!matching.length) return '';
  return `<section class="panel defense-panel"><h2>Защита проекта</h2>${matching.map(item => `<article class="defense-item"><div class="defense-time">${icon('clock')}<strong>${new Date(item.starts_at).toLocaleString('ru-RU', { dateStyle: 'long', timeStyle: 'short' })}</strong></div><p class="form-caption">Время устройства</p>${item.description ? `<p class="review-comment">${e(item.description)}</p>` : ''}<a class="button secondary small" href="${e(item.join_url)}" target="_blank" rel="noopener noreferrer">Открыть встречу ${icon('arrow')}</a></article>`).join('')}</section>`;
}

export function projectOutcome(project, reviews, defenses, ownExpertId) {
  return `<div class="project-outcomes">${defensesPanel(defenses, project.id)}<section class="panel"><div class="panel-heading"><h2>Результаты экспертизы</h2><span class="status ${project.reviews_released ? 'success' : ''}">${icon(project.reviews_released ? 'check' : 'clock')}${project.reviews_released ? 'Опубликованы' : 'Ещё не опубликованы'}</span></div>${reviewCards(reviews, { ownExpertId, empty: project.reviews_released ? 'Опубликованных рецензий пока нет.' : 'Оценки появятся после публикации организатором.' })}</section></div>`;
}
