import {imageSet} from './images.js';
import {contestPath} from './contest-path.js';
import {escapeHtml as e,heading,icon,button} from './ui.js';

export function journey(s){
  return `<section class="participant-journey"><div><h2>Мой прогресс</h2><p>Выполненные задачи отмечаются по данным твоего аккаунта.</p></div>${contestPath(s,true)}</section>`;
}
export function awardsView(s){
  const certs=s.certificates;
  const participant=s.user.role==='participant';
  const explanation=participant?'После завершения теста можно скачать сертификат с уникальным номером и QR-кодом. Грамоты появятся здесь после выдачи организатором.':'Здесь хранятся документы, выданные тебе организатором. Благодарность наставнику оформляется отдельно от грамоты ученика.';
  const empty=participant?'Документов пока нет. Пройди тест и открой его результат.':'Документов пока нет. Они появятся после выдачи организатором.';
  return `${heading('Мои документы и награды','Скачай или распечатай выданные тебе сертификаты, грамоты и благодарности.')}<section class="award-feature"><img src="/assets/sakha-bear.webp" width="800" height="800" alt="Мишка Саха рядом с разделом наград"><div><h2>${certs.length?'Твои достижения сохранены':'Как получить документ'}</h2><p>${explanation}</p><p>Материальные призы и специальные награды определяет утверждённое Положение. Показанные документы не являются обещанием приза.</p><a class="text-link" href="/rules" data-route="rules">Условия награждения ${icon('arrow')}</a></div></section><section class="panel"><h2>Выданные документы</h2>${certs.length?certs.map(c=>`<article class="award-row"><span class="award-symbol">${icon(c.kind==='diploma'?'shield':'file')}</span><div><h3>${e(c.title)}</h3><p>${e(c.number)} · ${new Date(c.issued_at).toLocaleDateString('ru-RU')}</p><small>${c.kind==='diploma'?'Грамота':c.kind==='teacher_thanks'?'Благодарность':'Сертификат'}</small></div><div>${button('Скачать PDF',`data-certificate="${e(c.id)}"`,'secondary small')}${button('Печать',`data-print-certificate="${e(c.id)}"`,'secondary small')}</div></article>`).join(''):`<p class="console-empty">${empty}</p>`}</section>`;
}
export function newsView(s){
  const rows=s.content.filter(item=>item.kind==='news'&&item.slug!=='demo-materials');
  const empty=`<section class="panel"><h2>Пока нет опубликованных новостей</h2><p>Объявления появятся здесь после публикации организатором. Уже сейчас можно изучить материалы и порядок участия.</p><a class="text-link" href="/participation" data-route="participation">Как участвовать ${icon('arrow')}</a></section>`;
  return `<div class="public-page">${heading('Новости конкурса','Объявления организатора, обновления этапов и материалы об участии. Следи за датами и сверяй условия с Положением.')}<div class="news-list">${rows.length?rows.map(item=>`<article>${item.extra?.image?`<img class="news-cover" src="${e(item.extra.image)}" ${imageSet(item.extra.image)?`srcset="${e(imageSet(item.extra.image))}" sizes="(max-width:700px) 100vw, 780px"`:''} width="1280" height="720" alt="${e(item.title)}" loading="lazy">`:''}<time datetime="${e(item.created_at)}">${new Date(item.created_at).toLocaleDateString('ru-RU',{day:'numeric',month:'long',year:'numeric'})}</time><h2><a href="/materials/${encodeURIComponent(item.slug)}" data-content="${e(item.slug)}">${e(item.title)}</a></h2><p>${e(item.excerpt||item.body.slice(0,260))}</p><a class="text-link" href="/materials/${encodeURIComponent(item.slug)}" data-content="${e(item.slug)}">Читать новость ${icon('arrow')}</a></article>`).join(''):empty}</div></div>`;
}
