import {formatFileSize} from './ui.js';
import { escapeHtml as e, icon, button, heading } from './ui.js';
import { projectStatusNames, reviewCards, defensesPanel } from './review-components.js';

export const roleNames = { admin: 'Организатор', commission: 'Комиссия', expert: 'Эксперт', teacher: 'Наставник', participant: 'Участник' };
const date = value => value ? new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }) : 'Не указано';
const status = project => `<span class="status ${project.status === 'evaluated' ? 'success' : ''}">${icon(project.status === 'draft' ? 'file' : 'check')}${e(projectStatusNames[project.status] || project.status)}</span>`;
const action = name => `data-role-action="${name}"`;
const nomination = (s, id) => s.nominations.find(n => n.id === id)?.title || 'Исследовательский проект';

function workspaceNav(s) {
  return `<nav class="workspace-tabs" aria-label="Разделы рабочего кабинета"><a href="#workspace" data-route="workspace" class="${s.route === 'workspace' ? 'active' : ''}" ${s.route === 'workspace' ? 'aria-current="page"' : ''}>${icon('folder')}${s.user.role === 'expert' ? 'Мои назначения' : s.user.role === 'teacher' ? 'Участники и работы' : 'Работы конкурса'}</a>${['admin','commission'].includes(s.user.role) ? `<a href="#rankings" data-route="rankings" class="${s.route === 'rankings' ? 'active' : ''}" ${s.route === 'rankings' ? 'aria-current="page"' : ''}>${icon('compass')}Результаты</a>` : ''}<button class="link-button" data-role-action="refresh">Обновить ${icon('arrow')}</button></nav>`;
}

function projectRows(s) {
  const w = s.work;
  const rows = s.user.role === 'expert' ? w.assignments.map(a => ({ ...a.project, assignment: a })) : w.projects;
  if (!rows.length) return `<tr><td colspan="4"><div class="role-empty"><h3>${w.query || w.status ? 'Работы не найдены' : s.user.role === 'expert' ? 'Назначений пока нет' : 'Работ пока нет'}</h3><p>${w.query || w.status ? 'Попробуй другой запрос или статус.' : 'Новые работы появятся здесь.'}</p></div></td></tr>`;
  return rows.map(p => `<tr class="work-row">
    <td class="work-row-title"><h3>${e(p.title)}</h3><div class="work-row-meta"><span>${e(nomination(s,p.nomination_id))}</span>${p.participant_name ? `<span>${e(p.participant_name)}</span>` : ''}</div></td>
    <td class="work-row-status">${p.reviews_released ? '<span class="status success">Опубликовано</span>' : status(p)}${p.assignment?.review_submitted ? `<span class="role-small-note">Твоя оценка: ${Number(p.assignment.own_review.weighted_score).toFixed(2)} / 100</span>` : ''}</td>
    <td class="work-row-date">${date(p.submitted_at || p.created_at)}</td>
    <td class="work-row-action">${button(p.assignment?.review_submitted ? 'Посмотреть' : s.user.role === 'expert' ? 'Открыть и оценить' : 'Открыть работу', `data-role-project="${e(p.id)}"`, 'secondary small')}</td>
  </tr>`).join('');
}

