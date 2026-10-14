import {icon} from './ui.js';
import { request, getSession } from './api.js';
import './assistant.css';

function assistantPanel() {
  return `<section class="assistant-panel" aria-labelledby="assistant-title"><h2 id="assistant-title">Помощник GigaChat</h2><p>GigaChat поможет понять тему и составить план исследования. Ответы могут содержать ошибки: проверяй факты по источникам.</p><form id="assistant-form"><label for="assistant-question">Твой вопрос</label><textarea id="assistant-question" name="question" rows="3" minlength="3" maxlength="1000" required placeholder="Например, почему белые медведи зависят от морского льда?"></textarea><p class="assistant-privacy">Не указывай имя, телефон, адрес или другие личные данные. Помощник недоступен во время теста.</p><label class="assistant-consent"><input name="consent" type="checkbox" required><span>Разрешаю отправить текст вопроса в GigaChat для ответа</span></label><button class="button" type="submit">Задать вопрос</button><p class="assistant-answer" role="status" aria-live="polite"></p></form></section>`;
}

let widget;
let currentRoute = () => '';

function closeAssistant() {
  const panel=widget?.querySelector('#assistant-window');
  if(!panel || panel.hidden) return;
  const hadFocus=panel.contains(document.activeElement);
  panel.hidden=true;
  const toggle=widget.querySelector('[data-assistant-toggle]');
  toggle.setAttribute('aria-expanded','false');
  if(hadFocus) toggle.focus();
}

export function syncAssistant(route) {
  if(!widget) return;
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
  document.addEventListener('submit', async event => {
    if (event.target.id !== 'assistant-form') return;
    event.preventDefault();
    const form = event.target;
    const output = form.querySelector('.assistant-answer');
    if (!getSession()) { output.textContent = 'Войди в личный кабинет, чтобы задать вопрос.'; return; }
    if (!form.reportValidity()) return;
    const data = new FormData(form);
    const button = form.querySelector('button');
    button.disabled = true; form.setAttribute('aria-busy', 'true');
    output.textContent = 'Готовлю ответ…';
    try {
      const result = await request('/assistant/ask', {method: 'POST', body: {question: data.get('question'), consent: data.get('consent') === 'on'}});
      output.textContent = result.answer;
    } catch (error) { output.textContent = error.message; }
    finally { button.disabled = false; form.removeAttribute('aria-busy'); }
  });
}
