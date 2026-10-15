import {publicCriteria} from './public-criteria.js';
import {presenceLabel} from './presence.js';
import {formatFileSize} from './ui.js';
import {participationDocuments} from './documents-public.js';
import {homeBanners} from './home-banners.js';
import {contestPath} from './contest-path.js';
import { projectOutcome, defensesPanel } from './review-components.js';
import { escapeHtml as e, icon, mark, button, heading, go, act } from './ui.js';
import './participant.css';
import { soundButton } from './sound.js';
import { educationArticles } from './education.js';
import {geographyFields} from './geography.js';
import {avatar} from './profile.js';
import {journey} from './product-views.js';
import {partnerDashboard} from './partner.js';

export const statusNames = { draft: 'Черновик', submitted: 'На проверке', admitted: 'Допущен к конкурсу', rejected: 'Нужны изменения', reviewing: 'На экспертизе', evaluated: 'Оценён' };
const status = p => `<span class="status ${p.status === 'admitted' ? 'success' : ''}">${icon(p.status === 'draft' ? 'file' : 'check')}${e(statusNames[p.status] || p.status)}</span>`;
const date = value => new Date(value).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
export function errorBox(message, retry = true) {
  return `<div class="notice error-notice" role="alert">${icon('info')}<div><strong>Не получилось завершить действие</strong><p>${e(message)}</p>${retry ? '<button class="link-button" data-action="retry">Попробовать ещё раз</button>' : ''}</div></div>`;
}
export function header(s) {
  const menu=(title,items)=>`<details class="nav-group"><summary>${title}<svg viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4" fill="none" stroke="currentColor" stroke-width="1.5"/></svg></summary><div class="nav-panel">${items.map(([route,label,description,symbol])=>`<a href="/#${route}" data-route="${route}">${icon(symbol)}<span><strong>${label}</strong><small>${description}</small></span>${icon('arrow')}</a>`).join('')}</div></details>`;
  return `<header class="header"><a class="brand" href="/" data-route="home" aria-label="Арктика: главная">${mark()}<div><div class="brand-name">Арктика</div><div class="brand-note">конкурс открытий</div></div></a><nav class="navigation product-navigation" aria-label="Основная навигация">${menu('Конкурс',[['about','О конкурсе','Цели, этапы и номинации','compass'],['rules','Положение','Условия и сроки участия','file'],['news','Новости','Объявления организатора','book'],['media','Медиатека','Фото, видео и архив работ','book'],['help','Помощь','Ответы на вопросы и поиск','info']])}${menu('Участникам',[['participation','Как участвовать','От регистрации до экспертизы','compass'],['dashboard','Тест и проекты','Твой путь в личном кабинете','folder'],['awards','Документы и награды','Сертификаты, грамоты и благодарности','shield']])}<a href="/preparation" data-route="preparation">Подготовка к конкурсу</a><a href="/materials" data-route="materials" ${['materials','article'].includes(s.route)?'aria-current="page"':''}>Открывай Север</a></nav><div class="header-actions">${presenceLabel()}${s.user?`<button type="button" class="button account-button" data-route="dashboard" aria-label="Мой кабинет">${icon('user')}<span class="account-label">Мой кабинет</span></button>`:`<button type="button" class="button account-button" data-route="login" aria-label="Войти в личный кабинет">${icon('user')}<span class="account-label">Войти</span></button>`}${s.route==='home'?'':soundButton()}<button class="menu-button round-icon" type="button" data-action="menu" aria-label="Открыть меню">${icon('menu')}</button></div></header>`;
}
export function mobileNavigation(s) {
  const workRole = ['admin','commission','expert','teacher'].includes(s.user?.role);
  const items = workRole ? [['home','home','Главная'],['workspace','folder','Кабинет'],...(['admin','commission'].includes(s.user.role) ? [['rankings','compass','Результаты']] : [])] : [['home','home','Главная'],['dashboard','compass','Мой кабинет'],['project','folder','Проект']];
  const active = s.route === 'review-project' ? 'workspace' : ['quiz', 'quiz-confirm', 'result'].includes(s.route) ? 'dashboard' : s.route === 'submitted' ? 'project' : s.route;
  return `<nav class="mobile-nav" aria-label="Навигация участника">${items.map(([r,i,t]) => `<a href="${r === 'home' ? '/' : `/#${r}`}" data-route="${r}" class="${active === r ? 'active' : ''}" ${active === r ? 'aria-current="page"' : ''}>${icon(i)}<span>${t}</span></a>`).join('')}</nav>`;
}
export function footer(s) {
  return `<footer class="footer"><span>Удивительная и неизведанная Арктика</span><div class="footer-links"><a href="/rules" data-route="rules">Положение о конкурсе</a><a href="/help" data-route="help">Помощь</a><a href="/partners" data-route="partners">Партнёрам</a><a href="/contacts" data-route="contacts">Контакты</a>${s.user ? '<button data-action="logout">Выйти</button>' : ''}</div></footer>`;
}
export function landing(s) {
  const news = s.content.filter(item => item.kind === 'news' && item.slug !== 'demo-materials').slice(0, 3);
  return `<div class="participant-home">
    <section class="north-cover">
      <div class="cover-copy"><p class="cover-kicker">Школьный конкурс об Арктике</p><h1 tabindex="-1">Удивительная<br>и неизведанная<br>Арктика</h1><p class="cover-intro">Узнай, как устроена жизнь на Севере, проверь свои знания и представь собственное исследование. От первого вопроса до проекта, который увидят эксперты.</p><div class="cover-actions">${button('Пройти тестирование', go('testing'))}</div></div>
      ${soundButton('hero')}<picture class="cover-bear"><source media="(prefers-reduced-motion: reduce)" srcset="/assets/arctic-bear.webp"><img src="/assets/arctic-bear-animated.webp" width="648" height="648" alt="Белый медвежонок в голубой шапке приветствует участников"></picture><img class="cover-landscape" fetchpriority="high" src="/assets/arctic-landscape.webp" width="1672" height="941" alt="Снежные горы и льды арктического побережья">
    </section>

    <section class="discovery-editorial"><div><h2>Исследуй Арктику</h2><p>Арктика хранит истории о природе, людях и смелых идеях. Здесь исследование может начаться с карты, музейного предмета, семейного рассказа или наблюдения за окружающим миром.</p><p>Конкурс помогает пройти весь путь: разобраться в теме, проверить знания, собрать источники и показать, что удалось узнать. Педагог поддержит работу, а эксперты дадут обратную связь.</p><a class="text-link" href="/about" data-route="about">Подробнее о конкурсе ${icon('arrow')}</a></div><aside><span class="editorial-coordinate" aria-hidden="true">66°33′ N</span><h3>Что может стать темой</h3><ul><li>Лёд, климат и северные экосистемы</li><li>История, языки и культура народов Севера</li><li>Технологии и повседневная жизнь в Арктике</li></ul><p>Это идеи для исследования. Официальные номинации и условия смотри в Положении.</p></aside></section><section class="journey-section" aria-labelledby="journey-title"><div class="home-section-heading"><h2 id="journey-title">Как проходит конкурс</h2><a class="text-link" href="/participation" data-route="participation">Как участвовать ${icon('arrow')}</a></div>${contestPath(s)}</section>
    <section class="home-materials"><div><h2>Материалы об Арктике</h2><p>Природа, культура и идеи для первого исследования. Начни со знакомства с Арктикой.</p><a class="text-link" href="/materials" data-route="materials">Открыть материалы ${icon('arrow')}</a></div><a class="home-story" href="/materials/nature" data-article="nature"><span class="reading-symbol">${icon('mountain')}</span><h3>Лёд, океан<br>и жизнь на Севере</h3><span class="text-link">Читать заметку ${icon('arrow')}</span></a></section>
    ${homeBanners(s.content)}
    ${news.length ? `<section class="publication-section"><div class="library-heading"><h2>Новости конкурса</h2></div><div class="published-list">${news.map(item => `<a class="article-row" href="/materials/${encodeURIComponent(item.slug)}" data-content="${e(item.slug)}"><div><h3>${e(item.title)}</h3><p>${e(item.excerpt || '')}</p></div>${icon('arrow')}</a>`).join('')}</div></section>` : ''}
    ${s.publicError ? `<p class="public-warning" role="status">${e(s.publicError)}</p>` : ''}
  </div>`;
}

