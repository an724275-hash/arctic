import './ux.css';
import './motion.css';
import {accountForm} from './account-form.js';
let introPlayed=false;
let pendingTabFocus;

export function polishPage(state) {
  const main=document.querySelector('#content');
  main?.setAttribute('aria-busy',String(state.loading));
  main?.querySelector('h1')?.setAttribute('tabindex','-1');
  document.querySelectorAll('img:not([decoding])').forEach(img=>img.decoding='async');
  document.querySelectorAll('input[type=email]').forEach(input=>{
    input.setAttribute('autocapitalize','none');input.setAttribute('autocorrect','off');input.spellcheck=false;
  });
  document.querySelectorAll('[role=tablist]').forEach(list=>{
    list.querySelectorAll('[role=tab]').forEach(tab=>tab.tabIndex=tab.getAttribute('aria-selected')==='true'?0:-1);
  });
  if(pendingTabFocus){
    const tab=document.querySelector(`[role=tab][data-tab="${CSS.escape(pendingTabFocus)}"]`);
    if(tab){tab.focus();pendingTabFocus=undefined;}
  }
  if(!introPlayed&&!state.loading)requestAnimationFrame(()=>{if(introPlayed)return;document.querySelector('.brand-mark')?.setAttribute('data-motion-intro','');introPlayed=true;});
  const cover=document.querySelector('.north-cover');
  if(cover&&!matchMedia('(prefers-reduced-motion:reduce)').matches){
    const snow=document.createElement('div');snow.className='polar-snow';snow.setAttribute('aria-hidden','true');
    for(let i=0;i<12;i++){const flake=document.createElement('span');flake.style.left=`${8+i*7}%`;flake.style.top='-12px';flake.style.setProperty('--fall-duration',`${9+i%5}s`);flake.style.setProperty('--fall-delay',`${-i*1.3}s`);snow.append(flake);}
    snow.style.setProperty('--snow-distance',`${Math.max(cover.clientHeight,700)+80}px`);
    cover.append(snow);
  }
  if(state.route==='people'&&state.user?.role==='admin'){
    const details=document.createElement('details');details.className='panel account-creation';details.innerHTML=accountForm();
    main.querySelector('.console-content')?.append(details);
  }
  if(state.route==='forgot-password'&&state.capabilities?.email_delivery===false){
    const note=document.createElement('p');note.className='notice';note.role='status';
    note.textContent='Автоматическая отправка писем пока недоступна. Для восстановления доступа обратитесь к организатору через раздел «Помощь».';
    main.querySelector('form')?.before(note);
  }
  if(state.user&&state.user.role!=='participant')document.querySelector('#profile-grade')?.closest('.form-field')?.setAttribute('hidden','');
  if(state.user?.role==='partner'){
    document.querySelectorAll('.navigation [data-route=awards]').forEach(link=>link.remove());
    const cabin=document.querySelector('.navigation [data-route=dashboard]');
    if(cabin){cabin.querySelector('strong').textContent='Кабинет партнёра';cabin.querySelector('small').textContent='Материалы и связь с организатором';}
  }
  if(state.user?.role==='participant'&&!state.attempts.some(a=>a.passed===true)&&state.attempt?.passed!==true){
    document.querySelectorAll('[data-action=new-project]').forEach(button=>{button.disabled=true;button.title='Доступно после проходного результата теста';});
    const section=document.querySelector('.project-register,.next-project');
    if(section){const note=document.createElement('p');note.className='chart-caption';note.textContent=`Второй этап откроется после результата не ниже ${state.config?.pass_percent??60}% в тесте.`;section.querySelector('h2')?.after(note);}
  }
  if(state.user?.role!=='admin')document.querySelectorAll('[data-console^=export-]').forEach(button=>button.remove());
  if(state.user?.role==='teacher'&&state.route==='workspace'){
    const section=document.querySelector('.mentor-students');
    if(section){
      const bar=document.createElement('div');bar.className='console-page-actions';
      const text=document.createElement('p');text.textContent='Пригласи ученика личной ссылкой. Он сам подтвердит привязку.';
      const button=document.createElement('button');button.type='button';button.className='button secondary';button.dataset.action='create-mentor-link';button.textContent='Пригласить ученика';
      bar.append(text,button);section.before(bar);
    }
  }
  if(state.route==='dashboard'&&state.mentorConnection?.teacher){
    const note=document.createElement('p');note.className='chart-caption';note.textContent='Наставник: '+state.mentorConnection.teacher.full_name;
    document.querySelector('.cabinet-tools')?.after(note);
  }
  document.querySelectorAll('input[type=password]').forEach(input=>{
    if(!input.hasAttribute('maxlength'))input.maxLength=256;
    if(input.closest('.password-control'))return;
    const wrap=document.createElement('div');wrap.className='password-control';
    input.before(wrap);wrap.append(input);
    const toggle=document.createElement('button');toggle.type='button';
    toggle.className='password-toggle';toggle.textContent='Показать';
    toggle.setAttribute('aria-label','Показать пароль');toggle.setAttribute('aria-pressed','false');
    if(input.id)toggle.setAttribute('aria-controls',input.id);
    toggle.addEventListener('click',()=>{
      const visible=input.type==='password';input.type=visible?'text':'password';
      toggle.textContent=visible?'Скрыть':'Показать';
      toggle.setAttribute('aria-label',visible?'Скрыть пароль':'Показать пароль');
      toggle.setAttribute('aria-pressed',String(visible));
    });
    wrap.append(toggle);
  });
  const navRoute=state.route==='article'?'materials':['quiz','quiz-confirm','result','project','submitted'].includes(state.route)?'dashboard':state.route;
  document.querySelectorAll('.navigation [data-route]').forEach(link=>{
    if(link.dataset.route===navRoute)link.setAttribute('aria-current','page');else link.removeAttribute('aria-current');
  });
  document.querySelectorAll('.nav-group').forEach(group=>group.classList.toggle('current-group',Boolean(group.querySelector('[aria-current=page]'))));
  document.querySelectorAll('.console-table-wrap').forEach(wrap=>{
    wrap.tabIndex=0;wrap.setAttribute('role','region');
    wrap.setAttribute('aria-label','Таблица. На узком экране можно прокручивать по горизонтали.');
  });
}

