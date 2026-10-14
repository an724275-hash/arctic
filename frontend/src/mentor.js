import {request} from './api.js';
import {heading,escapeHtml as e,icon} from './ui.js';

export function mentorView(s){
 if(s.mentorError)return `${heading('Приглашение недоступно',e(s.mentorError))}<a class="button secondary" href="/help" data-route="help">Помощь ${icon('arrow')}</a>`;
 const info=s.mentorInvitation;
 return `${heading('Твой наставник','Связь создаётся только после твоего подтверждения.')}<section class="panel compact-panel"><h2>${e(info?.teacher_name||'Приглашение наставника')}</h2><p class="chart-caption">${e(info?.school||'Наставник конкурса')} поможет проверить материалы исследования. Он увидит твои работы и опубликованные оценки, но не сможет проходить тест или отправлять проект вместо тебя.</p>${s.user?s.user.role==='participant'?`<form data-mentor-join class="project-form"><label class="check-field"><input type="checkbox" name="consent" required><span>Подтверждаю привязку к этому наставнику.</span></label>${s.mentorConnection?.teacher?'<label class="check-field"><input name="replace" type="checkbox"><span>Разрешаю заменить моего текущего наставника.</span></label>':''}<div class="form-message" role="alert"></div><button type="submit" class="button">Привязать наставника ${icon('check')}</button></form>`:'<p class="notice">Приглашение предназначено ученику. Открой его в аккаунте участника.</p>':'<div class="console-export"><a class="button" href="/#login" data-route="login">Войти</a><a class="button secondary" href="/#register" data-route="register">Создать аккаунт</a></div><p class="form-caption">После входа или регистрации вернём тебя к подтверждению.</p>'}<button type="button" class="link-button" data-action="cancel-mentor">Отменить приглашение</button></section>`;
}

export function createMentor(s){
 const key='arctic-mentor-invite';
 try{s.mentorToken=(location.pathname==='/teacher-invite'?new URLSearchParams(location.search).get('token'):null)||sessionStorage.getItem(key);if(s.mentorToken)sessionStorage.setItem(key,s.mentorToken);}catch{s.mentorToken=null;}
 async function load(){
  s.mentorError='';
  if(!s.mentorToken){s.mentorError='Открой личную ссылку, которую передал наставник.';return;}
  try{s.mentorInvitation=await request('/teachers/invite-link/'+encodeURIComponent(s.mentorToken),{auth:false});s.mentorConnection=s.user?.role==='participant'?await request('/teachers/link'):null;}
  catch(error){s.mentorError=error.message;}
 }
 function clear(){s.mentorToken=null;s.mentorInvitation=null;s.mentorConnection=null;try{sessionStorage.removeItem(key);}catch{}}
 return {load,clear};
}
