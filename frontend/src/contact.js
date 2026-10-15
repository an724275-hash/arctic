import {request} from './api.js';

export function hasContactDraft() {
  const form=document.querySelector('#contact-form');
  return Boolean(form && (form.getAttribute('aria-busy')==='true' || ['name','email','message'].some(name=>form.elements[name]?.value.trim())));
}

export function contactView() {
  const kind=new URLSearchParams(location.search).get('kind');
  return `<article class="reading-page"><h1 tabindex="-1">Связь с организатором</h1><p class="reading-lead">Задай вопрос об участии или предложи помощь конкурсу. Обращение попадёт в кабинет организатора.</p><form id="contact-form" class="project-form"><div class="form-field"><label for="contact-kind">Тема обращения</label><select id="contact-kind" name="kind"><option value="feedback">Вопрос об участии</option><option value="sponsor" ${kind==='sponsor'?'selected':''}>Партнёрство и спонсорство</option><option value="volunteer" ${kind==='volunteer'?'selected':''}>Хочу помочь как волонтёр</option></select></div><div class="form-field"><label for="contact-name">Как к тебе обращаться</label><input id="contact-name" name="name" minlength="2" maxlength="200" autocomplete="name" required></div><div class="form-field"><label for="contact-email">Электронная почта для ответа</label><input id="contact-email" name="email" type="email" maxlength="254" autocomplete="email" required></div><div class="form-field"><label for="contact-message">Сообщение</label><textarea id="contact-message" name="message" minlength="10" maxlength="10000" rows="5" required></textarea><p class="form-caption">Не отправляй пароли, документы или данные других участников.</p></div><label class="check-field"><input name="consent" type="checkbox" required><span>Разрешаю организатору обработать указанные данные для ответа на обращение.</span></label><button class="button" type="submit">Отправить обращение</button><p class="contact-result" role="status" aria-live="polite"></p></form></article>`;
}

export function installContact() {
  document.addEventListener('submit', async event => {
    if(event.target.id !== 'contact-form') return;
    event.preventDefault();
    const form=event.target;
    if(form.getAttribute('aria-busy')==='true') return;
    for(const name of ['name','email','message']) form.elements[name].value=form.elements[name].value.trim();
    if(!form.reportValidity()) return;
    const data=new FormData(form),button=form.querySelector('button'),output=form.querySelector('.contact-result');
    button.disabled=true;form.setAttribute('aria-busy','true');
    try {
      await request('/contact',{method:'POST',auth:false,body:{kind:data.get('kind'),name:data.get('name'),email:data.get('email'),message:data.get('message'),consent:data.get('consent')==='on'}});
      form.reset();output.textContent='Обращение сохранено. Организатор увидит его в своём кабинете.';
    } catch(error) {output.textContent=error.message;}
    finally {button.disabled=false;form.removeAttribute('aria-busy');}
  });
}
