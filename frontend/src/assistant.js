import {icon} from './ui.js';
import { request, getSession } from './api.js';
import './assistant.css';

function assistantPanel() {
  return `<section class="assistant-panel" aria-labelledby="assistant-title">
    <header class="assistant-chat-header"><h2 id="assistant-title">Помощник GigaChat</h2><p>Об Арктике и твоём исследовании</p></header>
    <ol class="assistant-messages" role="log" aria-label="Переписка с помощником" aria-live="polite" aria-relevant="additions"></ol>
    <p class="assistant-status" role="status" aria-live="polite"></p>
    <form id="assistant-form"><label class="assistant-input-label" for="assistant-question">Сообщение</label><textarea id="assistant-question" name="question" rows="2" minlength="3" maxlength="1000" required placeholder="Напиши свой вопрос…"></textarea>
    <div class="assistant-compose-actions"><button type="button" class="link-button assistant-clear">Новый разговор</button><button class="button" type="submit">Отправить ${icon('arrow')}</button></div>
    <details class="assistant-privacy"><summary>Перед отправкой</summary><p>Не отправляй личные данные. Ответы могут содержать ошибки — проверяй факты. Во время теста помощник недоступен.</p></details>
    <label class="assistant-consent"><input name="consent" type="checkbox" required><span>Разрешаю отправлять сообщения беседы в GigaChat</span></label></form></section>`;
}

let widget;
let currentRoute = () => '';
let history=[];
let pending=false;
let conversation=0;
let accountId;

function addMessage(role,text){
  const message=document.createElement('li');
  message.className=`assistant-message assistant-${role}`;
  message.dataset.role=role;
  const author=document.createElement('small');author.textContent=role==='user'?'Ты':'GigaChat';
  const content=document.createElement('p');content.textContent=text;
  message.append(author,content);
  const list=widget.querySelector('.assistant-messages');list.append(message);list.scrollTop=list.scrollHeight;
  return message;
}

function clearConversation(){
  history=[];conversation++;
  widget.querySelector('.assistant-messages').replaceChildren();
  widget.querySelector('.assistant-status').textContent='';
  addMessage('assistant','Привет! Помогу разобраться в Арктике или составить план исследования. Что хочешь узнать?');
}


function closeAssistant() {
  const panel=widget?.querySelector('#assistant-window');
  if(!panel || panel.hidden) return;
  const hadFocus=panel.contains(document.activeElement);
  panel.hidden=true;widget.classList.remove('keyboard-open');widget.style.removeProperty('bottom');
  const toggle=widget.querySelector('[data-assistant-toggle]');
  toggle.setAttribute('aria-expanded','false');
  if(hadFocus) toggle.focus();
}

export function syncAssistant(route) {
  if(!widget) return;
  const nextAccount=getSession()?.user?.id||null;
  if(nextAccount!==accountId){accountId=nextAccount;clearConversation();widget.querySelector('#assistant-form').reset();}
  const blocked=['quiz','quiz-confirm'].includes(route);
  widget.querySelector('[data-assistant-toggle]').disabled=blocked;
  if(blocked) closeAssistant();
}

