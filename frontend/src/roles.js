import { request } from './api.js';
import { escapeHtml as e, button, icon } from './ui.js';

const workspaceRoles = new Set(['admin', 'commission', 'expert', 'teacher']);
const analystRoles = new Set(['admin', 'commission']);
const roleRoutes = new Set(['workspace', 'review-project', 'rankings']);
const pageSize = 100;

function initialWork() {
  return {
    projects: [], assignments: [], students: [], experts: [], criteria: [], reviews: [], defenses: [],
    stats: null, project: null, assignment: null, hasMore: false, moreStudents: false,
    query: '', status: '', notice: '', reviewDraft: null,
    ranking: { items: [], total: 0 }, rankingOffset: 0, rankingNomination: '',
  };
}

export function createWorkspace(state, ui) {
  state.work = initialWork();
  let busy = false;
  let dirty = false;
  let confirmation = null;
  let previewUrl;
  const isWorkspace = () => workspaceRoles.has(state.user?.role);
  const isAdmin = () => state.user?.role === 'admin';
  const draftKey = () => `arctic-review-draft:${state.user.id}:${state.work.assignment.id}`;

  async function loadList(append = false) {
    const w = state.work;
    if (state.user.role === 'expert') {
      const rows = await request(`/expert/assignments?offset=${append ? w.assignments.length : 0}&limit=${pageSize}`);
      w.assignments = append ? [...w.assignments, ...rows] : rows;
      w.hasMore = rows.length === pageSize;
    } else {
      const rows = await request(`/projects?offset=${append ? w.projects.length : 0}&limit=${pageSize}`);
      w.projects = append ? [...w.projects, ...rows] : rows;
      w.hasMore = rows.length === pageSize;
    }
  }

  async function loadStudents(append = false) {
    const w = state.work;
    const students = await request(`/teachers/students?offset=${append ? w.students.length : 0}&limit=100`);
    w.students = append ? [...w.students, ...students] : students;
    w.moreStudents = students.length === 100;
  }

  async function loadExperts() {
    const experts = [];
    let total;
    do {
      const page = await request(`/admin/users?role=expert&is_active=true&limit=200&offset=${experts.length}`);
      experts.push(...page.items); total = page.total;
      if (!page.items.length) break;
    } while (experts.length < total);
    const directions=await request('/admin/expert-directions');
    const eligible=new Set(directions.filter(d=>d.nomination_id===state.work.project?.nomination_id).map(d=>d.expert_id));
    state.work.experts = experts.filter(expert=>eligible.has(expert.id));
  }

  async function ownAssignment(projectId) {
    let match;
    let offset = 0;
    while (true) {
      const rows = await request(`/expert/assignments?offset=${offset}&limit=200`);
      match = rows.find(row => row.project_id === projectId);
      if (match) return match;
      if (rows.length < 200) return null;
      offset += rows.length;
    }
  }

  function readDraft() {
    const w = state.work;
    if (!w.assignment || w.assignment.review_submitted) { w.reviewDraft = null; return; }
    try { w.reviewDraft = JSON.parse(sessionStorage.getItem(draftKey()) || 'null'); }
    catch { w.reviewDraft = null; }
    w.reviewDraft ||= { scores: {}, comment: '' };
    dirty = false;
  }

  async function loadDetail(projectId) {
    if (!projectId) throw new Error('Открой работу из своего рабочего кабинета.');
    const w = state.work;
    const [project, reviews, criteria, defenses] = await Promise.all([
      request(`/projects/${projectId}`), request(`/projects/${projectId}/reviews`),
      state.user.role === 'expert' ? request('/criteria', { auth: false }) : [],
      state.user.role !== 'commission' ? request('/defenses') : [],
    ]);
    w.project = project; w.reviews = reviews; w.criteria = criteria; w.defenses = defenses;
    w.assignment = state.user.role === 'expert' ? await ownAssignment(projectId) : null;
    if (state.user.role === 'expert' && !w.assignment) throw new Error('Эта работа не назначена тебе. Вернись к списку назначений.');
    if (isAdmin() && ['admitted', 'reviewing'].includes(project.status)) await loadExperts();
    if (state.user.role === 'expert') readDraft();
  }

  async function loadRanking() {
    const w = state.work;
    const query = new URLSearchParams({ limit: '20', offset: String(w.rankingOffset) });
    if (w.rankingNomination) query.set('nomination_id', w.rankingNomination);
    w.ranking = await request(`/admin/rankings?${query}`);
  }

  async function load(route, id) {
    if (!isWorkspace()) throw new Error('Этот рабочий кабинет доступен другой роли.');
    if (route === 'workspace') {
      await Promise.all([
        loadList(),
        analystRoles.has(state.user.role) ? request('/admin/stats').then(stats => state.work.stats = stats) : null,
        state.user.role === 'teacher' ? loadStudents() : null,
      ]);
    }
    if (route === 'review-project') await loadDetail(id || state.work.project?.id);
    if (route === 'rankings') {
      if (!analystRoles.has(state.user.role)) throw new Error('Рейтинг доступен организатору и комиссии.');
      await loadRanking();
    }
  }

  function roleFormMessage(form, message) {
    const target = form?.querySelector('.role-form-message');
    if (target && form.isConnected) target.innerHTML = `<div class="notice error-notice" role="alert"><p>${e(message)}</p></div>`;
    else ui.toast(message);
  }

  async function run(action, form) {
    if (busy) return;
    busy = true;
    const controls = form ? [...form.querySelectorAll('button,input,select,textarea')] : [];
    const disabled = controls.map(control => control.disabled);
    controls.forEach(control => control.disabled = true);
    form?.setAttribute('aria-busy', 'true');
    try { await action(); }
    catch (error) { roleFormMessage(form, error.message); }
    finally {
      busy = false; controls.forEach((control,i) => control.disabled = disabled[i]);
      form?.removeAttribute('aria-busy');
    }
  }

  async function reloadAfter(message) {
    const id = state.work.project.id;
    state.work.notice = message;
    // Назначения и статусы перечитываются после подтверждения операции сервером.
    if (state.user.role === 'expert') await loadList();
    await loadDetail(id);
    ui.render(); updatePreview(); ui.toast(message);
  }

  function captureReviewDraft(save = false) {
    const form = document.querySelector('#expert-review-form');
    if (!form) return;
    const data = new FormData(form);
    const scores = {};
    for (const criterion of state.work.criteria) {
      const raw = String(data.get(`score:${criterion.id}`) ?? '');
      if (raw.trim() !== '') scores[criterion.id] = Number(raw);
    }
    const draft = { scores, comment: String(data.get('comment') || ''), savedAt: save ? new Date().toISOString() : state.work.reviewDraft?.savedAt };
    state.work.reviewDraft = draft;
    if (save) {
      sessionStorage.setItem(draftKey(), JSON.stringify(draft));
      dirty = false;
      const label = document.querySelector('#review-draft-state');
      if (label) label.textContent = `Черновик сохранён в этой вкладке ${new Date(draft.savedAt).toLocaleTimeString('ru-RU')}. Организатор его не видит.`;
    }
    return draft;
  }

  function updatePreview() {
    const output = document.querySelector('#weighted-preview');
    if (!output) return;
    const draft = captureReviewDraft();
    const criteria = state.work.criteria;
    if (!criteria.length || criteria.some(c => !Number.isFinite(draft.scores[c.id]) || draft.scores[c.id] < 0 || draft.scores[c.id] > c.max_score)) { output.textContent = '—'; return; }
    const maxWeight = Math.max(...criteria.map(c => c.weight));
    const weighted = 100 * criteria.reduce((sum,c) => sum + draft.scores[c.id] / c.max_score * (c.weight / maxWeight), 0) / criteria.reduce((sum,c) => sum + c.weight / maxWeight, 0);
    output.textContent = weighted.toLocaleString('ru-RU', { maximumFractionDigits: 2 });
  }

  function confirm(kind, payload, title, explanation) {
    confirmation = { kind, payload, projectId: state.work.project.id, assignmentId: state.work.assignment?.id };
    ui.modal(title, `<p><strong>${e(state.work.project.title)}</strong></p><p>${e(explanation)}</p><div class="dialog-actions">${button(kind === 'review' ? 'Отправить рецензию' : kind === 'publish' ? 'Опубликовать' : 'Подтвердить решение', 'data-role-action="confirm"', '', 'check')}</div>`);
  }

  async function commitConfirmation() {
    const pending = confirmation;
    if (!pending || busy) return;
    await run(async () => {
      document.querySelector('#dialog').close();
      if (pending.kind === 'moderate') {
        await request(`/admin/projects/${pending.projectId}/moderate`, { method: 'POST', body: pending.payload });
        await reloadAfter(pending.payload.status === 'admitted' ? 'Работа допущена к конкурсу.' : 'Работа возвращена участнику с комментарием.');
      }
      if (pending.kind === 'publish') {
        await request(`/admin/projects/${pending.projectId}/publish`, { method: 'POST' });
        await reloadAfter('Результаты опубликованы для участника и наставника.');
      }
      if (pending.kind === 'review') {
        await request(`/expert/assignments/${pending.assignmentId}/review`, { method: 'POST', body: pending.payload });
        sessionStorage.removeItem(draftKey()); dirty = false;
        await reloadAfter('Твоя рецензия принята и сохранена на сервере.');
      }
      confirmation = null;
    });
  }

  async function handleClick(target) {
    if (target.dataset.roleProject) {
      await ui.navigate('review-project', { id: target.dataset.roleProject }); return true;
    }
    if (target.dataset.rolePreview) {
      const project = state.work.project;
      const file = project?.files.find(row => row.id === target.dataset.rolePreview);
      if (!file) throw new Error('Файл не найден. Обнови карточку проекта.');
      await run(async () => {
        const blob = await request(`/files/${file.id}/download`, { blob: true });
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        previewUrl = URL.createObjectURL(new Blob([blob], { type:'application/pdf' }));
        ui.modal(file.original_name, `<iframe class="pdf-preview" title="${e(file.original_name)}" src="${previewUrl}"></iframe><p class="form-caption">Если просмотр недоступен, скачай документ.</p><button class="button secondary small" data-file="${e(file.id)}" data-filename="${e(file.original_name)}">Скачать PDF ${icon('file')}</button>`);
      }); return true;
    }
    const name = target.dataset.roleAction;
    if (!name) return false;
    if (name === 'confirm') { await commitConfirmation(); return true; }
    if (name === 'confirm-publish') {
      if (!isAdmin()) throw new Error('Публикация доступна организатору.');
      confirm('publish', null, 'Опубликовать результаты?', 'Участник и связанный наставник увидят оценки и комментарии экспертов.'); return true;
    }
    if (name === 'save-review-draft') {
      captureReviewDraft(true); ui.toast('Черновик рецензии сохранён в этой вкладке.'); return true;
    }
    if (name === 'refresh') {
      if (!canLeave()) return true;
      state.work.notice = '';
      await ui.navigate(state.route, { id: state.work.project?.id }); return true;
    }
    await run(async () => {
      if (name === 'more-projects') await loadList(true);
      if (name === 'more-students') await loadStudents(true);
      if (name === 'ranking-next' || name === 'ranking-previous') {
        const next = Math.max(0, state.work.rankingOffset + (name === 'ranking-next' ? 20 : -20));
        if (next >= state.work.ranking.total && next !== 0) return;
        state.work.rankingOffset = next; await loadRanking();
      }
      ui.render();
    });
    return true;
  }

  async function handleSubmit(form) {
    const recognized = ['work-filter-form', 'ranking-filter-form', 'moderation-form', 'assignment-form', 'auto-assignment-form', 'expert-review-form', 'defense-form'];
    if (!recognized.includes(form.id)) return false;
    if (!form.reportValidity() || busy) return true;
    const data = new FormData(form);
    const w = state.work;
    if (form.id === 'work-filter-form') { w.query = String(data.get('query') || ''); w.status = String(data.get('status') || ''); ui.render(); return true; }
    if (form.id === 'ranking-filter-form') { w.rankingNomination = String(data.get('nomination_id') || ''); w.rankingOffset = 0; await run(async () => { await loadRanking(); ui.render(); }, form); return true; }
    if (form.id === 'expert-review-form') {
      if (state.user.role !== 'expert' || !w.assignment || w.assignment.review_submitted) { roleFormMessage(form, 'Эту рецензию уже нельзя редактировать. Обнови страницу.'); return true; }
      const draft = captureReviewDraft(true);
      if (draft.comment.trim().length < 10) { roleFormMessage(form, 'Добавь комментарий не короче 10 символов.'); return true; }
      confirm('review', { scores: draft.scores, comment: draft.comment.trim() }, 'Отправить окончательную рецензию?', 'После отправки оценки и комментарий нельзя изменить. Предварительный итог будет проверен сервером.'); return true;
    }
    if (!isAdmin()) { roleFormMessage(form, 'Это действие доступно только организатору.'); return true; }
    if (form.id === 'moderation-form') {
      const payload = { status: data.get('status'), comment: String(data.get('comment') || '').trim() };
      if (payload.status === 'rejected' && payload.comment.length < 5) { roleFormMessage(form, 'Объясни причину возврата: не меньше 5 символов.'); return true; }
      confirm('moderate', payload, payload.status === 'admitted' ? 'Допустить работу к конкурсу?' : 'Вернуть работу на доработку?', payload.comment || 'Работа перейдёт к этапу назначения экспертов.'); return true;
    }
    await run(async () => {
      if (form.id === 'assignment-form') {
        const expert_ids = data.getAll('expert_ids');
        if (!expert_ids.length) throw new Error('Выбери хотя бы одного эксперта.');
        const result = await request(`/admin/projects/${w.project.id}/assign`, { method:'POST', body:{ expert_ids } });
        await reloadAfter(result.assigned ? `Добавлено назначений: ${result.assigned}.` : 'Выбранные эксперты уже были назначены.');
      }
      if (form.id === 'auto-assignment-form') {
        const result = await request('/admin/projects/auto-assign', { method:'POST', body:{ count:Number(data.get('count')), project_ids:[w.project.id] } });
        await reloadAfter(result.assigned ? `Автоматически добавлено назначений: ${result.assigned}.` : 'Нужное число экспертов уже назначено.');
      }
      if (form.id === 'defense-form') {
        const starts = new Date(String(data.get('starts_at')));
        if (!Number.isFinite(starts.valueOf())) throw new Error('Укажи корректную дату и время защиты.');
        await request('/admin/defenses', { method:'POST', body:{ project_id:w.project.id, starts_at:starts.toISOString(), join_url:data.get('join_url'), description:String(data.get('description') || '') } });
        await reloadAfter('Защита назначена. Участник увидит дату и ссылку в своём кабинете.');
      }
    }, form);
    return true;
  }

  function handleInput(event) {
    if (event.target.closest('#expert-review-form')) {
      dirty = true; updatePreview();
      const label = document.querySelector('#review-draft-state');
      if (label) label.textContent = 'Есть несохранённые изменения. Сохрани черновик перед выходом.';
    }
  }

  function canLeave() {
    if (busy) { ui.toast('Подожди, завершаем действие.'); return false; }
    if (dirty && !window.confirm('Черновик рецензии изменён. Уйти без сохранения последних изменений?')) return false;
    dirty = false; return true;
  }

  return {
    isRoute: route => roleRoutes.has(route),
    defaultRoute: () => ['admin','commission'].includes(state.user?.role) ? 'overview' : isWorkspace() ? 'workspace' : 'dashboard',
    routeAllowed: route => !roleRoutes.has(route) || isWorkspace() && (route !== 'rankings' || analystRoles.has(state.user.role)),
    load, handleClick, handleSubmit, handleInput, canLeave, afterRender: updatePreview,
    get busy() { return busy; }, get dirty() { return dirty; },
    menu() { return `<nav class="menu-links"><a href="#home" data-route="home">Главная</a><a href="#workspace" data-route="workspace">${state.user?.role === 'expert' ? 'Мои назначения' : state.user?.role === 'teacher' ? 'Мои участники и работы' : 'Работы конкурса'}</a>${analystRoles.has(state.user?.role) ? '<a href="#rankings" data-route="rankings">Результаты конкурса</a>' : ''}<a href="#library" data-anchor="library">Открывай Север</a><button class="link-button" data-action="logout">Выйти из аккаунта</button></nav>`; },
    help() {
      const messages = {
        expert: 'Открой назначенную работу, изучи материалы и оцени все критерии. Черновик сохраняется в этой вкладке. После окончательной отправки рецензию нельзя изменить; тогда становятся доступны оценки коллег.',
        admin: 'Проверь поданную работу, допусти её к конкурсу или верни с комментарием. Назначь экспертов. Когда все рецензии получены, опубликуй результаты для участника. Дату и ссылку защиты можно назначить в карточке допущенной работы.',
        commission: 'Просматривай работы, поступившие рецензии и рейтинг завершённой экспертизы. Решения о допуске, назначениях и публикации принимает организатор.',
        teacher: 'Здесь видны участники с подтверждённой связью и их работы. Ты можешь открыть материалы, посмотреть опубликованные рецензии и расписание защиты.',
      };
      return `<p>${messages[state.user?.role] || ''}</p>`;
    },
    reset() { state.work = initialWork(); dirty = false; confirmation = null; if (previewUrl) URL.revokeObjectURL(previewUrl); previewUrl = null; },
  };
}