export function aboutView(s) {
  return `<div class="public-page">
    <header class="public-heading"><h1 tabindex="-1">О конкурсе</h1><p>Арктика начинается с любопытства. Конкурс помогает школьникам узнать, как связаны природа, история и жизнь людей на Севере, а затем превратить интерес в собственное исследование. Участник проходит образовательный этап, проверяет знания и представляет проект экспертам.</p></header>
    <div class="public-editorial"><section class="public-prose"><h2>О чём конкурс</h2><p>«Удивительная и неизведанная Арктика» объединяет образовательные материалы, проверку знаний и конкурс проектных работ. Здесь можно разобраться в теме, сформулировать свой вопрос и представить результаты экспертам.</p><p>Природа Арктики связана с жизнью людей, культурой и историей освоения Севера. Для проекта подойдут наблюдения, работа с картами и источниками, сравнение данных или творческое исследование выбранной темы.</p><a class="text-link" href="/materials" data-route="materials">Познакомиться с Арктикой ${icon('arrow')}</a></section><aside class="public-note"><h2>Кто участвует</h2><p>Школьник выбирает тему, собирает материалы и готовит работу. Педагог помогает уточнить вопрос, составить план и проверить источники. Организатор проверяет комплектность заявки, а эксперты изучают допущенные проекты и дают содержательную обратную связь. Возрастные категории и другие условия устанавливает Положение.</p><a class="text-link" href="/participation" data-route="participation">Порядок участия ${icon('arrow')}</a></aside></div>
    <section class="sakha-story"><div class="sakha-mascot"><img src="/assets/sakha-bear.webp" width="800" height="800" alt="Маскот Арктики с флагом Республики Саха (Якутия) на шапке" loading="lazy"></div><div><h2>Темы исследования</h2><p>Интерес к Арктике может начаться с родного края: рассказа семьи, предмета в музее или наблюдения за природой. Мишка с флагом Республики Саха (Якутия) приглашает узнать больше о людях, культуре и жизни Севера.</p><p>Выбери конкретную историю, найди достоверные источники и обсуди свой вопрос с наставником. Даже небольшое исследование может стать первым шагом к большому открытию.</p><a class="text-link" href="/materials/culture" data-article="culture">Люди и культура Севера ${icon('arrow')}</a></div></section>
    <section class="public-section"><div class="public-section-heading"><h2>Этапы конкурса</h2><p>Результаты и документы доступны в личном кабинете.</p></div>${contestPath(s)}</section>
    <section class="public-section public-editorial"><div class="public-prose"><h2>Номинации</h2><p>При подаче работы выбери направление, которое соответствует главному вопросу исследования. Сравни название и описание номинации с содержанием работы: важен предмет исследования, а не только способ оформления. Окончательные требования к каждой номинации нужно сверить с Положением.</p>${s.nominations.length ? `<div class="nomination-directory">${s.nominations.map(n => `<details><summary>${e(n.title)}</summary>${n.description ? `<p>${e(n.description)}</p>` : '<p>Требования к направлению уточняются в Положении конкурса.</p>'}</details>`).join('')}</div>` : '<p class="muted">Доступные номинации появятся здесь после публикации организатором.</p>'}</div><aside class="public-note public-note-blue"><h2>Условия участия</h2><p>Возрастные категории, сроки, требования к оформлению и порядок награждения определяет Положение о конкурсе.</p><a class="text-link" href="/rules" data-route="rules">Открыть Положение ${icon('arrow')}</a></aside></section>
    <div class="public-action"><div><h2>Порядок участия</h2><p>Посмотри порядок участия и подготовь свою первую идею.</p></div><a class="button" href="/participation" data-route="participation">Как участвовать ${icon('arrow')}</a></div>
  </div>`;
}

