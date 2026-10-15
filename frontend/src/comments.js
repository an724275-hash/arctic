import {request, getSession} from './api.js';
import {escapeHtml as e, heading, icon} from './ui.js';
import './comments.css';

const statuses = {pending:'На проверке', approved:'Опубликован', rejected:'Не опубликован'};
const date = value => new Date(value).toLocaleString('ru-RU', {dateStyle:'medium', timeStyle:'short'});
let busy = false;

export function articleComments(state) {
  return `<details class="article-comments" data-article-comments="${e(state.articleSlug)}"><summary>Обсуждение</summary><div data-comment-public></div><button type="button" class="link-button" data-comments-more hidden>Показать ещё</button><div data-comment-own></div>${state.user ? `<form data-comment-form><label for="article-comment-body">Твой комментарий</label><textarea id="article-comment-body" name="body" required minlength="2" maxlength="2000" rows="4"></textarea><p class="form-caption">Комментарий появится после проверки организатором. Не указывай личные контакты.</p><button type="submit" class="button secondary">Отправить на проверку ${icon('message')}</button></form>` : '<button type="button" class="text-link" data-action="comment-login">Войти и оставить комментарий</button>'}<p data-comment-status role="status"></p></details>`;
}

export function commentModerationView() {
  return `${heading('Комментарии', 'Проверь текст перед публикацией в обсуждении статьи.')}<section data-comment-moderation><div class="comment-filter"><label for="comment-filter">Показывать</label><select id="comment-filter" data-comment-filter><option value="pending">На проверке</option><option value="approved">Опубликованные</option><option value="rejected">Отклонённые</option></select></div><div data-comment-queue></div><p data-comment-moderation-status role="status"></p><div class="comment-pagination"><button type="button" class="link-button" data-comment-page="previous" disabled>Назад</button><span data-comment-page-label></span><button type="button" class="link-button" data-comment-page="next" disabled>Далее</button></div></section>`;
}

async function loadDiscussion(details, append = false) {
  const status = details.querySelector('[data-comment-status]');
  const offset = append ? Number(details.dataset.offset || 0) : 0;
  const generation = Number(details.dataset.generation || 0) + 1;
  details.dataset.generation = generation;
  status.textContent = 'Загружаем комментарии…';
  try {
    const slug = encodeURIComponent(details.dataset.articleComments);
    const [page, own] = await Promise.all([
      request(`/articles/${slug}/comments?offset=${offset}&limit=20`, {auth:false}),
      getSession()?.user ? request(`/articles/${slug}/comments/mine`) : [],
    ]);
    if (!details.isConnected || Number(details.dataset.generation) !== generation) return;
    const ids = new Set(own.map(row => row.id));
    const list = details.querySelector('[data-comment-public]');
    const rows = page.items.map(row => `<article class="comment-row"><header><strong>${ids.has(row.id) ? 'Ты' : e(row.author)}</strong><time>${date(row.created_at)}</time></header><p>${e(row.body)}</p>${ids.has(row.id) ? `<button type="button" class="link-button" data-comment-remove="${e(row.id)}">Удалить</button>` : ''}</article>`).join('');
    if (!append) list.innerHTML = rows || '<p class="form-caption">Опубликованных комментариев пока нет.</p>';
    else list.insertAdjacentHTML('beforeend', rows);
    details.dataset.offset = offset + page.items.length;
    details.querySelector('[data-comments-more]').hidden = offset + page.items.length >= page.total;
    details.querySelector('[data-comment-own]').innerHTML = own.filter(row => row.status !== 'approved').map(row => `<article class="comment-row own-comment"><header><strong>${statuses[row.status]}</strong><time>${date(row.created_at)}</time></header><p>${e(row.body)}</p>${row.reason ? `<p class="form-caption">${e(row.reason)}</p>` : ''}<button type="button" class="link-button" data-comment-remove="${e(row.id)}">Удалить</button></article>`).join('');
    status.textContent = '';
    details.dataset.loaded = 'true';
  } catch (error) { if (details.isConnected) status.textContent = error.message; }
}

