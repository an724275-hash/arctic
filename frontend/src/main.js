import {installComments, loadCommentModeration, hasCommentDraft} from './comments.js';
import {createQuizClock} from './quiz-clock.js';
import {installRegistrationTeacher, requireRegistrationTeacher} from './registration-teacher.js';
import {installInteractionMotion} from './interactions.js';
import {mobileMenu} from './mobile-menu.js';
import {testEntry} from './test-entry.js';
import {installPresence, syncPresence} from './presence.js';
import {installContact, hasContactDraft} from './contact.js';
import {installAssistant, syncAssistant} from './assistant.js';
import './styles.css';
import './app.css';
import './roles.css';
import './release.css';
import { toggleSound, playCue } from './sound.js';
import { request, download, getSession, setSession } from './api.js';
import { escapeHtml as e, icon, button, act } from './ui.js';
import { views, header, footer, mobileNavigation, errorBox, timerText } from './views.js';
import { roleViews } from './role-views.js';
import { createWorkspace } from './roles.js';
import { readRoute, routeUrl, pageTitles } from './routes.js';
import { publicViews, articles } from './public-views.js';
import {consoleViews,consoleRoutes,createConsole,consoleFrame} from './console.js';
import {profileView,createProfile} from './profile.js';
import {updateCities,selectCity,cityKeys} from './geography.js';
import {awardsView,newsView} from './product-views.js';
import {preparationView} from './preparation.js';
import {polishPage,installNavigationPolish} from './ux.js';
import {mentorView,createMentor} from './mentor.js';
import './layout.css';
import './refinements.css';

const routeViews = { ...views, ...roleViews, ...publicViews, ...consoleViews, testing:testEntry,profile:profileView,awards:awardsView,news:newsView,preparation:preparationView,'teacher-invite':mentorView };

const app = document.querySelector('#app');
const dialog = document.querySelector('#dialog');
const state = {
  route: 'home', user: getSession()?.user || null, config: null, nominations: [], content: [],
  attempts: [], projects: [], certificates: [], attempt: null, answers: {}, question: 0, deadline: 0,
  project: null, file: null, materials: {}, projectReviews: [], defenses: [], article: null, articleSlug: '', saving: false, answerError: '', loading: false, error: '', publicError: '',
};
const protectedRoutes = new Set(['testing','dashboard', 'quiz', 'quiz-confirm', 'result', 'project', 'submitted', 'workspace', 'review-project', 'rankings']);
consoleRoutes.forEach(route=>protectedRoutes.add(route));
protectedRoutes.add('profile');
protectedRoutes.add('awards');
let navigation = 0;
let pendingRoute = 'dashboard';
let toastTimer;
let answerSave = Promise.resolve();
let answerRevision = 0;
let answerEpoch = 0;
let finishPending = false;
let formBusy = false;
let timerFailureAt = -Infinity;
let draftDirty = false;
let activeUrl = `${location.pathname}${location.search}${location.hash}`;
let activeHistoryIndex = Number.isInteger(history.state?.arcticIndex) ? history.state.arcticIndex : 0;
let restoringHistory = false;
let animatedPage = '';
const workspace = createWorkspace(state, { render, navigate, toast, modal });
const control = createConsole(state,{render,toast,modal,reloadPublic:loadPublic});
const profile = createProfile(state,{render,toast});
const mentor=createMentor(state);

function routeHash(route, id) {
  if (['project', 'submitted'].includes(route)) id ||= state.project?.id;
  if (['quiz', 'quiz-confirm', 'result'].includes(route)) id ||= state.attempt?.id;
  if (route === 'review-project') id ||= state.work.project?.id;
  if (route === 'article') id ||= state.articleSlug;
  return id && ['project','submitted','quiz','quiz-confirm','result','review-project','article'].includes(route) ? `${route}/${encodeURIComponent(id)}` : route;
}

function writeRoute(route, mode = 'replace') {
  const url = routeUrl(route, location.search);
  const current = `${location.pathname}${location.search}${location.hash}`;
  const push = mode === 'push' && url !== current;
  const currentIndex = Number.isInteger(history.state?.arcticIndex) ? history.state.arcticIndex : activeHistoryIndex;
  activeHistoryIndex = push ? currentIndex + 1 : currentIndex;
  history[push ? 'pushState' : 'replaceState']({ arcticIndex: activeHistoryIndex }, '', url);
  activeUrl = url;
}