export function participationView(s) {
  return `<div class="public-page">
    <header class="public-heading"><h1 tabindex="-1">Как участвовать</h1><p>В конкурсе два этапа: тестирование и исследовательская работа. Сначала зарегистрируйся и пройди тест. Второй этап открывается после проходного результата. Кабинет сохраняет твои документы и показывает, на каком этапе находится проект. Начать можно с чтения материалов, даже если тема ещё не выбрана.</p></header>
    ${contestPath(s)}
    <section class="submission-desk" id="submission-requirements"><div><h2>Что приложить к работе</h2><p>В основном документе покажи вопрос, цель, метод, собственные результаты и выводы. Для чужих фактов и изображений укажи авторов и источники. Наставник может проверить материалы до отправки.</p></div><dl class="document-specs"><div><dt>Исследование</dt><dd>PDF или DOCX <span>обязательно</span></dd></div><div><dt>Презентация</dt><dd>PDF или PPTX <span>по желанию</span></dd></div><div><dt>Видео</dt><dd>MP4, WebM или ссылка <span>по желанию</span></dd></div><div><dt>Размер файла</dt><dd>До 30 МБ</dd></div></dl></section>
    <section class="public-section public-faq"><h2>Вопросы перед стартом</h2><details><summary>Нужен ли готовый проект при регистрации?</summary><p>Нет. Сначала можно изучить материалы и пройти тест. Первую идею проекта сохрани в черновике и возвращайся к ней по мере подготовки.</p></details><details><summary>Можно ли остановить тест и вернуться позже?</summary><p>Сохранённые ответы останутся в кабинете, но время попытки не останавливается. При возврате ты продолжишь тот же тест с оставшимся временем.</p></details><details><summary>Где посмотреть сертификат и оценку проекта?</summary><p>Сертификат доступен в кабинете после завершения теста. Оценки проекта и комментарии экспертов появятся после публикации результатов организатором.</p></details><details><summary>Как выбрать тему исследования?</summary><p>Начни с одного конкретного вопроса. Определи, какие источники или наблюдения помогут на него ответить, и обсуди план с педагогом.</p><a class="text-link" href="/materials/idea" data-article="idea">Заметка о выборе темы ${icon('arrow')}</a></details></section>
    ${publicCriteria(s.criteria)}
    ${participationDocuments(s.content)}
    <div class="public-action"><div><h2>Начать участие</h2><p>Тест, черновики и результаты находятся в твоём кабинете.</p></div>${button(s.user ? 'Открыть кабинет' : 'Начать участие', go('dashboard'))}</div>
  </div>`;
}

export function libraryView(s) {
  const materials = s.content.filter(item => item.kind === 'education');
  return `<div class="public-page">
    <header class="public-heading"><h1 tabindex="-1">Открывай Север</h1><p>Здесь собраны материалы о природе, культуре, истории и современных задачах Арктики. Они помогут подготовиться к тесту, выбрать тему проекта и понять, какие источники нужны для проверки собственной идеи. Читай по порядку или начни с вопроса, который тебе интересен.</p></header>
    <div class="material-intro"><a class="material-feature" href="/materials/nature" data-article="nature"><span class="reading-symbol">${icon('mountain')}</span><h2>Лёд, океан<br>и жизнь на Севере</h2><p>Знакомство с Арктикой, её природой и вопросами, которые можно исследовать.</p><span class="text-link">Читать заметку ${icon('arrow')}</span></a><div class="material-reading-list"><a href="/materials/culture" data-article="culture"><div><h2>Люди и культура Севера</h2><p>Традиции, ремёсла и связь человека с местом.</p></div>${icon('arrow')}</a><a href="/materials/idea" data-article="idea"><div><h2>Как выбрать тему проекта</h2><p>От наблюдения к вопросу и плану исследования.</p></div>${icon('arrow')}</a></div></div>
    <section class="public-section"><div class="public-section-heading"><h2>Семь тем для знакомства с Арктикой</h2><p>От природы и климата до профессий и собственного вклада. В каждой теме есть объяснения, вопрос для исследования и ссылки на источники.</p></div><div class="form-field library-search"><label for="library-search">Найти тему</label><input id="library-search" type="search" data-library-search placeholder="Например, медведь или профессии" autocomplete="off"></div><p data-library-empty hidden role="status">По этому запросу тем не найдено. Попробуй другое слово.</p><div class="material-catalog education-catalog">${Object.entries(educationArticles).map(([slug,item]) => `<a href="/materials/${slug}" data-article="${slug}"><div><h3>${e(item.title)}</h3><p>${e(item.intro)}</p></div>${icon('arrow')}</a>`).join('')}</div></section>
    ${materials.length ? `<section class="public-section"><div class="public-section-heading"><h2>Дополнительные материалы</h2><p>Публикации организатора дополняют основные темы и помогают выбрать направление работы.</p></div><div class="material-catalog">${materials.map(item => `<a href="/materials/${encodeURIComponent(item.slug)}" data-content="${e(item.slug)}"><div><h3>${e(item.title)}</h3><p>${e(item.excerpt || 'Открыть материал')}</p></div>${icon('arrow')}</a>`).join('')}</div></section>` : ''}
    <section class="public-section research-guide"><h2>Читай как исследователь</h2><div><p>Записывай вопросы, которые появляются во время чтения. Сравнивай сведения из нескольких источников и сохраняй ссылки, чтобы позже указать их в работе.</p><p>Тему легче раскрыть, если она конкретна. Вместо рассказа обо всей Арктике выбери одно явление, место или исследовательский вопрос.</p><a class="text-link" href="/participation" data-route="participation">Как оформить и отправить проект ${icon('arrow')}</a></div></section>
    ${s.publicError ? `<p class="public-warning" role="status">${e(s.publicError)}</p>` : ''}
  </div>`;
}