export function workspace(s) {
  const w = s.work;
  const expert = s.user.role === 'expert';
  const teacher = s.user.role === 'teacher';
  const title = expert ? 'Мои назначения' : teacher ? 'Мои участники' : 'Работы конкурса';
  const students = teacher ? `<section class="panel mentor-students"><h2>Участники</h2>${w.students.length ? `<div class="student-list">${w.students.map(student => `<article><span class="student-avatar">${e(student.full_name.charAt(0))}</span><div><h3>${e(student.full_name)}</h3><p>${e([student.school, student.grade ? `${student.grade} класс` : '', student.region].filter(Boolean).join(' · '))}</p></div></article>`).join('')}</div>` : '<p class="role-empty">Нет подтверждённых участников.</p>'}${w.moreStudents ? button('Показать ещё участников', action('more-students'), 'secondary small') : ''}</section>` : '';
  return `<div class="account-line"><span>${e(s.user.full_name)}</span><span>${e(roleNames[s.user.role])}</span></div>
    ${heading(title, expert ? 'Открой назначенную работу, изучи материалы и выставь оценки. Отправленную рецензию изменить нельзя.' : teacher ? 'Здесь твои ученики, их работы и результаты. Помогай с подготовкой; тест и отправку проекта ученик выполняет сам.' : s.user.role === 'commission' ? 'Просматривай работы и результаты экспертизы. Комиссия не изменяет заявки и оценки.' : 'Проверяй заявки, возвращай на доработку или допускай к экспертизе. После оценок опубликуй результаты.', expert ? 'book' : 'compass')}${workspaceNav(s)}
    ${w.notice ? `<div class="notice" role="status"><p>${e(w.notice)}</p></div>` : ''}
    ${w.stats ? `<div class="role-stats"><div><strong>${w.stats.participants_total}</strong><span>участников</span></div><div><strong>${w.stats.projects_total}</strong><span>проектов</span></div><div><strong>${w.stats.reviews_total}</strong><span>рецензий</span></div><div><strong>${w.stats.certificates_total}</strong><span>сертификатов</span></div></div>` : ''}
    ${students}
    <section class="panel work-list">${teacher ? '<h2>Работы участников</h2>' : ''}
      <form id="work-filter-form" class="work-filters">
        <div class="form-field"><label for="work-query">Поиск работ</label><input id="work-query" name="query" type="search" maxlength="200" value="${e(w.query)}" placeholder="Название или тема"></div>
        <div class="form-field"><label for="work-status">Статус</label><select id="work-status" name="status"><option value="">Все статусы</option>${(expert ? [['awaiting','Ждут моей оценки'],['completed','Я уже оценил']] : Object.entries(projectStatusNames)).map(([key,label]) => `<option value="${key}" ${w.status === key ? 'selected' : ''}>${label}</option>`).join('')}</select></div>
        <button class="button secondary small" type="submit">Найти</button>
      </form>
      <p class="sr-only" role="status">Показано работ: ${expert ? w.assignments.length : w.projects.length}${w.hasMore ? '. Можно загрузить ещё.' : '.'}</p>
      <table class="work-table"><thead><tr><th scope="col">Исследование</th><th scope="col">Статус</th><th scope="col">Подано</th><th scope="col"><span class="sr-only">Действия</span></th></tr></thead><tbody id="work-rows">${projectRows(s)}</tbody></table>
      ${w.hasMore ? `<div class="work-list-more">${button('Загрузить ещё работы', action('more-projects'), 'secondary')}</div>` : ''}
    </section>`;
}

function materialPanel(project) {
  return `<section class="panel"><h2>Материалы исследования</h2><p class="project-abstract">${e(project.abstract)}</p>${project.files.length ? `<div class="file-list">${project.files.map(file => `<div class="file-item">${icon('file')}<div><strong>${e(file.original_name)}</strong><small>${({document:'Основной документ',presentation:'Презентация',video:'Видео'})[file.kind] || 'Материал'} · ${formatFileSize(file.size_bytes)}</small><div class="file-actions">${file.media_type === 'application/pdf' || /\.pdf$/i.test(file.original_name) ? `<button class="link-button" data-role-preview="${e(file.id)}">Открыть PDF</button>` : ''}<button class="link-button" data-file="${e(file.id)}" data-filename="${e(file.original_name)}">Скачать</button></div></div></div>`).join('')}</div>` : '<p class="role-empty">Материалы не загружены.</p>'}${project.video_url ? `<a class="text-link" href="${e(project.video_url)}" target="_blank" rel="noopener noreferrer">Посмотреть видео по ссылке ${icon('arrow')}</a>` : ''}</section>`;
}

function moderationPanel() {
  return `<section class="panel action-panel"><h2>Решение организатора</h2><form id="moderation-form" class="project-form role-form"><div class="form-field"><label for="moderation-status">Решение</label><select id="moderation-status" name="status"><option value="admitted">Допустить к конкурсу</option><option value="rejected">Вернуть на доработку</option></select></div><div class="form-field"><label for="moderation-comment">Комментарий участнику</label><textarea id="moderation-comment" name="comment" maxlength="5000" placeholder="При возврате на доработку объясни, что нужно исправить"></textarea><span class="form-caption">При возврате нужна причина, не меньше 5 символов.</span></div><div class="role-form-message" role="alert"></div><button class="button" type="submit">Проверить решение ${icon('arrow')}</button></form></section>`;
}

