const paths = {
  testing:'/test',partners:'/partners',media:'/media', contacts: '/contacts', home: '/', about: '/about', participation: '/participation', materials: '/materials',
  rules: '/rules', help: '/help',news:'/news',preparation:'/preparation', 'verify-email': '/verify-email', 'reset-password': '/reset-password',
  'teacher-invite':'/teacher-invite',
};
const aliases = { route: 'participation', library: 'materials' };

export function readRoute(location) {
  const hash = location.hash.slice(1);
  // старые ссылки
  if (hash && hash !== 'content') {
    const [name, ...rest] = hash.split('/');
    return [aliases[name] || name, ...rest].join('/');
  }
  const path = location.pathname.replace(/\/$/, '') || '/';
  if (path.startsWith('/materials/')) return `article/${path.slice('/materials/'.length)}`;
  return Object.keys(paths).find(key => paths[key] === path) || (path === '/index.html' ? 'home' : 'not-found');
}

export function routeUrl(route, query = '') {
  const [name, id] = route.split('/');
  if (name === 'article') return `/materials/${id || ''}`;
  const kind=new URLSearchParams(query).get('kind');
  const search = name==='contacts'&&['sponsor','volunteer'].includes(kind)?`?kind=${kind}`:['verify-email', 'reset-password'].includes(name) ? query : '';
  return paths[name] ? `${paths[name]}${search}` : `/#${route}`;
}

export const pageTitles = {
  testing:'Тест по Арктике',preparation:'Подготовка к конкурсу','expert-directions':'Направления экспертов',
  'question-bank':'Банк вопросов','content-editor':'Контент сайта',overview:'Обзор конкурса','contest-settings':'Настройки конкурса',people:'Участники',communications:'Обращения и уведомления',notifications:'Уведомления',profile:'Настройки профиля',awards:'Документы и награды',news:'Новости',
  home: 'Открой свою Арктику', about: 'О конкурсе', participation: 'Как участвовать',
  materials: 'Открывай Север', article: 'Материал', rules: 'Положение о конкурсе',
  help: 'Помощь', 'not-found': 'Страница не найдена', login: 'Вход', register: 'Регистрация',
  partners:'Партнёрам',media:'Медиатека', contacts: 'Связь с организатором', dashboard: 'Мой кабинет', quiz: 'Знакомство с Арктикой', result: 'Мой результат',
  project: 'Мой проект', submitted: 'Статус проекта', workspace: 'Рабочий кабинет',
  'review-project': 'Работа участника', rankings: 'Результаты конкурса',
};