export function installNavigationPolish() {
  const banner=document.createElement('div');banner.className='connection-banner';
  banner.role='status';banner.hidden=navigator.onLine;
  banner.textContent='Нет подключения к интернету. Не закрывай страницу: введённые данные остаются в форме. Сохранение станет доступно после подключения.';
  document.body.append(banner);
  window.addEventListener('offline',()=>{banner.hidden=false;});
  window.addEventListener('online',()=>{banner.hidden=true;});
  document.addEventListener('toggle',event=>{
    if(!event.target.matches('.nav-group')||!event.target.open)return;
    document.querySelectorAll('.nav-group[open]').forEach(group=>{if(group!==event.target)group.open=false;});
  },true);
  document.addEventListener('click',event=>{
    if(!event.target.closest('.city-field')){
      const list=document.querySelector('#city-options');
      if(list)list.hidden=true;
      document.querySelector('#city')?.setAttribute('aria-expanded','false');
    }
    if(event.target.closest('.nav-group'))return;
    document.querySelectorAll('.nav-group[open]').forEach(group=>group.open=false);
  });
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape')return;
    document.querySelectorAll('.nav-group[open]').forEach(group=>{
      group.open=false;
      if(group.contains(document.activeElement))group.querySelector('summary').focus();
    });
  });
  document.addEventListener('focusin',event=>{
    document.querySelectorAll('.nav-group[open]').forEach(group=>{if(!group.contains(event.target))group.open=false;});
  });
  document.addEventListener('keydown',event=>{
    const tab=event.target.closest('[role=tab]');
    if(!tab||!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
    const tabs=[...tab.closest('[role=tablist]').querySelectorAll('[role=tab]:not(:disabled)')];
    const index=tabs.indexOf(tab);
    const next=event.key==='Home'?tabs[0]:event.key==='End'?tabs.at(-1):tabs[(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length];
    event.preventDefault();
    if(next===tab)return;
    pendingTabFocus=next.dataset.tab;next.click();
  });
}