function render(scroll = false) {
  const page = state.loading ? '<section class="panel loading-panel" role="status"><span class="loader"></span><h1>Загружаем страницу…</h1></section>' : state.error ? errorBox(state.error) : routeViews[state.route](state);
  const body = ['workspace','review-project','rankings',...consoleRoutes].includes(state.route) ? consoleFrame(state,page) : page;
  const pageKey = `${state.route}/${state.articleSlug || ''}/${state.attempt?.id || ''}`;
  const enter = !state.loading && pageKey !== animatedPage;
  if (!state.loading) animatedPage = pageKey;
  app.innerHTML = `<div class="shell"><div class="site-topbar">${header(state)}${mobileNavigation(state)}</div><main id="content"${enter ? ' class="scene-enter"' : ''}>${body}</main>${footer(state)}</div>`;
  document.title = `${state.route === 'article' && state.article ? state.article.title : pageTitles[state.route] || 'Арктика'} | Арктика`;
  app.querySelectorAll('a[data-route]').forEach(link => { link.href = routeUrl(link.dataset.route); });
  if (scroll) window.scrollTo({ top: 0, behavior: 'instant' });
  workspace.afterRender();
  profile.afterRender();
  polishPage(state);
  updateSeo();
  syncAssistant(state.route);
  syncPresence();
  if(state.route==='comment-moderation'&&!state.loading&&!state.error)void loadCommentModeration();
  // при прокрутке
  revealSections();
}
function updateSeo(){
  const meta=(name,value,property=false)=>{let node=document.head.querySelector(`meta[${property?'property':'name'}="${name}"]`);if(!node){node=document.createElement('meta');node.setAttribute(property?'property':'name',name);document.head.append(node);}node.content=value;};
  const description=state.route==='article'&&state.article?(state.article.intro||state.article.excerpt||state.article.body||'').slice(0,280):'Конкурс «Удивительная и неизведанная Арктика»: образовательные материалы, тестирование, исследовательские проекты и сертификаты.';
  meta('description',description);meta('robots',protectedRoutes.has(state.route)||['login','register','forgot-password','reset-password','verify-email','teacher-invite','not-found'].includes(state.route)?'noindex, noarchive':'index, follow');meta('og:title',document.title,true);meta('og:description',description,true);
  let canonical=document.head.querySelector('link[rel=canonical]');if(!canonical){canonical=document.createElement('link');canonical.rel='canonical';document.head.append(canonical);}canonical.href=location.origin+location.pathname;
  const old=document.querySelector('#article-schema');old?.remove();
  if(state.route==='article'&&state.article){const script=document.createElement('script');script.type='application/ld+json';script.id='article-schema';script.textContent=JSON.stringify({'@context':'https://schema.org','@type':'Article',headline:state.article.title,description,mainEntityOfPage:canonical.href,author:{'@type':'Organization',name:'asa team'},image:location.origin+(state.article.image||'/assets/arctic-coast.webp')});document.head.append(script);}
}
let revealObserver;
let revealedPage = '';
const revealedSections = new Set();
function revealSections() {
  revealObserver?.disconnect();
  const page = `${state.route}/${state.articleSlug || ''}`;
  if (page !== revealedPage) { revealedSections.clear(); revealedPage = page; }
  if (!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  revealObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealedSections.add(entry.target.dataset.revealIndex);
        revealObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.08 });
  app.querySelectorAll('.discovery-editorial, .journey-section, .home-materials, .public-section').forEach((section, index) => {
    section.dataset.revealIndex = String(index);
    section.classList.add('reveal-section');
    if (revealedSections.has(String(index))) section.classList.add('is-visible');
    else revealObserver.observe(section);
    section.addEventListener('focusin', () => {
      section.classList.add('is-visible');
      revealedSections.add(String(index));
      revealObserver.unobserve(section);
    }, { once: true });
  });
}
async function printCertificate(id) {
  const blob = await request(`/certificates/${id}/download`, { blob: true });
  const url = URL.createObjectURL(blob);
  modal('Сертификат для печати', `<p class="form-caption">Документ в формате A4, альбомная ориентация. В окне PDF выбери значок принтера или нажми Ctrl+P, когда документ открыт.</p><iframe class="certificate-preview" title="Сертификат PDF" src="${url}"></iframe><div class="certificate-actions"><a class="button secondary small" href="${url}" target="_blank" rel="noopener">Открыть PDF для печати</a><a class="button light small" href="${url}" download="Арктика — сертификат.pdf">Скачать PDF</a></div>`);
  dialog.classList.add('certificate-dialog');
  dialog.addEventListener('close', () => { dialog.classList.remove('certificate-dialog'); URL.revokeObjectURL(url); }, { once: true });
}
function toast(message) {
  const el = document.querySelector('#toast'); el.textContent = message; el.classList.add('visible');
  clearTimeout(toastTimer); toastTimer = setTimeout(() => el.classList.remove('visible'), 5000);
}
function modal(title, body) {
  if (dialog.open) dialog.close();
  dialog.innerHTML = `<h2 id="dialog-title">${e(title)}</h2>${body}<div class="dialog-actions">${button('Понятно', act('close'), 'secondary', 'check')}</div>`;
  dialog.showModal();
}
function currentFormMessage(message, success = false) {
  const el = document.querySelector('.form-message');
  if (el) { el.innerHTML = `<div class="notice ${success ? 'success-notice' : 'error-notice'}"><p>${e(message)}</p></div>`; el.scrollIntoView({ block: 'nearest' }); }
  else toast(message);
}
async function loadPublic() {
  const results = await Promise.allSettled([
    request('/quiz/config', { auth: false }), request('/nominations', { auth: false }), request('/content?limit=100', { auth: false }), request('/stages',{auth:false}),
    request('/capabilities',{auth:false}), request('/criteria',{auth:false}),
  ]);
  ['config', 'nominations', 'content','stages','capabilities','criteria'].forEach((key,i) => { if (results[i].status === 'fulfilled') state[key] = results[i].value; });
  state.publicError = results.some(r => r.status === 'rejected') ? 'Часть материалов пока недоступна. Попробуй обновить страницу позже.' : '';
}
async function loadDashboard() {
  if(state.user.role==='partner'){
    const notifications=await request('/notifications?unread_only=true&limit=100');
    state.unreadNotifications=notifications.length;await profile.photo();return;
  }
  const participant = state.user.role === 'participant';
  const [projects, attempts, certificates, defenses,notifications] = await Promise.all([
    request('/projects'), participant ? request('/quiz/attempts') : [], request('/certificates'), participant ? request('/defenses') : [], request('/notifications?unread_only=true&limit=100'),
  ]);
  state.projects = projects; state.attempts = attempts; state.certificates = certificates; state.defenses = defenses;
  state.unreadNotifications=notifications.length;
  if(participant)state.mentorConnection=await request('/teachers/link');
  await profile.photo();
}
const quizClock = createQuizClock();
async function requestAttempt(path, options) {
  const started = performance.now();
  const attempt = await request(path, options);
  quizClock.sync(attempt, started);
  return attempt;
}
function setAttempt(attempt, resetQuestion = false) {
  state.attempt = attempt;
  state.answers = structuredClone(attempt.answers);
  state.deadline = quizClock.deadline;
  state.answerError = '';
  if (resetQuestion) state.question = 0;
  state.question = Math.min(state.question, attempt.questions.length - 1);
}
function clearLocalAccount() {
  setSession(null);
  state.user = null; state.attempt = null; state.project = null; state.file = null; state.materials = {};
  state.attempts = []; state.projects = []; state.certificates = []; state.projectReviews = []; state.answers = {};
  state.saving = false; state.answerError = ''; draftDirty = false;
  answerEpoch++; answerSave = Promise.resolve();
  workspace.reset(); control.reset(); profile.reset();
}
function storeProjectInput() {
  const form = document.querySelector('#project-form');
  if (!form) return;
  state.project = { ...(state.project || {}), ...Object.fromEntries(new FormData(form)) };
  delete state.project.intent;
}
async function navigate(next, { reload = true, id, force = false, historyMode = 'push' } = {}) {
  const routeParts = next.split('/');
  next = routeParts[0]; id ||= routeParts[1] ? decodeURIComponent(routeParts[1]) : undefined;
  if (next === 'article') id ||= state.articleSlug;
  next = routeViews[next] ? next : 'not-found';
  const stay = () => {
    if (historyMode !== 'none') return;
    const targetIndex = history.state?.arcticIndex;
    // возвращаем историю
    if (Number.isInteger(targetIndex) && targetIndex !== activeHistoryIndex) {
      restoringHistory = true;
      history.go(activeHistoryIndex - targetIndex);
    }
    else history.replaceState({ arcticIndex: activeHistoryIndex }, '', activeUrl);
  };
  if (!force && hasCommentDraft() && !window.confirm('Уйти со страницы? Неотправленный комментарий будет потерян.')) return stay();
  if (!force && hasContactDraft() && !window.confirm('Уйти со страницы? Неотправленное обращение будет потеряно.')) return stay();
  if (!force && !workspace.canLeave()) return stay();
  if (!force && (!control.canLeave() || !profile.canLeave())) return stay();
  if (!force && formBusy) { toast('Подожди, завершаем сохранение.'); return stay(); }
  if (!force && state.saving && !( ['quiz', 'quiz-confirm'].includes(state.route) && ['quiz', 'quiz-confirm'].includes(next))) { toast('Подожди, сохраняем ответ.'); return stay(); }
  if (!force && state.answerError && ['quiz','quiz-confirm'].includes(state.route) && !['quiz','quiz-confirm'].includes(next)) { toast('Сначала сохрани ответ повторно или заверши тест.'); return stay(); }
  if (!force && draftDirty && state.route === 'project' && next !== 'project') {
    storeProjectInput();
    if (!window.confirm('Есть несохранённые изменения проекта. Уйти со страницы?')) return stay();
    draftDirty = false;
  }
  if (dialog.open) dialog.close();
  if (protectedRoutes.has(next) && !state.user) { pendingRoute = routeHash(next, id); next = 'login'; }
  if (['login', 'register', 'dashboard'].includes(next) && state.user) next = workspace.defaultRoute();
  if(state.user?.role==='partner'&&['testing','quiz','quiz-confirm','result','project','submitted','awards'].includes(next))next='dashboard';
  if (state.user && ['admin','commission','expert','teacher'].includes(state.user.role) && ['testing','quiz','quiz-confirm','result','project','submitted'].includes(next)) next = ['project','submitted'].includes(next) && id ? 'review-project' : 'workspace';
  if (state.user && !workspace.routeAllowed(next)) next = workspace.defaultRoute();
  if(state.user && !control.rolesAllowed(next)) next=workspace.defaultRoute();
  const nav = ++navigation;
  state.route = next; state.error = ''; state.loading = (protectedRoutes.has(next) || consoleRoutes.has(next) || next === 'article') && reload;
  if (next === 'article') state.articleSlug = id || '';
  writeRoute(routeHash(next, id), historyMode);
  if (state.loading) render(true);
  try {
    if (reload) {
      if (next === 'article') state.article = articles[id] || await request(`/content/${encodeURIComponent(id)}`, { auth: false });
      if (workspace.isRoute(next)) await workspace.load(next, id);
      if(consoleRoutes.has(next)) await control.load(next);
      if(next==='profile') await profile.load();
      if(next==='teacher-invite'||next==='register'&&state.mentorToken)await mentor.load();
      if(next==='awards') await loadDashboard();
      if (next === 'testing') {
        state.attempts = await request('/quiz/attempts');
        const active = state.attempts.find(attempt => attempt.status === 'active');
        if (active) { await navigate('quiz', {id: active.id, force: true}); return; }
      }
      if (next === 'dashboard') await loadDashboard();
      if (next === 'quiz' || next === 'quiz-confirm' || next === 'result') {
        let attemptId = id || state.attempt?.id;
        if (!attemptId) {
          state.attempts = await request('/quiz/attempts');
          attemptId = state.attempts[0]?.id;
        }
        if (!attemptId) { await navigate('dashboard', { force: true }); return; }
        setAttempt(await requestAttempt(`/quiz/attempts/${attemptId}`), Boolean(id));
        state.route = state.attempt.status !== 'active' ? 'result' : next === 'result' ? 'quiz' : next;
      }
      if (next === 'project' || next === 'submitted') {
        if(next==='project'&&!id&&!state.project?.id){
          state.attempts=await request('/quiz/attempts');
          if(!state.attempts.some(a=>a.passed===true)){toast('Второй этап откроется после проходного результата теста.');await navigate('dashboard',{force:true});return;}
        }
        if (id || state.project?.id) state.project = await request(`/projects/${id || state.project.id}`);
        else if (next === 'submitted') { await navigate('dashboard', { force: true }); return; }
        if (state.project?.id) {
          const [reviews, defenses] = await Promise.all([request(`/projects/${state.project.id}/reviews`), request('/defenses')]);
          state.projectReviews = reviews; state.defenses = defenses;
        }
      }
    }
    if (nav !== navigation) return;
    state.loading = false; writeRoute(routeHash(state.route)); render(true);
    document.querySelector('#content h1')?.focus({ preventScroll: true });
  } catch (error) {
    if (nav !== navigation || error.status === 401) return;
    state.error = error.message; state.loading = false; render();
  }
}
async function startQuiz() {
  if (!state.user) return navigate('login');
  state.loading = true; state.error = ''; render();
  try {
    setAttempt(await requestAttempt('/quiz/attempts', { method: 'POST' }), true);
    await navigate(state.attempt.status === 'active' ? 'quiz' : 'result', { reload: false, force: true });
  } catch (error) { state.loading = false; render(); toast(error.message); }
}