export function login(s) {
  return `<div class="auth-layout participant-auth">
    <section class="panel auth-panel">${heading('Войти в аккаунт', 'Используй почту и пароль своего аккаунта.', 'user')}
      <form id="login-form" class="project-form"><div class="form-field"><label for="email">Электронная почта</label><input id="email" name="email" type="email" autocomplete="email" required maxlength="254" placeholder="name@example.ru"></div><div class="form-field"><label for="password">Пароль</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="256"></div><div class="form-message" role="alert"></div><button class="button wide" type="submit"><span>Войти</span>${icon('arrow')}</button><button type="button" class="link-button" data-route="forgot-password">Не помню пароль</button><div class="auth-switch">Нет аккаунта? <a href="#register" data-route="register">Зарегистрироваться</a></div></form>
    </section>
    <aside class="auth-art"><img src="/assets/arctic-landscape.webp" alt="Снежные горы у арктического залива"><div><h2>Твои работы<br>и результаты</h2><p>Здесь хранятся твои работы, результаты и сертификаты.</p></div></aside>
  </div>`;
}
export function register() {
  return `${heading('Регистрация участника', 'Создай личный аккаунт для тестирования и подачи работы. Укажи ФИО так, как оно должно выглядеть в сертификате, и проверь адрес почты. Для несовершеннолетнего участника требуется заполнение раздела законного представителя.', 'user')}<div class="workspace-grid"><section class="panel"><form id="register-form" class="project-form"><div class="form-section-title">Личные данные</div><div class="form-field"><label for="full_name">Фамилия, имя и отчество</label><input id="full_name" name="full_name" autocomplete="name" minlength="2" maxlength="200" required placeholder="Как указать тебя в сертификате"></div><div class="field-grid"><div class="form-field"><label for="birth_date">Дата рождения</label><input id="birth_date" name="birth_date" type="date" required max="${new Date().toISOString().slice(0,10)}"></div><div class="form-field"><label for="grade">Класс <span class="optional">необязательно</span></label><select id="grade" name="grade"><option value="">Выбери класс</option>${Array.from({length:11}, (_,i)=>`<option>${i+1}</option>`).join('')}</select></div></div><div class="form-field"><label for="school">Школа <span class="optional">необязательно</span></label><input id="school" name="school" maxlength="250" placeholder="Название школы"></div>${geographyFields()}<fieldset class="guardian-fields" id="guardian-fields" hidden disabled><legend>Если тебе ещё нет 18 лет</legend><p class="form-caption">Заполни этот раздел вместе с законным представителем.</p><div class="form-field"><label for="guardian_name">ФИО законного представителя</label><input id="guardian_name" name="guardian_name" maxlength="200" required></div><div class="form-field"><label for="guardian_email">Его электронная почта</label><input id="guardian_email" name="guardian_email" type="email" required></div><label class="check-field"><input name="guardian_consent" type="checkbox" required><span>Законный представитель согласен на участие и обработку данных ребёнка.</span></label></fieldset><div class="form-section-title">Данные для входа</div><div class="form-field"><label for="email">Электронная почта</label><input id="email" name="email" type="email" autocomplete="email" required maxlength="254" placeholder="name@example.ru"></div><div class="form-field"><label for="password">Пароль</label><input id="password" name="password" type="password" autocomplete="new-password" minlength="10" maxlength="256" required aria-describedby="password-hint"><span class="form-caption" id="password-hint">Не меньше 10 символов, включая буквы и цифры.</span></div><label class="check-field"><input name="consent" type="checkbox" required><span>Согласен на обработку персональных данных для участия в конкурсе.</span></label><div class="form-message" role="alert"></div><button class="button" type="submit"><span>Создать аккаунт</span>${icon('arrow')}</button><div class="auth-switch">Уже участник? <a href="#login" data-route="login">Войти</a></div></form></section><aside class="stack"><section class="panel green"><p class="section-index">Перед регистрацией</p><h2>Проверь данные</h2><p class="sidebar-copy">Полное имя появится в сертификате. Проверь его написание до отправки формы.</p><p class="sidebar-copy">Для входа нужна почта, к которой у тебя есть доступ. Если тебе нет 18 лет, заполни согласие вместе с законным представителем.</p></section></aside></div>`;
}
export function passwordPage(s) {
  const reset = s.route === 'reset-password';
  if (!reset && !s.capabilities?.email_delivery) return `<section class="panel compact-panel">${heading('Восстановление доступа','Обратись к организатору конкурса, если не помнишь пароль. Не сообщай свой пароль в обращении.','shield')}<a class="button" href="/contacts" data-route="contacts">Связаться с организатором</a><a href="#login" data-route="login" class="backlink">${icon('back')}Вернуться ко входу</a></section>`;
  return `<section class="panel compact-panel">${heading(reset ? 'Новый пароль' : 'Восстановление доступа', reset ? 'Придумай новый пароль для своего аккаунта.' : 'Укажи почту аккаунта для получения ссылки восстановления.', 'shield')}<form id="${reset ? 'reset' : 'forgot'}-form" class="project-form"><div class="form-field"><label for="recovery">${reset ? 'Новый пароль' : 'Электронная почта'}</label><input id="recovery" name="${reset ? 'password' : 'email'}" type="${reset ? 'password' : 'email'}" ${reset ? 'minlength="10" autocomplete="new-password"' : 'autocomplete="email"'} required></div>${reset ? '<p class="form-caption">Не меньше 10 символов, включая буквы и цифры.</p>' : ''}<div class="form-message" role="alert"></div><button class="button" type="submit">${reset ? 'Изменить пароль' : 'Запросить письмо'} ${icon('arrow')}</button><a href="#login" data-route="login" class="backlink">${icon('back')}Вернуться ко входу</a></form></section>`;
}
export function verifyEmail() {
  return `<section class="panel compact-panel">${heading('Подтвердим твою почту', 'Нажми кнопку, чтобы подтвердить адрес из письма.', 'shield')}${button('Подтвердить почту', act('verify-email'))}</section>`;
}