export function installAssistant(route = () => '') {
  currentRoute=route;
  widget=document.createElement('aside');
  widget.className='assistant-widget';
  widget.setAttribute('aria-label','Помощник и навигация');
  widget.innerHTML=`<section id="assistant-window" class="assistant-window" role="dialog" aria-labelledby="assistant-title" hidden><button type="button" class="assistant-close" aria-label="Закрыть помощника">${icon('close')}</button>${assistantPanel()}</section><div class="assistant-tools"><button type="button" class="assistant-top" aria-label="Наверх" title="Наверх" hidden><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M12 20V4m-7 7 7-7 7 7"/></svg></button><button type="button" class="assistant-launcher" data-assistant-toggle aria-controls="assistant-window" aria-expanded="false" aria-label="Открыть GigaChat" title="Помощник GigaChat"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true"><path d="M20 11a8 8 0 0 1-8 8H5l-4 3V11a9 9 0 0 1 19 0Z"/><path d="M6 10h9M6 14h6"/></svg></button></div>`;
  document.body.append(widget);
  const panel=widget.querySelector('#assistant-window');
  const toggle=widget.querySelector('[data-assistant-toggle]');
  toggle.addEventListener('click',()=>{
    if(panel.hidden) {
      panel.hidden=false;toggle.setAttribute('aria-expanded','true');
      widget.querySelector('#assistant-question').focus({preventScroll:true});
    } else closeAssistant();
  });
  widget.querySelector('.assistant-close').addEventListener('click',closeAssistant);
  widget.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();closeAssistant();}});
  const top=widget.querySelector('.assistant-top');
  const updateTop=()=>{top.hidden=window.scrollY<300;};
  window.addEventListener('scroll',updateTop,{passive:true});updateTop();
  top.addEventListener('click',()=>{
    window.scrollTo({top:0,behavior:matchMedia('(prefers-reduced-motion:reduce)').matches?'instant':'smooth'});
  });
  syncAssistant(currentRoute());
  widget.querySelector('.assistant-clear').addEventListener('click',()=>{if(!pending)clearConversation();});
  const viewportLayout=()=>{
    const viewport=window.visualViewport;
    const keyboard=viewport&&matchMedia('(max-width:700px)').matches&&viewport.height<600&&!panel.hidden&&document.activeElement?.id==='assistant-question';
    widget.classList.toggle('keyboard-open',Boolean(keyboard));
    if(keyboard){widget.style.bottom=`${Math.max(8,window.innerHeight-viewport.height-viewport.offsetTop+8)}px`;widget.style.setProperty('--assistant-viewport-height',`${viewport.height-24}px`);}
    else widget.style.removeProperty('bottom');
  };
  window.visualViewport?.addEventListener('resize',viewportLayout);
  widget.addEventListener('focusin',viewportLayout);
  widget.addEventListener('focusout',()=>queueMicrotask(viewportLayout));
  widget.querySelector('#assistant-question').addEventListener('keydown',event=>{
    if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();if(!pending)widget.querySelector('#assistant-form').requestSubmit();}
  });
  document.addEventListener('submit', async event => {
    if (event.target.id !== 'assistant-form') return;
    event.preventDefault();
    const form = event.target;
    const status=widget.querySelector('.assistant-status');
    if(pending)return;
    if(!getSession()){status.textContent='Войди в личный кабинет, чтобы написать помощнику.';return;}
    if(!form.reportValidity())return;
    const input=form.elements.question,question=input.value.trim();
    if(question.length<3){status.textContent='Напиши вопрос из нескольких слов.';return;}
    const generation=conversation;
    const context=history.slice(-6).map(message=>({...message,content:message.content.slice(0,1000)}));
    const button=form.querySelector('[type=submit]'),clear=form.querySelector('.assistant-clear');
    pending=true;button.disabled=true;clear.disabled=true;input.disabled=true;
    form.setAttribute('aria-busy','true');
    addMessage('user',question);input.value='';status.textContent='Помощник печатает…';
    try{
      const result=await request('/assistant/ask',{method:'POST',body:{question,consent:form.elements.consent.checked,history:context}});
      if(generation===conversation&&!['quiz','quiz-confirm'].includes(currentRoute())){
        addMessage('assistant',result.answer);history.push({role:'user',content:question},{role:'assistant',content:result.answer});
        history=history.slice(-6);status.textContent='';
      }
    }catch(error){
      if(generation===conversation){status.textContent=error.message;input.value=question;}
    }finally{
      pending=false;button.disabled=false;clear.disabled=false;input.disabled=false;form.removeAttribute('aria-busy');
      if(!panel.hidden&&generation===conversation)input.focus({preventScroll:true});
    }
  });
}
