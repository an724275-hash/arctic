import {cmsView} from './cms.js';
import {request,download} from './api.js';
import {escapeHtml as e,icon,heading} from './ui.js';
import './console.css';
import {expertSettings} from './expert-settings.js';
import {testingSettings} from './testing-settings.js';

export const consoleRoutes = new Set(['content-editor','overview','contest-settings','people','expert-directions','communications','notifications']);
const labels = {participant:'Участник',teacher:'Наставник',expert:'Эксперт',admin:'Организатор',commission:'Комиссия',partner:'Партнёр'};
const statuses = {draft:'Черновик',submitted:'Проверка',admitted:'Допущен',rejected:'Исправления',reviewing:'Экспертиза',evaluated:'Оценён'};
const nav = [['overview','compass','Обзор'],['workspace','folder','Проекты'],['content-editor','book','Контент'],['people','user','Участники'],['expert-directions','user','Эксперты'],['contest-settings','shield','Конкурс'],['communications','book','Обращения и уведомления'],['rankings','check','Результаты']];
const link = (route,label,symbol='arrow')=>`<a href="/#${route}" data-route="${route}">${icon(symbol)}<span>${e(label)}</span></a>`;
const date = value=>value ? new Date(value).toLocaleString('ru-RU',{dateStyle:'medium',timeStyle:'short'}) : 'Срок не указан';
const num = value=>Number(value || 0).toLocaleString('ru-RU');
const blank = text=>`<p class="console-empty">${e(text)}</p>`;
export function consoleFrame(s,body) {
  if (!['admin','commission'].includes(s.user?.role)) return body;
  return `<div class="console-layout"><aside class="console-sidebar"><p>Управление конкурсом</p><nav aria-label="Разделы организатора">${nav.filter(([r])=>s.user.role==='admin'||['overview','workspace','rankings'].includes(r)).map(([r,i,t])=>`<a href="/#${r}" data-route="${r}" ${s.route===r || r==='workspace'&&s.route==='review-project' ? 'aria-current="page"' : ''}>${icon(i)}<span>${t}</span></a>`).join('')}</nav><div class="console-identity"><strong>${e(s.user.full_name)}</strong><span>${labels[s.user.role]}</span>${link('home','Открыть сайт','home')}</div></aside><div class="console-content">${body}</div></div>`;
}
function bars(rows, total, labelMap={}) {
  const max=Math.max(1,...rows.map(r=>r.count));
  return rows.length ? `<div class="data-bars">${rows.map(row=>`<div class="data-bar"><div><span>${e(labelMap[row.label]||row.label)}</span><strong>${num(row.count)}${total ? `<small> · ${Math.round(row.count/total*100)}%</small>` : ''}</strong></div><div class="data-track"><span style="width:${row.count/max*100}%"></span></div></div>`).join('')}</div>` : blank('Пока нет данных. Диаграмма появится после регистрации участников или подачи работ.');
}
function signupChart(rows) {
  if (!rows.length) return blank('За последние 30 дней регистраций не было.');
  const max=Math.max(1,...rows.map(row=>row.count));
  const points=rows.map((row,i)=>`${40+(rows.length===1?260:i/(rows.length-1)*520)},${174-row.count/max*135}`);
  return `<svg class="signup-chart" viewBox="0 0 600 220" role="img" aria-label="Количество регистраций по дням"><path d="M40 39H560M40 107H560M40 174H560" stroke="#D6E2E8" fill="none"/><path d="M${points.join(' L')}" fill="none" stroke="#345F73" stroke-width="3" stroke-linejoin="round"/>${rows.map((r,i)=>`<circle cx="${points[i].split(',')[0]}" cy="${points[i].split(',')[1]}" r="5" fill="#345F73"><title>${e(r.label)}: ${r.count}</title></circle>`).join('')}<text x="40" y="209">${e(rows[0].label)}</text><text x="560" y="209" text-anchor="end">${e(rows.at(-1).label)}</text></svg><details class="chart-table"><summary>Данные по дням</summary><table><thead><tr><th>Дата</th><th>Регистрации</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${e(r.label)}</td><td>${num(r.count)}</td></tr>`).join('')}</tbody></table></details>`;
}
function overview(s) {
  const d=s.console.stats;
  return `${heading('Обзор конкурса','Участники, работы и результаты конкурса.')}<div class="console-page-actions"><span>Обновлено ${date(s.console.updated)}</span><button class="button secondary small" data-console="refresh">Обновить данные</button></div><dl class="console-metrics">${[['participants_total','Участников'],['projects_total','Проектов'],['reviews_total','Рецензий'],['certificates_total','Сертификатов']].map(([key,label])=>`<div><dt>${label}</dt><dd>${num(d[key])}</dd></div>`).join('')}</dl><div class="console-charts"><section class="panel"><h2>География участников</h2><p class="chart-caption">Регионы, указанные в профилях активных участников.</p>${bars(d.regions,d.participants_total)}</section><section class="panel"><h2>Работы по номинациям</h2><p class="chart-caption">Включает сохранённые черновики и отправленные работы.</p>${bars(d.nominations,d.projects_total)}</section><section class="panel"><h2>Регистрации за 30 дней</h2><p class="chart-caption">Все роли. Наведи на точку или открой таблицу.</p>${signupChart(d.signups_daily)}</section><section class="panel"><h2>Этапы проверки работ</h2>${bars(d.project_statuses,d.projects_total,statuses)}<div class="console-export"><button class="button secondary small" data-console="export-projects">Проекты CSV</button><button class="button secondary small" data-console="export-users">Участники CSV</button><button class="button secondary small" data-console="export-reviews">Оценки экспертов CSV</button><button class="button secondary small" data-console="export-analytics">Вся аналитика JSON</button></div><p class="form-caption">Экспорт содержит персональные данные. Передавай его только уполномоченным организаторам.</p></section></div>`;
}
function field(name,label,value='',type='text',extra='') {
  return `<div class="form-field"><label for="setting-${name}">${label}</label><input id="setting-${name}" name="${name}" type="${type}" value="${e(value)}" ${extra}></div>`;
}
const localDate=value=>value ? new Date(new Date(value).getTime()-new Date(value).getTimezoneOffset()*60000).toISOString().slice(0,16) : '';
function settings(s) {
  const c=s.console,tab=c.tab;
  if(tab==='testing')return testingSettings(s);
  const rows=c[tab], item=rows.find(r=>r.id===c.selected) || {};
  const tabs=[['stages','Этапы'],['testing','Тест'],['nominations','Номинации'],['criteria','Критерии оценки']];
  const form=tab==='stages' ? `${field('slug','Код этапа',item.slug||'','text',`required pattern="[a-z0-9_-]+" maxlength="80" ${item.id?'readonly':''}`)}${field('title','Название',item.title||'','text','required minlength="2" maxlength="200"')}<div class="field-grid">${field('starts_at','Начало',localDate(item.starts_at),'datetime-local')}${field('ends_at','Окончание',localDate(item.ends_at),'datetime-local')}</div>${field('position','Порядок',item.position||0,'number','required min="0" max="1000"')}<p class="form-caption">Время вводится в часовом поясе этого устройства. Пустые даты не ограничивают этап.</p>` : `${field(tab==='criteria'?'name':'title','Название',item.name||item.title||'','text','required minlength="2" maxlength="200"')}<div class="form-field"><label for="setting-description">Описание</label><textarea id="setting-description" name="description" maxlength="10000" rows="5">${e(item.description||'')}</textarea></div>${tab==='criteria'?`<div class="field-grid">${field('max_score','Максимальный балл',item.max_score??10,'number','required min="0.01" max="1000" step="any"')}${field('weight','Вес критерия',item.weight??1,'number','required min="0.01" max="1000" step="any"')}</div><p class="form-caption">Взвешенный итог учитывает долю баллов каждого критерия и его вес. Изменение критериев ограничено сервером, если они уже используются в рецензиях.</p>`:''}`;
  return `${heading('Настройки конкурса','Управляй этапами, направлениями работ и шкалой экспертизы. Изменения сохраняются на сервере и фиксируются в журнале действий.')}<div class="console-tabs" role="tablist" aria-label="Настройки">${tabs.map(([id,title])=>`<button role="tab" aria-selected="${tab===id}" data-console="tab" data-tab="${id}">${title}</button>`).join('')}</div><div class="settings-grid"><section class="panel settings-list"><div class="panel-heading"><h2>${tabs.find(([id])=>id===tab)[1]}</h2><button class="link-button" data-console="new">Добавить</button></div>${rows.length?rows.map(row=>`<button class="settings-row ${row.id===c.selected?'active':''}" data-console="select" data-id="${e(row.id)}"><span class="setting-dot">${icon(row.id===c.selected?'check':'compass')}</span><span><strong>${e(row.title||row.name)}</strong><small>${tab==='stages'?`${row.is_enabled?'Включён':'Отключён'} · ${date(row.starts_at)}`:row.is_active?'Доступен':'Неактивен'}</small></span>${icon('arrow')}</button>`).join(''):blank('Записей пока нет. Создай первую через форму справа.')}</section><section class="panel"><h2>${item.id?'Редактирование':'Новая запись'}</h2><form data-console-form="settings" class="project-form">${form}<label class="check-field"><input type="checkbox" name="enabled" ${tab==='stages'?item.is_enabled!==false?'checked':'':item.is_active!==false?'checked':''}><span>${tab==='stages'?'Этап включён':'Запись активна'}</span></label><div class="form-message" role="alert"></div><button class="button" type="submit">Сохранить изменения ${icon('check')}</button></form></section></div>`;
}
function people(s) {
  const c=s.console;
  return `${heading('Участники и команда конкурса','Поиск работает по ФИО и почте. Данные доступны только организатору; роль и состояние аккаунта отображаются из базы.')}<section class="panel"><form data-console-form="people" class="console-filter"><div class="form-field"><label for="people-search">Имя или электронная почта</label><input id="people-search" name="q" type="search" maxlength="200" value="${e(c.query)}" placeholder="Найти участника"></div><div class="form-field"><label for="people-role">Роль</label><select id="people-role" name="role"><option value="">Все роли</option>${Object.entries(labels).map(([id,label])=>`<option value="${id}" ${c.role===id?'selected':''}>${label}</option>`).join('')}</select></div><button class="button secondary" type="submit">Найти</button></form><div class="console-table-wrap"><table class="console-table"><thead><tr><th>Участник</th><th>Роль</th><th>Учебное заведение</th><th>Регион и город</th><th>Аккаунт</th></tr></thead><tbody>${c.people.items.map(user=>`<tr><td><strong>${e(user.full_name)}</strong><small>${e(user.email)}</small></td><td>${labels[user.role]||e(user.role)}</td><td>${e(user.school||'Не указано')}${user.grade?`<small>${user.grade} класс</small>`:''}</td><td>${e(user.region||'Не указан')}<small>${e(user.city||'')}</small></td><td>${user.is_active?'Активен':'Отключён'}<small>${user.email_verified?'Почта подтверждена':'Почта не подтверждена'}</small></td></tr>`).join('')}</tbody></table></div>${!c.people.items.length?blank('По этому запросу ничего не найдено. Измени имя или роль.'):''}<div class="console-pagination"><span>Найдено ${num(c.people.total)} · ${c.offset+1}–${c.offset+c.people.items.length}</span><button class="link-button" data-console="people-back" ${c.offset?'':'disabled'}>Назад</button><button class="link-button" data-console="people-next" ${c.offset+c.people.items.length<c.people.total?'':'disabled'}>Далее</button></div></section>`;
}
function communications(s) {
  const c=s.console;
  return `${heading('Обращения и уведомления','Отвечай на запросы и информируй участников внутри кабинета. SMTP и VK пока не подключены; этот экран не отправляет письма или сообщения в соцсети.')}<div class="console-charts"><section class="panel"><h2>Обращения с сайта</h2><p class="chart-caption">Последние ${c.messages.items.length} из ${c.messages.total} обращений.</p>${c.messages.items.length?c.messages.items.map(message=>`<details class="contact-message"><summary>${e(message.name)}<span>${date(message.created_at)}</span></summary><p>${e(message.message)}</p><p>${e(message.email)}</p><label>Статус <select data-message-status="${e(message.id)}">${[['new','Новое'],['in_progress','В работе'],['resolved','Решено'],['closed','Закрыто']].map(([id,title])=>`<option value="${id}" ${id===message.status?'selected':''}>${title}</option>`).join('')}</select></label></details>`).join(''):blank('Обращений пока нет. Новые запросы появятся здесь после отправки формы обратной связи.')}</section><section class="panel"><h2>Новое уведомление</h2><form data-console-form="announcement" class="project-form">${field('title','Заголовок','','text','required minlength="2" maxlength="250"')}<div class="form-field"><label for="announcement-role">Аудитория</label><select id="announcement-role" name="role">${Object.entries(labels).map(([id,label])=>`<option value="${id}">${label}</option>`).join('')}</select></div><div class="form-field"><label for="announcement-body">Текст сообщения</label><textarea id="announcement-body" name="body" required minlength="2" maxlength="10000" rows="5"></textarea></div><section class="announcement-preview" aria-label="Предпросмотр уведомления"><span>${icon('info')}В кабинете участника</span><h3 data-preview-title>Заголовок уведомления</h3><p data-preview-body>Текст появится здесь по мере ввода.</p></section><div class="form-message" role="alert"></div><button class="button" type="submit">Проверить и отправить ${icon('arrow')}</button><p class="form-caption">Перед отправкой будет запрошено подтверждение аудитории.</p></form></section></div>`;
}
function notifications(s) {
  const rows=s.console.notifications;
  return `${heading('Уведомления','Сообщения организатора и события участия. Здесь нет рекламной рассылки или сообщений из внешних сервисов.')}<div class="console-page-actions">${link('dashboard','Вернуться в кабинет','back')}<button class="button secondary small" data-console="read-all">Отметить прочитанными</button></div><section class="panel">${rows.length?rows.map(item=>`<article class="notification-item ${item.read_at?'':'unread'}"><div><h2>${e(item.title)}</h2><time>${date(item.created_at)}</time><p>${e(item.body)}</p></div>${!item.read_at?`<button class="link-button" data-console="read" data-id="${e(item.id)}">Прочитано ${icon('check')}</button>`:''}</article>`).join(''):blank('Новых сообщений пока нет. Когда организатор опубликует уведомление, оно появится здесь.')}</section>`;
}
export const consoleViews={'content-editor':cmsView,overview,'contest-settings':settings,people,'expert-directions':expertSettings,communications,notifications};

export function createConsole(s,ui) {
  s.console={cms:{items:[],selected:'',query:'',kind:'',offset:0},stats:null,updated:null,tab:'stages',selected:'',stages:[],nominations:[],criteria:[],people:{items:[],total:0},query:'',role:'',offset:0,messages:{items:[],total:0},notifications:[]};
  let busy=false,dirty=false;
  const c=s.console;
  const rolesAllowed=route=>route==='notifications' ? Boolean(s.user) : route==='overview' ? ['admin','commission'].includes(s.user?.role) : !consoleRoutes.has(route)||s.user?.role==='admin';
  async function load(route) {
    if(!rolesAllowed(route)) throw new Error('Этот раздел доступен только организатору.');
    if(route==='overview') {c.stats=await request('/admin/stats');c.updated=new Date().toISOString();}
    if(route==='contest-settings') { [c.stages,c.nominations,c.criteria,c.quizConfig]=await Promise.all(['/admin/stages','/admin/nominations','/admin/criteria','/admin/quiz-config'].map(url=>request(url)));if(c.tab!=='testing'&&!c[c.tab].some(row=>row.id===c.selected)) c.selected=c[c.tab][0]?.id||''; }
    if(route==='people') c.people=await request(`/admin/users?limit=30&offset=${c.offset}&q=${encodeURIComponent(c.query)}${c.role?'&role='+c.role:''}`);
    if(route==='expert-directions') [c.experts,c.nominations,c.directions]=await Promise.all(['/admin/users?role=expert&limit=200','/admin/nominations','/admin/expert-directions'].map(url=>request(url)));
    if(route==='content-editor'){c.cms.items=await request(`/admin/content?limit=30&offset=${c.cms.offset}&q=${encodeURIComponent(c.cms.query)}${c.cms.kind?'&kind='+c.cms.kind:''}`);}
    if(route==='communications') c.messages=await request('/admin/messages?limit=100');
    if(route==='notifications') c.notifications=await request('/notifications');
  }
  const canLeave=()=>{if(busy)return false;if(dirty&&!window.confirm('Есть несохранённые изменения. Уйти со страницы?'))return false;dirty=false;return true;};
  async function refresh(){await load(s.route);ui.render();}
  async function click(target) {
    if(!target.dataset.console) return false;
    if(busy) return true;
    const action=target.dataset.console;
    if(['tab','new','select'].includes(action)) {
      if(!canLeave()) return true;
      dirty=false;
      if(action==='tab') {c.tab=target.dataset.tab;c.selected=c.tab==='testing'?'':c[c.tab][0]?.id||'';}
      if(action==='select') c.selected=target.dataset.id;
      if(action==='new') c.selected='';
      ui.render();
    }
    if(action==='cms-new'||action==='cms-select'){
      if(!canLeave())return true;
      c.cms.selected=action==='cms-select'?target.dataset.id:'';ui.render();
    }
    if(action==='cms-prev'||action==='cms-next'){
      if(!canLeave())return true;
      c.cms.offset=Math.max(0,c.cms.offset+(action==='cms-next'?30:-30));await refresh();
    }
    if(action==='cms-preview'){
      const form=document.querySelector('[data-console-form=cms]');
      const data=Object.fromEntries(new FormData(form));
      ui.modal('Предпросмотр',`<h3>${e(data.title)}</h3><p>${e(data.excerpt)}</p><div class="cms-preview-text">${e(data.body)}</div>`);
    }
    if(action==='cms-delete'){
      if(!window.confirm('Удалить материал? Он исчезнет с сайта. Несохранённые изменения будут потеряны.'))return true;
      busy=true;target.disabled=true;
      try{await request(`/admin/content/${c.cms.selected}`,{method:'DELETE'});c.cms.selected='';dirty=false;await ui.reloadPublic();await refresh();ui.toast('Материал удалён.');}
      finally{busy=false;target.disabled=false;}
    }
    if(action==='refresh'){if(!canLeave())return true;await refresh();}
    if(action==='export-projects'||action==='export-users') await download(`/admin/export/${action==='export-projects'?'projects':'users'}.csv`,`${action==='export-projects'?'Проекты':'Участники'}.csv`);
    if(action==='export-reviews')await download('/admin/export/reviews.csv','Оценки-экспертов.csv');
    if(action==='export-analytics')await download('/admin/export/analytics.json','Аналитика.json');
    if(action.startsWith('people-')) {c.offset=Math.max(0,c.offset+(action==='people-next'?30:-30));await refresh();}
    if(action==='read-all') {await request('/notifications/read-all',{method:'POST'});await refresh();}
    if(action==='read') {await request(`/notifications/${target.dataset.id}/read`,{method:'PATCH'});await refresh();}
    return true;
  }
  async function submit(form) {
    if(busy||!form.reportValidity())return;
    const data=Object.fromEntries(new FormData(form));
    const type=form.dataset.consoleForm;
    if(type==='cms-filter'){if(!canLeave())return;c.cms.query=data.q;c.cms.kind=data.kind;c.cms.offset=0;await refresh();return;}
    if(type==='people') {c.query=data.q;c.role=data.role;c.offset=0;await refresh();return;}
    if(type==='announcement'&&!window.confirm(`Отправить уведомление всем активным аккаунтам роли «${labels[data.role]}»?`))return;
    busy=true;
    const submit=form.querySelector('[type=submit]');submit.disabled=true;
    const message=form.querySelector('.form-message');message.textContent='Сохраняем…';
    try {
      if(type==='cms'){
        const item=c.cms.items.find(row=>row.id===c.cms.selected);
        const extra={...(item?.extra||{}),caption:data.caption,resource_url:data.resource_url,archive:data.archive==='on',year:data.year?Number(data.year):null};
        if(data.photo)extra.image=data.photo;else delete extra.image;
        const body={kind:data.kind,title:data.title,slug:data.slug,body:data.body,excerpt:data.excerpt,image_url:data.photo.startsWith('https://')?data.photo:null,extra,published:data.published==='on'};
        const result=await request(`/admin/content${item?'/'+item.id:''}`,{method:item?'PUT':'POST',body});
        dirty=false;c.cms.selected=result.id;c.cms.offset=0;c.cms.query='';c.cms.kind='';await ui.reloadPublic();await refresh();ui.toast(result.published?'Материал опубликован.':'Черновик сохранён.');
      }
      if(type==='create-account'){
        await request('/admin/users',{method:'POST',body:{full_name:data.full_name,email:data.email,password:data.password,role:data.role}});
        dirty=false;await refresh();ui.toast('Аккаунт создан. Передайте данные пользователю лично.');
      }
      if(type==='quiz-settings'){
        await request('/admin/quiz-config',{method:'PUT',body:{title:data.title,question_count:Number(data.question_count),duration_seconds:Math.round(Number(data.duration_minutes)*60),pass_percent:Number(data.pass_percent),max_attempts:Number(data.max_attempts),enabled:data.enabled==='on'}});
        dirty=false;await ui.reloadPublic();await refresh();ui.toast('Настройки теста сохранены.');
      }
      if(type==='expert-directions'){
        await request(`/admin/experts/${encodeURIComponent(data.expert_id)}/directions`,{method:'PUT',body:{nomination_ids:new FormData(form).getAll('nomination_id')}});
        dirty=false;await refresh();ui.toast('Направления эксперта сохранены.');
      }
      if(type==='settings') {
        const item=c[c.tab].find(row=>row.id===c.selected);
        const body=c.tab==='stages'?{title:data.title,starts_at:data.starts_at?new Date(data.starts_at).toISOString():null,ends_at:data.ends_at?new Date(data.ends_at).toISOString():null,is_enabled:data.enabled==='on',position:Number(data.position)}:c.tab==='nominations'?{title:data.title,description:data.description,is_active:data.enabled==='on'}:{name:data.name,description:data.description,max_score:Number(data.max_score),weight:Number(data.weight),is_active:data.enabled==='on'};
        const url=c.tab==='stages'?`/admin/stages/${encodeURIComponent(data.slug)}`:`/admin/${c.tab}${item?'/'+item.id:''}`;
        const result=await request(url,{method:c.tab==='stages'||item?'PUT':'POST',body});c.selected=result.id;
        dirty=false;await ui.reloadPublic();await refresh();ui.toast('Изменения сохранены на сервере.');
      }
      if(type==='announcement') {
        const result=await request('/admin/announcements',{method:'POST',body:{title:data.title,body:data.body,roles:[data.role],email:false}});
        dirty=false;form.reset();message.textContent=`Создано уведомлений: ${result.notifications_created}.`;ui.toast('Уведомление опубликовано в кабинетах.');
      }
    } catch(error){message.textContent=error.message;}
    finally{busy=false;submit.disabled=false;}
  }
  function input(event) {
    if(event.target.id==='cms-kind')document.querySelector('.cms-media-fields').hidden=event.target.value!=='media';
    const form=event.target.closest('[data-console-form]');
    if(form&&!['people','cms-filter'].includes(form.dataset.consoleForm)) dirty=true;
    if(form?.dataset.consoleForm==='announcement') {
      document.querySelector('[data-preview-title]').textContent=form.elements.title.value||'Заголовок уведомления';
      document.querySelector('[data-preview-body]').textContent=form.elements.body.value||'Текст появится здесь по мере ввода.';
    }
  }
  async function change(target) {
    if(!target.dataset.messageStatus)return;
    const item=c.messages.items.find(item=>item.id===target.dataset.messageStatus),previous=item.status;
    target.disabled=true;
    try {await request(`/admin/messages/${item.id}`,{method:'PATCH',body:{status:target.value}});item.status=target.value;ui.toast('Статус обращения обновлён.');}
    catch(error){target.value=previous;ui.toast(error.message);}
    finally{target.disabled=false;}
  }
  return {load,click,submit,input,change,rolesAllowed,canLeave,reset:()=>{dirty=false;busy=false;c.notifications=[];},get dirty(){return dirty;},get busy(){return busy;}};
}