function saveAnswers() {
  answerRevision++;
  if (state.saving) return answerSave;
  state.saving = true; state.answerError = '';
  updateAnswerFeedback();
  const attemptId = state.attempt.id;
  const epoch = answerEpoch;
  // очередь ответов
  answerSave = answerSave.catch(() => {}).then(async () => {
    if (epoch !== answerEpoch) return;
    try {
      let revision;
      do {
        revision = answerRevision;
        const payload = structuredClone(state.answers);
        const attempt = await requestAttempt(`/quiz/attempts/${attemptId}/answers`, { method: 'PATCH', body: { answers: payload } });
        if (state.attempt?.id !== attemptId) return;
        state.attempt = attempt;
        state.deadline = quizClock.deadline;
        if (attempt.status !== 'active') {
          setAttempt(attempt); state.route = 'result'; render(); return;
        }
      } while (revision !== answerRevision);
    } catch (error) { if (epoch === answerEpoch) state.answerError = error.message; }
    finally { if (epoch === answerEpoch) { state.saving = false; updateAnswerFeedback(); } }
  });
  return answerSave;
}
function updateAnswerFeedback() {
  const label = document.querySelector('.save-state');
  if (label) label.textContent = state.saving ? 'Сохраняем ответ…' : state.answerError ? 'Ответ пока не сохранён' : 'Сохранено';
  document.querySelectorAll('[data-action="finish"]').forEach(button => { button.disabled = state.saving; });
  const next = document.querySelector('[data-action="next"]');
  if (next) next.disabled = Boolean(state.answerError);
  const retry = document.querySelector('[data-action="retry-answer"]');
  if (retry) retry.hidden = !state.answerError;
  const error = document.querySelector('[data-answer-error]');
  if (error) { error.hidden = !state.answerError; error.querySelector('p').textContent = state.answerError; }
}
async function chooseAnswer(option) {
  if (finishPending || !state.attempt || state.attempt.status !== 'active') return;
  const question = state.attempt.questions[state.question];
  const selected = state.answers[question.id] || [];
  state.answers[question.id] = question.multiple_choice ? selected.includes(option) ? selected.filter(id => id !== option) : [...selected, option] : [option];
  document.querySelectorAll('[data-answer]').forEach(button => {
    const checked = state.answers[question.id].includes(button.dataset.answer);
    button.classList.toggle('selected', checked);
    button.setAttribute('aria-checked', String(checked));
    button.tabIndex = question.multiple_choice || checked ? 0 : -1;
    button.querySelector('.answer-radio').innerHTML = checked ? icon('check') : '';
  });
  const answered = state.attempt.questions.filter(q => state.answers[q.id]?.length).length;
  document.querySelector('.question-progress').textContent = `Отвечено ${answered} из ${state.attempt.questions.length}`;
  const mapButton = document.querySelector(`[data-question="${state.question}"]`);
  mapButton.classList.toggle('answered', state.answers[question.id].length > 0);
  mapButton.setAttribute('aria-label', `Вопрос ${state.question + 1}${state.answers[question.id].length ? ', ответ выбран' : ''}`);
  void saveAnswers();
}
async function finishQuiz(expired = false) {
  if (finishPending || !state.attempt) return;
  finishPending = true;
  await answerSave;
  state.loading = true; render();
  try {
    setAttempt(await requestAttempt(`/quiz/attempts/${state.attempt.id}/submit`, { method: 'POST', body: { answers: state.answers } }));
    await navigate('result', { reload: false, force: true });
    playCue('complete');
    if (expired) toast('Время закончилось. Сохранённые ответы учтены.');
  } catch (error) { state.loading = false; timerFailureAt = performance.now(); render(); toast(error.message); }
  finally { finishPending = false; }
}
async function saveProject(form, submit = false) {
  if (!form.reportValidity() || formBusy) return;
  storeProjectInput();
  if (submit && !state.file && !state.project.files?.some(f => f.kind === 'document')) { currentFormMessage('Добавь основной документ PDF или DOCX перед отправкой.'); return; }
  await withForm(form, async () => {
    const payload = { title: state.project.title.trim(), abstract: state.project.abstract.trim(), nomination_id: state.project.nomination_id, video_url: state.project.video_url?.trim() || null };
    const id = state.project.id;
    const saved = await request(id ? `/projects/${id}` : '/projects', { method: id ? 'PATCH' : 'POST', body: payload });
    state.project = { ...state.project, ...saved };
    writeRoute(routeHash('project', saved.id));
    draftDirty = Boolean(state.file || Object.values(state.materials).some(Boolean));
    if (state.file) {
      const data = new FormData(); data.append('file', state.file); data.append('kind', 'document');
      await request(`/projects/${saved.id}/files`, { method: 'POST', body: data });
      state.file = null;
    }
    for (const [kind, file] of Object.entries(state.materials)) {
      if (!file) continue;
      const data = new FormData(); data.append('file', file); data.append('kind', kind);
      await request(`/projects/${saved.id}/files`, { method: 'POST', body: data });
      state.materials[kind] = null;
    }
    draftDirty = false;
    if (submit) await request(`/projects/${saved.id}/submit`, { method: 'POST' });
    state.project = await request(`/projects/${saved.id}`);
    await navigate(submit ? 'submitted' : 'project', { reload: false, force: true });
    if (submit) playCue('submitted');
    toast(submit ? 'Проект отправлен на проверку.' : 'Черновик и материалы сохранены.');
  });
}
async function withForm(form, action) {
  if (formBusy) return;
  formBusy = true;
  const controls = [...form.querySelectorAll('button, input, textarea, select')];
  const disabled = controls.map(el => el.disabled);
  controls.forEach(el => el.disabled = true); form.setAttribute('aria-busy', 'true');
  const message = form.querySelector('.form-message'); if (message) message.innerHTML = '<p class="saving-label" role="status">Сохраняем…</p>';
  try { await action(); }
  catch (error) { if (error.status !== 401 || !getSession()) currentFormMessage(error.message); }
  finally { formBusy = false; controls.forEach((el,i) => el.disabled = disabled[i]); form.removeAttribute('aria-busy'); }
}
async function authenticate(form, registration) {
  if (registration && !requireRegistrationTeacher(form)) return;
  if (!form.reportValidity() || formBusy) return;
  const data = Object.fromEntries(new FormData(form));
  let payload = { email: data.email, password: data.password };
  if (registration) payload = {
    ...payload, full_name: data.full_name, birth_date: data.birth_date, role: 'participant',
    grade: data.grade ? Number(data.grade) : null, school: data.school || null, region: data.region || null,city:data.city||null,
    guardian_name: data.guardian_name || null, guardian_email: data.guardian_email || null,
    guardian_consent: data.guardian_consent === 'on', consent: data.consent === 'on',
    teacher_id: data.teacher_id || null, mentor_token: data.mentor_token || null, teacher_consent: data.teacher_consent === 'on',
  };
  let authenticated = false;
  await withForm(form, async () => {
    const session = await request(`/auth/${registration ? 'register' : 'login'}`, { method: 'POST', body: payload, auth: false });
    setSession(session); state.user = session.user;
    await loadPublic();
    authenticated = true;
  });
  if (!authenticated) return;
  if (registration) mentor.clear();
  await navigate(state.mentorToken?'teacher-invite':pendingRoute, { force: true });
  pendingRoute = 'dashboard';
  if (registration) {
    playCue('welcome');
    toast('Аккаунт создан. Добро пожаловать в экспедицию!');
  }
}