function assignmentPanel(w) {
  return `<section class="panel action-panel"><h2>Назначить экспертов</h2><form id="assignment-form" class="role-form"><fieldset class="expert-selector"><legend>Действующие эксперты</legend>${w.experts.length ? w.experts.map(expert => `<label class="check-field"><input type="checkbox" name="expert_ids" value="${e(expert.id)}"><span>${e(expert.full_name)}<small>${e(expert.email)}</small></span></label>`).join('') : '<p class="form-caption">Нет действующих экспертов. Добавь экспертов в конкурс.</p>'}</fieldset><div class="role-form-message" role="alert"></div><button class="button" type="submit" ${w.experts.length ? '' : 'disabled'}>Назначить выбранных ${icon('arrow')}</button></form><details class="auto-assignment"><summary>Распределить автоматически</summary><form id="auto-assignment-form" class="role-form"><div class="form-field"><label for="expert-count">Всего экспертов на эту работу</label><input id="expert-count" name="count" type="number" min="1" max="10" step="1" value="2" required></div><p class="form-caption">Назначения дополнятся до указанного числа с учётом нагрузки экспертов.</p><div class="role-form-message" role="alert"></div><button class="button secondary small" type="submit">Распределить эту работу</button></form></details></section>`;
}

function reviewForm(s) {
  const w = s.work;
  const draft = w.reviewDraft || { scores: {}, comment: '' };
  if (!w.criteria.length) return '<section class="panel"><h2>Критерии пока не настроены</h2><p class="role-empty">Организатор должен добавить действующие критерии перед оценкой.</p></section>';
  return `<section class="panel review-form-panel"><h2>Оценка исследования</h2><p class="form-caption">Изучи основной документ и дополнительные материалы. Оцени каждый критерий в пределах указанной шкалы; итог учитывает веса критериев. В комментарии объясни сильные стороны работы и конкретные рекомендации. После отправки оценки нельзя изменить.</p><form id="expert-review-form" class="role-form"><div class="criteria-fields">${w.criteria.map(criterion => `<div class="criterion-field"><div><label for="score-${e(criterion.id)}">${e(criterion.name)}</label><p>${e(criterion.description)}</p><span class="section-kicker">Вес ${e(criterion.weight)}</span></div><div class="score-input"><input id="score-${e(criterion.id)}" name="score:${e(criterion.id)}" type="number" min="0" max="${criterion.max_score}" step="any" inputmode="decimal" required value="${e(draft.scores[criterion.id] ?? '')}" aria-label="Оценка: ${e(criterion.name)}"><span>из ${e(criterion.max_score)}</span></div></div>`).join('')}</div><div class="review-score-preview"><span>Предварительный итог</span><output id="weighted-preview">—</output><span>из 100</span></div><div class="form-field"><label for="review-comment">Комментарий участнику</label><textarea id="review-comment" name="comment" minlength="10" maxlength="20000" required placeholder="Что получилось хорошо и что стоит развить в исследовании?">${e(draft.comment)}</textarea><span class="form-caption">От 10 символов. Будет виден участнику после публикации.</span></div><p id="review-draft-state" class="form-caption">${draft.savedAt ? `Черновик сохранён в этой вкладке ${new Date(draft.savedAt).toLocaleString('ru-RU')}. Организатор его не видит.` : 'Черновик доступен только в этой вкладке.'}</p><div class="role-form-message" role="alert"></div><div class="form-actions"><button type="button" class="button secondary" data-role-action="save-review-draft">Сохранить черновик</button><button type="submit" class="button">Проверить и отправить ${icon('arrow')}</button></div></form></section>`;
}

function defenseForm(project) {
  return `<section class="panel"><h2>Назначить защиту</h2><form id="defense-form" class="role-form"><div class="form-field"><label for="defense-time">Дата и время встречи</label><input id="defense-time" name="starts_at" type="datetime-local" required><span class="form-caption">Часовой пояс этого устройства</span></div><div class="form-field"><label for="defense-link">Ссылка на встречу</label><input id="defense-link" name="join_url" type="url" pattern="https?://.*" required placeholder="https://…"></div><div class="form-field"><label for="defense-description">Подробности</label><textarea id="defense-description" name="description" maxlength="5000" placeholder="Порядок подключения, длительность выступления"></textarea></div><div class="role-form-message" role="alert"></div><button class="button secondary" type="submit">Назначить встречу ${icon('clock')}</button></form></section>`;
}