export async function loadCommentModeration() {
  const panel = document.querySelector('[data-comment-moderation]');
  if (!panel) return;
  const generation = Number(panel.dataset.generation || 0) + 1;
  panel.dataset.generation = generation;
  const offset = Number(panel.dataset.offset || 0);
  const status = panel.querySelector('[data-comment-moderation-status]');
  status.textContent = 'Загружаем очередь…';
  try {
    const filter = panel.querySelector('[data-comment-filter]').value;
    const page = await request(`/admin/comments?status=${filter}&offset=${offset}&limit=20`);
    if (!panel.isConnected || Number(panel.dataset.generation) !== generation) return;
    panel.querySelector('[data-comment-queue]').innerHTML = page.items.length ? page.items.map(row => `<article class="comment-row moderation-row" data-comment-id="${e(row.id)}"><header><strong>${e(row.author_name)}</strong><time>${date(row.created_at)}</time></header><a class="text-link" href="/materials/${e(row.article_slug)}" data-article="${e(row.article_slug)}">Открыть статью ${icon('arrow')}</a><p>${e(row.body)}</p>${row.reason ? `<p class="form-caption">${e(row.reason)}</p>` : ''}<div class="form-actions">${row.status !== 'approved' ? `<button type="button" class="button secondary small" data-comment-decision="approved">Опубликовать</button>` : ''}${row.status !== 'rejected' ? '<button type="button" class="link-button" data-comment-decision="rejected">Отклонить</button>' : ''}</div></article>`).join('') : '<p class="console-empty">Комментариев в этой категории нет.</p>';
    panel.querySelector('[data-comment-page-label]').textContent = page.total ? `${offset + 1}–${offset + page.items.length} из ${page.total}` : '0 комментариев';
    panel.querySelector('[data-comment-page=previous]').disabled = offset === 0;
    panel.querySelector('[data-comment-page=next]').disabled = offset + page.items.length >= page.total;
    status.textContent = '';
  } catch (error) { if (panel.isConnected) status.textContent = error.message; }
}

export function hasCommentDraft() {
  return busy || Boolean(document.querySelector('[data-comment-form] textarea')?.value.trim());
}

export function installComments(ui) {
  document.addEventListener('toggle', event => {
    const details = event.target;
    if (details.matches('[data-article-comments]') && details.open && !details.dataset.loaded) void loadDiscussion(details);
  }, true);
  document.addEventListener('change', event => {
    if (!event.target.matches('[data-comment-filter]')) return;
    event.target.closest('[data-comment-moderation]').dataset.offset = 0;
    void loadCommentModeration();
  });
  async function moderate(id, status, reason = '') {
    if (busy) return;
    busy = true;
    try {
      await request(`/admin/comments/${id}`, {method:'PATCH', body:{status, reason}});
      await loadCommentModeration();
      ui.toast(status === 'approved' ? 'Комментарий опубликован.' : 'Комментарий отклонён.');
    } finally { busy = false; }
  }
  document.addEventListener('click', async event => {
    const target = event.target.closest('button');
    if (!target || target.disabled || busy) return;
    try {
      if (target.matches('[data-comments-more]')) { target.disabled = true; await loadDiscussion(target.closest('details'), true); }
      if (target.dataset.commentRemove) {
        if (!confirm('Удалить свой комментарий?')) return;
        busy = true;target.disabled = true;
        await request(`/article-comments/${target.dataset.commentRemove}`, {method:'DELETE'});
        await loadDiscussion(target.closest('details'));
      }
      if (target.dataset.commentPage) {
        const panel = target.closest('[data-comment-moderation]');
        panel.dataset.offset = Math.max(0, Number(panel.dataset.offset || 0) + (target.dataset.commentPage === 'next' ? 20 : -20));
        await loadCommentModeration();
      }
      if (target.dataset.commentDecision) {
        const id = target.closest('[data-comment-id]').dataset.commentId;
        if (target.dataset.commentDecision === 'approved') { target.disabled = true; await moderate(id, 'approved'); }
        else ui.modal('Отклонить комментарий', `<form data-comment-rejection="${e(id)}"><label for="comment-reason">Причина для автора</label><textarea id="comment-reason" name="reason" rows="3" maxlength="500" required></textarea><p class="form-message" role="alert"></p><button type="submit" class="button secondary">Отклонить комментарий</button></form>`);
      }
    } catch (error) { ui.toast(error.message); }
    finally { busy = false; if (target.isConnected) target.disabled = false; }
  });
  document.addEventListener('submit', async event => {
    const form = event.target;
    if (!form.matches('[data-comment-form],[data-comment-rejection]')) return;
    event.preventDefault();
    if (busy || !form.reportValidity()) return;
    const button = form.querySelector('[type=submit]');button.disabled = true;
    try {
      if (form.matches('[data-comment-rejection]')) {
        await moderate(form.dataset.commentRejection, 'rejected', form.elements.reason.value.trim());
        document.querySelector('#dialog').close();
      } else {
        busy = true;
        const details = form.closest('details');
        await request(`/articles/${encodeURIComponent(details.dataset.articleComments)}/comments`, {method:'POST', body:{body:form.elements.body.value.trim()}});
        form.reset();await loadDiscussion(details);ui.toast('Комментарий отправлен на проверку.');
      }
    } catch (error) { form.querySelector('.form-message') ? form.querySelector('.form-message').textContent = error.message : ui.toast(error.message); }
    finally { busy = false; if (button.isConnected) button.disabled = false; }
  });
}