function reviewAnswers() {
  modal('Твои ответы', `<div class="answer-review">${state.attempt.questions.map((q,i) => `<div><strong>${q.is_correct ? '✓' : '—'} ${i+1}. ${e(q.text)}</strong><p>Твой ответ: ${q.options.filter(o => q.selected_option_ids.includes(o.id)).map(o => e(o.text)).join(', ') || 'не выбран'}<br>Верный ответ: ${q.options.filter(o => q.correct_option_ids.includes(o.id)).map(o => e(o.text)).join(', ')}</p>${q.explanation ? `<p>${e(q.explanation)}</p>` : ''}</div>`).join('')}</div>`);
}
async function action(name) {
  switch (name) {
    case 'create-mentor-link': {
      const reply=await request('/teachers/invite-link',{method:'POST'});
      modal('Личная ссылка ученику',`<p>Одноразовая ссылка действует три дня. Передай её одному ученику. Он войдёт или зарегистрируется и сам подтвердит привязку.</p><div class="form-field"><label for="mentor-share">Ссылка приглашения</label><input id="mentor-share" readonly value="${e(reply.url)}"></div><button type="button" class="button secondary" data-action="copy-mentor-link">Скопировать ссылку ${icon('file')}</button>`);break;
    }
    case 'copy-mentor-link': {
      const input=document.querySelector('#mentor-share');
      try{await navigator.clipboard.writeText(input.value);toast('Ссылка скопирована.');}catch{input.select();toast('Выделил ссылку — скопируй её вручную.');}break;
    }
    case 'cancel-mentor':mentor.clear();return navigate('dashboard');
    case 'start': return startQuiz();
    case 'next':
      if (state.answerError) return;
      if (state.question === state.attempt.questions.length - 1) return navigate('quiz-confirm', { reload: false });
      state.question++; render(true); break;
    case 'previous': state.question = Math.max(0, state.question-1); render(true); break;
    case 'retry-answer': return saveAnswers();
    case 'finish': return finishQuiz();
    case 'review': reviewAnswers(); break;
    case 'new-project':
      state.attempts=await request('/quiz/attempts');
      if(!state.attempts.some(a=>a.passed===true)){toast('Сначала пройди тест с проходным результатом.');return navigate('dashboard');}
      state.project = null; state.projectReviews = []; state.file = null; state.materials = {}; draftDirty = false; return navigate('project', { reload: false });
    case 'refresh-project': return navigate('project');
    case 'reopen': await request(`/projects/${state.project.id}/reopen`, { method: 'POST' }); return navigate('project');
    case 'retry': await loadPublic(); return navigate(state.route);
    case 'resend-email': {
      const reply = await request('/auth/resend-verification', { method: 'POST' }); toast(reply.message); break;
    }
    case 'verify-email': {
      const token = new URLSearchParams(location.search).get('token');
      if (!token) throw new Error('В ссылке нет кода подтверждения. Открой ссылку из письма заново.');
      const reply = await request('/auth/verify-email', { method: 'POST', body: { token }, auth: false });
      if (state.user) { state.user = await request('/users/me'); setSession({ ...getSession(), user: state.user }); }
      await navigate(state.user ? 'dashboard' : 'login', { force: true }); toast(reply.message); break;
    }
    case 'logout': {
      let confirmed = false;
      try { await request('/auth/logout', { method: 'POST' }); confirmed = true; }
      catch { /* очищаем эту вкладку */ }
      clearLocalAccount();
      await navigate('home', { force: true });
      if (!confirmed) toast('Вы вышли из этой вкладки. Сервер не подтвердил завершение остальных сессий.');
      return;
    }
    case 'menu':
      if (dialog.open) dialog.close();
      dialog.classList.add('menu-dialog');
      dialog.innerHTML = mobileMenu(state);
      dialog.addEventListener('close', () => dialog.classList.remove('menu-dialog'), { once: true });
      dialog.showModal();
      break;
    case 'sound-toggle': await toggleSound(); break;
    case 'vk-login': modal('Вход через VK ID', '<p>Подключение VK ID ещё не настроено. Войти через ВКонтакте сейчас нельзя.</p><p>Используй электронную почту и пароль или зарегистрируй аккаунт. Результаты и сертификаты сохранятся в твоём кабинете.</p>'); break;
    case 'comment-login': pendingRoute=routeHash('article',state.articleSlug);return navigate('login');
    case 'rules': return navigate('rules');
    case 'help': return navigate('help');
    case 'close': dialog.close(); break;
  }
}