export function reviewProject(s) {
  const w = s.work;
  const p = w.project;
  const admin = s.user.role === 'admin';
  const expert = s.user.role === 'expert';
  const canReview = expert && w.assignment && !w.assignment.review_submitted && p.status === 'reviewing' && !p.reviews_released;
  const canAssign = admin && ['admitted','reviewing'].includes(p.status) && !p.reviews_released;
  const feedback = !canReview || w.reviews.length ? `<section class="panel"><h2>${expert ? 'Рецензии и результат' : 'Результаты экспертизы'}</h2>${reviewCards(w.reviews, { ownExpertId:s.user.id, empty: s.user.role === 'teacher' && !p.reviews_released ? 'Рецензии появятся после публикации.' : 'Рецензий пока нет.' })}</section>` : '';
  const sidebar = `${admin && p.status === 'submitted' ? moderationPanel() : ''}${canAssign ? assignmentPanel(w) : ''}
    ${admin && p.status === 'evaluated' && !p.reviews_released ? `<section class="panel action-panel"><h2>Опубликовать результат</h2><p class="role-empty">Участник и наставник увидят оценки и комментарии.</p>${button('Опубликовать результаты', action('confirm-publish'), '', 'check')}</section>` : ''}
    ${p.moderation_comment ? `<section class="panel"><h2>Комментарий организатора</h2><p class="review-comment">${e(p.moderation_comment)}</p></section>` : ''}
    ${defensesPanel(w.defenses, p.id)}${admin && ['admitted','reviewing','evaluated'].includes(p.status) ? defenseForm(p) : ''}`.trim();
  return `<a href="#workspace" data-route="workspace" class="backlink">${icon('back')}${expert ? 'Мои назначения' : 'Работы конкурса'}</a>
    ${heading(e(p.title), `${e(p.participant_name)} · ${e(p.nomination_title || nomination(s,p.nomination_id))}`, 'folder')}
    <div class="role-project-meta">${status(p)}${p.reviews_released ? '<span>Результаты опубликованы</span>' : ''}<span>Подано ${date(p.submitted_at)}</span><span>Наставник: ${e(p.mentor_name||'не назначен')}</span><button class="link-button" data-role-action="refresh">Обновить статус</button></div>
    ${w.notice ? `<div class="notice" role="status"><p>${e(w.notice)}</p></div>` : ''}
    <div class="workspace-grid role-project-grid${sidebar ? '' : ' role-project-wide'}"><div class="stack role-document">${materialPanel(p)}${canReview ? reviewForm(s) : ''}${feedback}</div>${sidebar ? `<aside class="stack">${sidebar}</aside>` : ''}</div>`;
}

export function rankings(s) {
  const w = s.work;
  const ranking = w.ranking;
  return `${heading('Результаты конкурса', 'Сравнивай работы в выбранной номинации по среднему взвешенному баллу экспертов. Количество рецензий показывает, сколько оценок вошло в итог. Статус публикации определяет, доступна ли обратная связь участнику.', 'compass')}${workspaceNav(s)}<section class="panel"><form id="ranking-filter-form" class="ranking-filter"><div class="form-field"><label for="ranking-nomination">Номинация</label><select id="ranking-nomination" name="nomination_id"><option value="">Все номинации</option>${s.nominations.map(n=>`<option value="${e(n.id)}" ${n.id === w.rankingNomination ? 'selected' : ''}>${e(n.title)}</option>`).join('')}</select></div><button class="button secondary small" type="submit">Показать</button></form><div class="rankings-labels" aria-hidden="true"><span>№</span><span>Исследование</span><span>Баллы</span><span></span></div><div class="rankings-list">${ranking.items.length ? ranking.items.map(item=>`<article class="ranking-row"><span class="ranking-place">${item.rank}</span><div><h3>${e(item.project.title)}</h3><p>${e(item.participant.full_name)} · ${e(item.nomination.title)}</p><span class="status ${item.reviews_released ? 'success' : ''}">${item.reviews_released ? 'Опубликовано' : 'Ожидает публикации'}</span></div><div class="ranking-score"><strong>${item.average_score.toLocaleString('ru-RU',{maximumFractionDigits:2})}</strong><span>из 100 · рецензий: ${item.review_count}</span></div>${button('Открыть', `data-role-project="${e(item.project.id)}"`, 'secondary small')}</article>`).join('') : '<p class="role-empty">В этой номинации пока нет работ с завершённой экспертизой.</p>'}</div><div class="ranking-pagination"><span>Всего работ: ${ranking.total}</span><div>${button('Назад', action('ranking-previous'), 'secondary small', 'back', w.rankingOffset ? '' : 'disabled')}${button('Далее', action('ranking-next'), 'secondary small', 'arrow', w.rankingOffset + ranking.items.length < ranking.total ? '' : 'disabled')}</div></div></section>`;
}

export const roleViews = { workspace, 'review-project': reviewProject, rankings };