export function dashboard(s) {
  if(s.user.role==='partner')return partnerDashboard(s);
  const attempt = s.attempts[0];
  const completed = attempt && attempt.status !== 'active';
  const config = s.config;
  const canStart = s.user.role === 'participant' && config?.enabled;
  const remaining = config ? Math.max(0, config.max_attempts - s.attempts.length) : 0;
  const testConfig = attempt?.config || config;
  const nonParticipant = s.user.role !== 'participant';
  return `<div class="participant-workspace">
    <header class="account-hero"><div class="account-identity">${avatar(s)}<div><p class="account-role">Участник конкурса</p><h1 tabindex="-1">${e(s.user.full_name)}</h1><p>${e(s.user.school || s.user.region || 'Личный кабинет участника')}</p></div></div><div class="activity-island" role="status">${icon(attempt?.status === 'active' ? 'clock' : completed ? 'check' : 'compass')}<span>${attempt?.status === 'active' ? 'Тест в процессе' : completed ? 'Тест завершён' : 'Готов к участию'}</span></div></header><div class="cabinet-intro"><h2>Личный кабинет</h2><p>Здесь собран весь путь участия: тестирование, черновики и отправленные исследования, опубликованная обратная связь и сертификаты. Открывай работу, чтобы проверить её текущий статус и замечания организатора. Сохраняй изменения перед выходом из формы проекта.</p></div>
    <nav class="cabinet-tools" aria-label="Личный кабинет"><a href="/#profile" data-route="profile">${icon('user')}Настройки профиля</a><a href="/#awards" data-route="awards">${icon('shield')}Мои документы</a><a href="/#notifications" data-route="notifications">${icon('info')}Уведомления${s.unreadNotifications?`<span class="notification-count">${s.unreadNotifications>99?'99+':s.unreadNotifications}</span>`:''}</a></nav>${!nonParticipant?journey(s):''}
    ${nonParticipant ? '<div class="notice"><p>Для тестирования и отправки своей работы войди в аккаунт участника.</p></div>' : ''}
    <div class="workspace-grid participant-grid">
      <div class="stack">
        <section class="panel next-challenge participant-next"><div class="cabinet-section-title">${icon('book')}<span>Тестирование</span></div>
          
          <h2>${completed ? 'Тест завершён' : attempt?.status === 'active' ? 'Продолжи с места остановки' : 'Тест «Знаток Арктики»'}</h2>
          <p>${completed ? 'Результат и разбор ответов сохранены в твоём аккаунте.' : 'Проверь знания о природе, людях и жизни Севера. Выбирай ответы в удобном темпе в пределах времени попытки. После завершения получишь результат, разбор и сертификат.'}</p>
          <div class="quiz-facts">${config ? `<span>${testConfig.question_count} вопросов${attempt ? ' в попытке' : ''}</span><span>${Math.ceil(testConfig.duration_seconds/60)} минут</span><span>${attempt?.status === 'active' ? 'Попытка начата' : `Осталось попыток: ${remaining}`}</span>` : '<span>Тест ещё не настроен</span>'}</div>
          <div class="challenge-bottom">${button(completed ? 'Мой результат' : attempt?.status === 'active' ? 'Продолжить тест' : 'Начать тест', completed ? `data-result="${e(attempt.id)}"` : act('start'), '', 'arrow', nonParticipant || !completed && !attempt && (!canStart || !remaining) ? 'disabled' : '')}${completed && canStart && remaining ? '<button class="link-button" data-action="start">Новая попытка</button>' : ''}</div>
        </section>
        <section class="panel project-register">
          <div class="panel-heading"><div><h2>Исследовательские работы</h2></div>${!nonParticipant && s.projects.length ? button('Новый проект', act('new-project'), 'secondary small', 'folder') : ''}</div>
          ${s.projects.length ? s.projects.map(p => `<div class="project-row"><div><h3>${e(p.title)}</h3><p>${e(s.nominations.find(n => n.id === p.nomination_id)?.title || 'Исследовательский проект')}</p>${status(p)}</div>${button('Открыть', `data-project="${e(p.id)}"`, 'secondary small')}</div>`).join('') : `<div class="empty-state"><p>Начни с одного исследовательского вопроса. Добавь название и описание, сохрани черновик и возвращайся к нему по мере подготовки. Перед отправкой приложи основной документ и проверь выводы и источники.</p>${!nonParticipant ? button('Создать проект', act('new-project'), 'secondary small', 'folder') : ''}</div>`}
        </section>
        ${s.attempts.length > 1 ? `<section class="panel"><h2>История тестирования</h2><div class="attempt-list">${s.attempts.map(a => `<button class="article-row" ${a.status === 'active' ? 'data-action="start"' : `data-result="${e(a.id)}"`}><div><h3>${a.status === 'active' ? 'Тест в процессе' : `${a.score_percent}% · ${a.passed ? 'Порог пройден' : 'Участие зафиксировано'}`}</h3><p>${date(a.started_at)}</p></div>${icon('arrow')}</button>`).join('')}</div></section>` : ''}
      </div>
      <aside class="stack participant-sidebar">
        ${defensesPanel(s.defenses || [])}
        <section class="panel documents-panel"><h2>Сертификаты</h2><p class="sidebar-copy">${s.certificates.length ? 'Выданы по результатам участия в конкурсе.' : 'Сертификат появится здесь после завершения теста.'}</p>${s.certificates.map(c => `<button class="text-link link-button certificate-link" data-certificate="${e(c.id)}">${icon('file')}<span>${e(c.title)}<small>№ ${e(c.number)}</small></span>${icon('arrow')}</button><button class="link-button document-print" data-print-certificate="${e(c.id)}">Распечатать сертификат</button>`).join('')}</section>
        <section class="field-guide"><h2>Подготовка к конкурсу</h2><p>Семь образовательных тем объясняют природу Арктики, её историю и профессии. В заметках есть вопросы для исследования и ссылки на источники, которые помогут обосновать твою работу.</p><a href="/materials" class="text-link" data-route="materials">Открыть заметки ${icon('arrow')}</a></section>
        ${!s.user.email_verified ? '<section class="email-reminder"><h3>Подтверди почту</h3><p class="form-caption">Проверь адрес, чтобы сохранить доступ к аккаунту.</p><button class="text-link link-button" data-action="resend-email">Запросить письмо</button></section>' : ''}
      </aside>
    </div>
  </div>`;
}