document.addEventListener('click', async event => {
  const target = event.target.closest('button,a');
  if (!target || target.disabled) return;
  if (target.tagName === 'A' && (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button !== 0)) return;
  if (target.matches('a[data-route],a[data-anchor],a[data-article]')) event.preventDefault();
  try {
    if(target.dataset.readingSection){event.preventDefault();document.getElementById(target.dataset.readingSection)?.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'});return;}
    if(target.dataset.city){selectCity(target);return;}
    if(await control.click(target))return;
    if (await workspace.handleClick(target)) { event.preventDefault(); return; }
    if (target.dataset.route) { event.preventDefault(); await navigate(target.dataset.route, { reload: !['quiz', 'quiz-confirm'].includes(target.dataset.route) }); return; }
    if (target.dataset.anchor) { event.preventDefault(); await navigate(({ about: 'about', route: 'participation', library: 'materials' })[target.dataset.anchor] || 'home'); return; }
    if (target.dataset.article || target.dataset.content) { event.preventDefault(); await navigate('article', { id: target.dataset.article || target.dataset.content }); return; }
    if (target.dataset.answer !== undefined) { await chooseAnswer(target.dataset.answer); return; }
    if (target.dataset.question !== undefined) { state.question = Number(target.dataset.question); render(true); return; }
    if (target.dataset.project) { state.file = null; state.materials = {}; draftDirty = false; await navigate('project', { id: target.dataset.project }); return; }
    if (target.dataset.result) { await navigate('result', { id: target.dataset.result }); return; }
    if (target.dataset.printCertificate) { target.disabled = true; try { await printCertificate(target.dataset.printCertificate); } finally { target.disabled = false; } return; }
    if (target.dataset.certificate) { target.disabled = true; await download(`/certificates/${target.dataset.certificate}/download`, 'Арктика — сертификат.pdf'); target.disabled = false; return; }
    if (target.dataset.file) { await download(`/files/${target.dataset.file}/download`, target.dataset.filename); return; }
    if (target.dataset.removeFile) {
      storeProjectInput();
      if (!window.confirm('Удалить этот файл из проекта?')) return;
      await request(`/projects/${state.project.id}/files/${target.dataset.removeFile}`, { method: 'DELETE' });
      state.project.files = state.project.files.filter(file => file.id !== target.dataset.removeFile); render(); return;
    }
    if (target.dataset.action) { event.preventDefault(); await action(target.dataset.action); }
  } catch (error) { target.disabled = false; toast(error.message); }
});
document.addEventListener('submit', async event => {
  const form = event.target;
  if (form.matches('[data-mentor-join]')) {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const replace = new FormData(form).get('replace') === 'on';
    await withForm(form, async () => {
      await request('/teachers/join', {method: 'POST', body: {token: state.mentorToken, replace}});
      mentor.clear();
      await navigate('dashboard', {force: true});
      toast('Наставник привязан.');
    });
    return;
  }
  if(form.dataset.consoleForm){event.preventDefault();try{await control.submit(form);}catch(error){toast(error.message);}return;}
  if(form.dataset.profileForm){event.preventDefault();await profile.submit(form);return;}
  if (['work-filter-form','ranking-filter-form','moderation-form','assignment-form','auto-assignment-form','expert-review-form','defense-form'].includes(form.id)) {
    event.preventDefault();
    try { await workspace.handleSubmit(form); } catch (error) { toast(error.message); }
    return;
  }
  if (!['login-form', 'register-form', 'project-form', 'forgot-form', 'reset-form'].includes(form.id)) return;
  event.preventDefault();
  if (form.id === 'login-form' || form.id === 'register-form') return authenticate(form, form.id === 'register-form');
  if (form.id === 'project-form') return saveProject(form, event.submitter?.value === 'submit');
  const data = Object.fromEntries(new FormData(form));
  await withForm(form, async () => {
    if (form.id === 'forgot-form') {
      const reply = await request('/auth/forgot-password', { method: 'POST', body: { email: data.email }, auth: false });
      currentFormMessage(reply.message, true);
    } else {
      const token = new URLSearchParams(location.search).get('token');
      if (!token) throw new Error('Открой ссылку восстановления из письма.');
      const reply = await request('/auth/reset-password', { method: 'POST', body: { password: data.password, token }, auth: false });
      await navigate('login', { force: true }); toast(reply.message);
    }
  });
});
document.addEventListener('input', event => {
  workspace.handleInput(event);
  control.input(event);profile.input(event);
  if(event.target.id==='city')updateCities(event.target);
  if(event.target.matches('[data-library-search]')){
    const query=event.target.value.trim().toLocaleLowerCase('ru-RU');
    const rows=[...document.querySelectorAll('.education-catalog>a')];
    rows.forEach(row=>row.hidden=!row.textContent.toLocaleLowerCase('ru-RU').includes(query));
    document.querySelector('[data-library-empty]').hidden=rows.some(row=>!row.hidden);
  }
  if (event.target.matches('[data-faq-search]')) {
    const query = event.target.value.trim().toLocaleLowerCase('ru-RU');
    const questions = [...document.querySelectorAll('.help-questions details')];
    questions.forEach(question => { question.hidden = !question.textContent.toLocaleLowerCase('ru-RU').includes(query); });
    document.querySelector('.faq-empty').hidden = questions.some(question => !question.hidden);
  }
  if (event.target.closest('#project-form') && event.target.type !== 'file') { draftDirty = true; storeProjectInput(); }
  if (event.target.name === 'birth_date') {
    const birth = new Date(`${event.target.value}T12:00:00`); const today = new Date();
    let age = today.getFullYear()-birth.getFullYear();
    if (today.getMonth() < birth.getMonth() || today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate()) age--;
    const fields = document.querySelector('#guardian-fields'); fields.hidden = !Number.isFinite(age) || age >= 18; fields.disabled = fields.hidden;
  }
});
document.addEventListener('change', event => {
  if(event.target.id==='profile-photo')profile.preview(event.target);
  if(event.target.id==='region'){const city=document.querySelector('#city');if(city?.value)updateCities(city);}
  if(event.target.dataset.messageStatus){void control.change(event.target);return;}
  control.input(event);profile.input(event);
  if (!event.target.matches('[data-upload-kind]')) return;
  const file = event.target.files[0]; if (!file) return;
  const kind = event.target.dataset.uploadKind;
  const formats = { document: /\.(pdf|docx)$/i, presentation: /\.(pdf|pptx)$/i, video: /\.(mp4|webm)$/i };
  if (!formats[kind].test(file.name) || file.size > 30*1024*1024 || !file.size) { event.target.value = ''; currentFormMessage('Выбери непустой файл подходящего формата размером до 30 МБ.'); return; }
  if (kind === 'document') state.file = file; else state.materials[kind] = file;
  draftDirty = true;
  const upload = event.target.closest('.upload');
  upload.querySelector('h3').textContent = file.name;
  upload.querySelector('p').textContent = 'Готов к загрузке при сохранении';
  upload.classList.add('attached');
});
document.addEventListener('keydown', event => {
  cityKeys(event);
  if (event.target.matches('[role="radio"]') && ['ArrowDown','ArrowUp','ArrowLeft','ArrowRight'].includes(event.key)) {
    event.preventDefault(); const radios = [...document.querySelectorAll('[role="radio"]')];
    const direction = ['ArrowDown','ArrowRight'].includes(event.key) ? 1 : -1;
    radios[(radios.indexOf(event.target)+direction+radios.length)%radios.length].click();
  }
});
window.addEventListener('session-expired', () => {
  clearLocalAccount();
  if (protectedRoutes.has(state.route)) { pendingRoute = 'dashboard'; void navigate('login', { force: true }); toast('Сессия закончилась. Войди снова, чтобы продолжить.'); }
});
function followHistory() {
  const url = `${location.pathname}${location.search}${location.hash}`;
  if (restoringHistory) {
    if (url === activeUrl) restoringHistory = false;
    return;
  }
  if (location.hash === '#content') return;
  if (url !== activeUrl) void navigate(readRoute(location), { historyMode: 'none' });
}
window.addEventListener('popstate', followHistory);
window.addEventListener('hashchange', followHistory);
window.addEventListener('beforeunload', event => { if (hasCommentDraft() || hasContactDraft() || draftDirty || state.saving || state.answerError || workspace.dirty || workspace.busy || control.dirty || control.busy || profile.dirty || profile.busy) { event.preventDefault(); event.returnValue = ''; } });
document.addEventListener('visibilitychange', async () => {
  if (document.hidden || state.saving || finishPending || state.loading || state.attempt?.status !== 'active' || !['quiz','quiz-confirm'].includes(state.route)) return;
  const id = state.attempt.id;
  try {
    const attempt = await requestAttempt(`/quiz/attempts/${id}`);
    if (state.attempt?.id !== id || !['quiz','quiz-confirm'].includes(state.route)) return;
    state.deadline = quizClock.deadline;
    if (attempt.status !== 'active') {
      setAttempt(attempt);
      await navigate('result', {reload:false,force:true});
    }
  } catch { /* повторим при сохранении */ }
});
setInterval(() => {
  if (!state.attempt || state.attempt.status !== 'active' || !['quiz','quiz-confirm'].includes(state.route) || state.loading) return;
  const timer = document.querySelector('#timer'); if (timer) timer.textContent = timerText(state);
  if (performance.now() >= state.deadline && performance.now()-timerFailureAt > 15000) void finishQuiz(true);
}, 1000);

async function boot() {
  state.loading = true;
  render();
  await loadPublic();
  if (state.user) {
    try { state.user = await request('/users/me'); setSession({ ...getSession(), user: state.user }); }
    catch (error) { if (error.status !== 401) state.publicError = error.message; }
  }
  await navigate(readRoute(location), { force: true, historyMode: 'replace' });
}
installComments({modal,toast});
installRegistrationTeacher();
installInteractionMotion();
installNavigationPolish();
installAssistant(() => state.route);
installContact();
installPresence();
void boot();


