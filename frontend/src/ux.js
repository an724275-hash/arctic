import './ux.css';

export function polishPage(state) {
  const main=document.querySelector('#content');
  main?.setAttribute('aria-busy',String(state.loading));
  main?.querySelector('h1')?.setAttribute('tabindex','-1');
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
  document.querySelectorAll('input[type=password]').forEach(input=>{
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
  document.querySelectorAll('.nav-group').forEach(group=>{
    if(group.querySelector('[aria-current=page]'))group.classList.add('current-group');
  });
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
}