export function timerText(s) {
  const seconds = Math.max(0, Math.ceil((s.deadline - Date.now()) / 1000));
  return `${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;
}
export function quiz(s) {
  const a = s.attempt;
  if (!a) return errorBox('Попытка не найдена. Вернись в кабинет и начни тест.');
  const q = a.questions[s.question];
  const selected = s.answers[q.id] || [];
  const answered = a.questions.filter(question => s.answers[question.id]?.length).length;
  return `<div class="participant-quiz">${heading(e(a.config.title), 'Читай формулировки внимательно и выбирай ответы в любом порядке. Изменить выбор можно до завершения попытки. Время идёт, даже если закрыть страницу.')}
    <div class="quiz-layout">
      <section class="quiz-main">
        <div class="quiz-toolbar"><span class="quiz-count">Вопрос ${s.question+1} из ${a.questions.length}</span><span class="timer" aria-label="Осталось времени">${icon('clock')}<span id="timer">${timerText(s)}</span></span></div>
        <div class="progress-track" role="progressbar" aria-label="Прогресс теста" aria-valuenow="${s.question+1}" aria-valuemin="0" aria-valuemax="${a.questions.length}"><div class="progress-fill" style="width:${(s.question+1)/a.questions.length*100}%"></div></div>
        <h2 id="question-title">${e(q.text)}</h2>
        <p class="quiz-hint">${q.multiple_choice ? 'Выбери все подходящие варианты.' : 'Выбери один ответ.'}</p>
        <div class="answers" role="${q.multiple_choice ? 'group' : 'radiogroup'}" aria-labelledby="question-title">${q.options.map((option, i) => `<button type="button" class="answer ${selected.includes(option.id) ? 'selected' : ''}" role="${q.multiple_choice ? 'checkbox' : 'radio'}" aria-checked="${selected.includes(option.id)}" tabindex="${q.multiple_choice || selected.includes(option.id) || !selected.length && i === 0 ? '0' : '-1'}" data-answer="${e(option.id)}" ><span class="answer-radio">${selected.includes(option.id) ? icon('check') : ''}</span><span class="answer-label">${e(option.text)}</span></button>`).join('')}</div>
        <div class="notice error-notice" data-answer-error role="alert" ${s.answerError ? '' : 'hidden'}><div><p>${e(s.answerError)}</p><button class="link-button" data-action="retry-answer">Сохранить ответ ещё раз</button></div></div>
        <div class="quiz-bottom"><span class="save-state" aria-live="polite">${icon(s.saving || s.answerError ? 'clock' : 'check')}${s.saving ? 'Сохраняем ответ…' : s.answerError ? 'Ответ пока не сохранён' : 'Сохранено'}</span>${button(s.question === a.questions.length-1 ? 'Завершить тест' : 'Следующий вопрос', act('next'), '', 'arrow', s.answerError ? 'disabled' : '')}</div>
        <div class="quiz-cancel">${s.question ? '<button class="link-button" data-action="previous">Предыдущий вопрос</button>' : '<button class="link-button" data-route="dashboard">Вернуться в кабинет</button>'}<button class="link-button" data-route="quiz-confirm">Завершить досрочно</button></div>
      </section>
      <aside class="quiz-aside"><section class="question-index"><h2>Вопросы теста</h2><p class="question-progress">Отвечено ${answered} из ${a.questions.length}</p><div class="question-map" aria-label="Перейти к вопросу">${a.questions.map((question,i)=>`<button data-question="${i}" aria-label="Вопрос ${i+1}${s.answers[question.id]?.length ? ', ответ выбран' : ''}" ${s.question === i ? 'aria-current="step"' : ''} class="${s.question === i ? 'current' : ''} ${s.answers[question.id]?.length ? 'answered' : ''}">${i+1}</button>`).join('')}</div><p class="question-legend"><span></span>Ответ выбран</p><div class="timer-note">${icon('clock')}<p>Таймер продолжает идти, если закрыть страницу. Вернуться к тесту можно из кабинета.</p></div></section></aside>
    </div>
  </div>`;
}
export function confirmation(s) {
  const total = s.attempt.questions.length;
  const answered = Object.values(s.answers).filter(options => options.length).length;
  return `${heading('Завершение теста', 'Проверь, на все ли вопросы ты ответил.')}<section class="panel confirmation"><div class="view-header-icon">${icon('shield')}</div><h2>Завершить тест?</h2><p>Ты ответил на ${answered} из ${total} вопросов. ${answered < total ? `Без ответа: ${total-answered}. Они не принесут баллов.` : 'Все вопросы отвечены.'} После завершения изменить ответы в этой попытке не получится.</p><p class="form-caption">Осталось времени: <span id="timer">${timerText(s)}</span></p><div class="form-actions">${button('Вернуться к вопросам', go('quiz'), 'secondary', 'back')}${button('Завершить и узнать результат', act('finish'), '', 'check', s.saving ? 'disabled' : '')}</div></section>`;
}
export function result(s) {
  const a = s.attempt;
  const correct = a.questions.filter(q => q.is_correct).length;
  const c = a.certificate;
  return `<div class="participant-result">${heading('Результат тестирования', 'Тест «Знаток Арктики» завершён. Посмотри итог и разбор вопросов, чтобы понять, какие темы стоит повторить. Сертификат можно скачать в PDF или открыть для печати; его номер и QR-код позволяют проверить документ.')}
    <div class="result-hero">
      <section class="result-score"><span class="result-status">${a.passed ? 'Тест пройден' : 'Участие зафиксировано'}</span><div class="score-number">${a.score_percent}<span>%</span></div><h2>${correct} из ${a.questions.length} верных ответов</h2><p>${a.passed ? 'Проходной порог набран. Можно перейти к своему исследованию.' : `Проходной порог: ${a.config.pass_percent}%. Посмотри разбор перед следующей попыткой.`}${a.status === 'expired' ? ' Время вышло. Учтены ответы, сохранённые до завершения попытки.' : ''}</p><button class="text-link link-button" data-action="review">Разобрать ответы ${icon('arrow')}</button></section>
      <section class="certificate"><p class="certificate-label">${c?.kind === 'test_passed' ? 'Сертификат об успешном прохождении' : 'Сертификат участника тестирования'}</p><h2 class="certificate-title">${e(c?.title || 'Знаток Арктики')}</h2><div class="name">${e(s.user.full_name)}</div><p class="fine">«Удивительная и неизведанная Арктика»<br>${c ? `№ ${e(c.number)} · ${date(c.issued_at)}` : 'Документ пока не выпущен.'}</p><div class="certificate-bar">${icon('file')}${c ? `<div class="certificate-actions">${button('Скачать PDF', `data-certificate="${e(c.id)}"`, 'secondary small', 'file')}${button('Распечатать', `data-print-certificate="${e(c.id)}"`, 'light small', 'file')}</div>` : ''}</div></section>
    </div>
    <section class="next-project"><div><h2>Твой исследовательский проект</h2><p>Выбери вопрос об Арктике и сохрани первую идею.</p></div>${button('Создать проект', act('new-project'))}</section>
    ${button('Вернуться в мой маршрут', go('dashboard'), 'secondary', 'back')}
  </div>`;
}

function uploadFields(s) {
  return [
    ['document', 'Основной документ', 'PDF или DOCX', '.pdf,.docx', s.file],
    ['presentation', 'Презентация', 'PDF или PPTX', '.pdf,.pptx', s.materials?.presentation],
    ['video', 'Видеоматериал', 'MP4 или WebM', '.mp4,.webm', s.materials?.video],
  ].map(([kind, label, formats, accept, file]) => {
    const id = kind === 'document' ? 'project-file' : `project-${kind}`;
    return `<div><label class="material-label" for="${id}">${label}${kind !== 'document' ? '<span class="optional">необязательно</span>' : ''}</label><label class="upload ${file ? 'attached' : ''}" for="${id}"><span class="upload-icon">${icon(file ? 'file' : 'upload')}</span><span><h3>${file ? e(file.name) : `Добавь ${kind === 'presentation' ? 'презентацию' : kind === 'video' ? 'видео' : 'документ'}`}</h3><p>${file ? 'Готов к загрузке при сохранении' : `${formats} · до 30 МБ`}</p></span><input type="file" id="${id}" data-upload-kind="${kind}" accept="${accept}" aria-label="${label}"></label></div>`;
  }).join('');
}

export function project(s) {
  const p = s.project || { title: '', abstract: '', nomination_id: '', video_url: '', files: [] };
  const locked = p.status && p.status !== 'draft';
  if (locked) return projectStatus(s);
  return `<a class="backlink" href="#dashboard" data-route="dashboard">${icon('back')}Мой кабинет</a>${heading(p.id ? 'Редактирование проекта' : 'Новый проект', 'Опиши исследовательский вопрос, способ работы и полученные результаты. Сначала можно сохранить черновик; для отправки понадобятся название, номинация, описание и основной документ. После отправки работа перейдёт на проверку организатору.', 'folder')}<div class="workspace-grid"><section class="panel"><form class="project-form" id="project-form"><div class="form-field"><label for="project-title">Название проекта</label><input id="project-title" name="title" minlength="3" maxlength="250" required placeholder="Какой вопрос ты хочешь исследовать?" value="${e(p.title)}"></div><div class="form-field"><label for="project-nomination">Номинация</label><select id="project-nomination" name="nomination_id" required><option value="">Выбери направление</option>${s.nominations.map(n=>`<option value="${e(n.id)}" ${p.nomination_id === n.id ? 'selected' : ''}>${e(n.title)}</option>`).join('')}</select>${!s.nominations.length ? '<span class="error">Пока нет доступных номинаций. Попробуй обновить страницу позже.</span>' : ''}</div><div class="form-field"><label for="project-abstract">О чём твой проект?</label><textarea id="project-abstract" name="abstract" minlength="10" maxlength="20000" required placeholder="Что ты исследуешь, почему это важно и что хочешь узнать">${e(p.abstract)}</textarea><span class="form-caption">Кратко объясни проблему, цель, метод и главный вывод. Это описание поможет организатору и экспертам понять содержание работы. Минимум 10 символов.</span></div><div class="form-field"><label for="video_url">Ссылка на видео <span class="optional">необязательно</span></label><input id="video_url" name="video_url" type="url" pattern="https://.*" maxlength="2048" value="${e(p.video_url || '')}" placeholder="https://…"></div><div class="form-section-title">Материалы исследования</div>${fileList(p.files || [], true)}${uploadFields(s)}<div class="form-message" role="alert"></div><div class="form-actions"><button class="button secondary" type="submit" name="intent" value="draft"><span>Сохранить черновик</span></button><button class="button" type="submit" name="intent" value="submit"><span>Отправить проект</span>${icon('arrow')}</button></div><p class="form-caption" id="project-save-state">${p.id ? `Черновик сохранён ${date(p.updated_at)}. Новые изменения нужно сохранить.` : 'Черновик и файлы сохранятся в твоём аккаунте. После отправки редактирование будет закрыто.'}</p></form></section><aside class="stack form-help"><section class="panel"><h2>Проверь работу</h2><ul class="checklist"><li>${icon('check')}Выбери конкретную тему, которая интересна тебе.</li><li>${icon('check')}Объясни, что и как ты исследовал.</li><li>${icon('check')}Добавь выводы и укажи источники.</li><li>${icon('check')}Проверь, что документ открывается и его удобно читать.</li></ul></section><section class="form-process-note"><h2>После отправки</h2><p>Организатор проверит комплектность и соответствие заявки условиям конкурса. При замечаниях работа будет возвращена для исправления; после допуска её изучат назначенные эксперты. Статус и комментарий появятся в кабинете, а рецензии будут доступны после публикации результатов. Редактирование отправленной работы закрыто.</p></section></aside></div>`;
}
function fileList(files, editable = false) {
  return files.length ? `<div class="file-list">${files.map(f => `<div class="file-item">${icon('file')}<div><button type="button" class="link-button" data-file="${e(f.id)}" data-filename="${e(f.original_name)}">${e(f.original_name)}</button><small>${formatFileSize(f.size_bytes)} · ${f.kind === 'document' ? 'Основной документ' : f.kind === 'presentation' ? 'Презентация' : 'Видеоматериал'}</small></div>${editable ? `<button type="button" class="round-icon" data-remove-file="${e(f.id)}" aria-label="Удалить ${e(f.original_name)}">${icon('close')}</button>` : ''}</div>`).join('')}</div>` : '';
}
export function projectStatus(s) {
  const p = s.project;
  const titles = { submitted: 'Проект отправлен', admitted: 'Проект допущен', reviewing: 'Проект на экспертизе', evaluated: 'Экспертиза завершена', rejected: 'Нужны изменения' };
  const messages = {
    submitted: 'Организатор проверит материалы. Следи за статусом в кабинете.',
    admitted: 'Материалы прошли проверку организатора. Следующий этап: оценка экспертов.',
    reviewing: 'Эксперты изучают работу. Рецензии появятся после публикации результатов.',
    evaluated: p.reviews_released ? 'Результаты опубликованы. Оценки и комментарии доступны ниже.' : 'Оценка завершена. Организатор опубликует результаты после проверки.',
    rejected: 'Верни работу в черновик, учти комментарий и отправь материалы снова.',
  };
  return `<div class="participant-submitted">
    <a class="backlink" href="#dashboard" data-route="dashboard">${icon('back')}Мой кабинет</a>
    <header class="submission-header"><div><h1 tabindex="-1">${titles[p.status] || 'Статус проекта'}</h1><p>${messages[p.status] || ''}</p></div>${status(p)}</header>
    <div class="submission-summary"><span class="section-index">${e(p.nomination_title || s.nominations.find(n => n.id === p.nomination_id)?.title || 'Исследовательский проект')}</span><h2>${e(p.title)}</h2><p>${p.submitted_at ? `Отправлено ${date(p.submitted_at)}` : 'Исследовательская работа'}</p></div>
    <div class="workspace-grid"><section class="panel"><h2>Описание проекта</h2><p class="project-abstract">${e(p.abstract)}</p>${fileList(p.files || [])}${p.video_url ? `<p><a class="text-link" href="${e(p.video_url)}" target="_blank" rel="noopener noreferrer">Посмотреть видео ${icon('arrow')}</a></p>` : ''}</section><aside class="panel submission-feedback"><h2>Обратная связь</h2><p class="project-abstract">${e(p.moderation_comment || 'Комментария пока нет.')}</p>${p.status === 'rejected' ? button('Вернуть в черновик', act('reopen'), 'secondary', 'back') : button('Обновить статус', act('refresh-project'), 'secondary', 'arrow')}</aside></div>
    ${projectOutcome(p, s.projectReviews || [], s.defenses || [])}
  </div>`;
}

export const views = { home: landing, about: aboutView, participation: participationView, materials: libraryView, login, register, dashboard, quiz, 'quiz-confirm': confirmation, result, project, submitted: projectStatus, 'forgot-password': passwordPage, 'reset-password': passwordPage, 'verify-email': verifyEmail };

