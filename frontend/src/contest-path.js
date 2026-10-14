import {escapeHtml as e, icon} from './ui.js';

export function contestPath(s, tracked = false) {
  const attempts = s.attempts || [];
  const projects = s.projects || [];
  const completed = attempts.find(a => a.status !== 'active');
  const passed = attempts.some(a => a.passed === true);
  const submitted = projects.some(p => p.status !== 'draft');
  const reviewed = projects.some(p => p.reviews_released);
  const stages = [
    {
      title: 'Знания об Арктике', label: 'Первый этап',
      description: 'Тест открывает доступ к исследовательской работе. Материалы можно читать по желанию.',
      tasks: [
        ['Аккаунт', 'Имя, школа и согласие представителя', Boolean(s.user), s.user ? 'profile' : 'register'],
        ['Тест', 'Ответы сохранены, попытка завершена', Boolean(completed), 'dashboard'],
        ['Результат', passed ? 'Проходной результат достигнут' : `Не ниже ${s.config?.pass_percent ?? 60}% правильных ответов`, passed, completed ? `result/${completed.id}` : 'dashboard'],
      ],
      details: `${s.config?.question_count ?? 15} вопросов. ${Math.ceil((s.config?.duration_seconds ?? 600) / 60)} минут на попытку. Таймер не останавливается при закрытии страницы. После завершения доступны результат, разбор ответов и сертификат. Если тебе нет 18 лет, регистрацию нужно заполнить вместе с законным представителем.`,
      action: ['Открыть тест', 'dashboard'],
    },
    {
      title: 'Собственное исследование', label: 'Второй этап',
      description: 'Выбери вопрос, покажи свои результаты и получи обратную связь экспертов.',
      tasks: [
        ['Черновик', 'Тема и описание сохранены', projects.some(p => p.title && p.abstract?.trim()), 'dashboard'],
        ['Отправка', 'Работа поступила организатору', submitted, 'dashboard'],
        ['Экспертиза', 'Оценки и рецензии опубликованы', reviewed, 'dashboard'],
      ],
      details: 'В документе нужны вопрос, цель, метод, результаты и выводы. Основной файл — PDF или DOCX, до 30 МБ. Презентация и видео необязательны. Наставник помогает проверить материалы. После отправки работу нельзя менять, пока организатор не вернёт её с замечаниями.',
      action: [tracked ? 'Открыть работы' : 'Условия работы', tracked ? 'dashboard' : 'participation'],
    },
  ];
  return `<div class="contest-path${tracked ? ' is-tracked' : ''}">${stages.map((stage, i) => {
    const done = tracked ? stage.tasks.filter(task => task[2]).length : 0;
    const locked = tracked && i === 1 && !passed;
    return `<article class="stage-window${locked ? ' is-locked' : ''}"><header><span class="stage-label">${stage.label}</span>${tracked ? `<span class="stage-count">${locked ? 'После теста' : `${done} из ${stage.tasks.length} выполнено`}</span>` : icon(i ? 'folder' : 'compass')}</header><h3>${stage.title}</h3><p class="stage-description">${stage.description}</p>${tracked ? `<div class="stage-meter" role="progressbar" aria-label="${stage.label}: выполненные задачи" aria-valuemin="0" aria-valuemax="${stage.tasks.length}" aria-valuenow="${done}"><span style="width:${done / stage.tasks.length * 100}%"></span></div>` : ''}<ol class="stage-tasks">${stage.tasks.map(([title, detail, finished, route], index) => {
      const state = tracked && finished ? 'done' : tracked && !locked && stage.tasks.slice(0, index).every(task => task[2]) ? 'current' : '';
      const body = `<span class="task-node" aria-hidden="true">${state === 'done' ? icon('check') : ''}</span><strong>${title}</strong><small>${detail}</small>${state ? `<span class="task-state">${state === 'done' ? 'Готово' : 'Следующая задача'}</span>` : ''}`;
      return `<li class="${state}">${locked ? `<div>${body}</div>` : `<a href="/#${e(route)}" data-route="${e(route)}">${body}</a>`}</li>`;
    }).join('')}</ol><details class="stage-requirements"><summary>Условия и документы</summary><p>${stage.details}</p></details><footer>${locked ? '<span class="stage-lock">Доступ откроется после проходного результата</span>' : !tracked && i === 1 && s.route === 'participation' ? `<button class="link-button" type="button" data-reading-section="submission-requirements">Условия работы ${icon('arrow')}</button>` : `<a class="text-link" href="/#${stage.action[1]}" data-route="${stage.action[1]}">${stage.action[0]} ${icon('arrow')}</a>`}</footer></article>`;
  }).join('')}</div>`;
}
