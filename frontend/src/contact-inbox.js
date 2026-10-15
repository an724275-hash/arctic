import {request} from './api.js';
import {escapeHtml as e} from './ui.js';

const statuses=[['new','Новое'],['in_progress','В работе'],['resolved','Решено'],['closed','Закрыто']];
const pageSize=30;

export async function loadContactInbox(c, offset=c.messagesOffset, status=c.messagesStatus) {
  const params=new URLSearchParams({limit:String(pageSize),offset:String(offset)});
  if(status) params.set('status',status);
  const result=await request(`/admin/messages?${params}`);
  if(offset>0 && offset>=result.total) return loadContactInbox(c,Math.max(0,Math.ceil(result.total/pageSize)-1)*pageSize,status);
  c.messages=result; c.messagesOffset=offset; c.messagesStatus=status;
}

export function contactInbox(c) {
  const {items,total}=c.messages;
  const options=selected=>statuses.map(([id,title])=>`<option value="${id}" ${selected===id?'selected':''}>${title}</option>`).join('');
  return `<section class="panel"><h2>Обращения с сайта</h2>
    <form data-console-form="inbox-filter" class="console-filter inbox-filter"><div class="form-field"><label for="inbox-status">Статус обращения</label><select id="inbox-status" name="status"><option value="">Все обращения</option>${options(c.messagesStatus)}</select></div><button class="button secondary small" type="submit">Показать</button></form>
    ${items.length?items.map(message=>`<details class="contact-message"><summary>${e(message.name)}<span>${new Date(message.created_at).toLocaleDateString('ru-RU')}</span></summary><p>${e(message.message)}</p><p>${e(message.email)}</p><label>Статус <select data-message-status="${e(message.id)}">${options(message.status)}</select></label></details>`).join(''):`<p class="role-empty">${c.messagesStatus?'Обращений с этим статусом нет.':'Обращений пока нет.'}</p>`}
    <nav class="console-pagination" aria-label="Страницы обращений"><span>${total?c.messagesOffset+1:0}–${c.messagesOffset+items.length} из ${total}</span><button type="button" class="link-button" data-console="messages-prev" aria-label="Предыдущая страница обращений" ${c.messagesOffset?'':'disabled'}>Назад</button><button type="button" class="link-button" data-console="messages-next" aria-label="Следующая страница обращений" ${c.messagesOffset+items.length<total?'':'disabled'}>Далее</button></nav>
  </section>`;
}
