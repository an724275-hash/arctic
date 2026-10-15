import {heading, button, act, escapeHtml as e} from './ui.js';
import './test-entry.css';

export function testEntry(s) {
  const config = s.config;
  if (!config) return `${heading('Тестирование', 'Не удалось получить настройки теста.')}<button class="button secondary" data-action="retry">Обновить</button>`;
  const attempts = s.attempts || [];
  const active = attempts.find(item => item.status === 'active');
  const remaining = Math.max(0, config.max_attempts - attempts.length);
  const stage = s.stages.find(item => item.slug === 'testing');
  const canStart = config.enabled && (!stage || stage.status === 'active') && remaining > 0;
  const latest = attempts[0];
  return `<div class="test-intro">${heading('Тест по Арктике', 'Природа, люди и жизнь на Севере. Первый этап конкурса.')}<div class="test-intro-layout"><section class="test-intro-main"><h2>Перед началом</h2><dl class="test-facts"><div><dt>вопросов</dt><dd>${config.question_count}</dd></div><div><dt>минут</dt><dd>${Math.ceil(config.duration_seconds / 60)}</dd></div><div><dt>проходной балл</dt><dd>${config.pass_percent}%</dd></div></dl><p>Выбирай ответы и переходи между вопросами в удобном порядке. До завершения теста выбор можно изменить.</p><p>Отсчёт начнётся после нажатия кнопки. Если закрыть страницу, время продолжит идти.</p><div class="form-actions">${button(active ? 'Продолжить тест' : 'Начать тест', act('start'), '', 'arrow', !active && !canStart ? 'disabled' : '')}${latest && latest.status !== 'active' ? button('Посмотреть результат', `data-result="${e(latest.id)}"`, 'secondary') : ''}</div><p class="form-caption">${!config.enabled || stage && stage.status !== 'active' ? 'Сейчас организатор не принимает новые попытки.' : remaining ? `Осталось попыток: ${remaining}.` : 'Доступные попытки использованы.'}</p></section><aside class="test-intro-aside"><h2>После теста</h2><p><strong>Результат и разбор</strong>Увидишь свой балл и сможешь разобрать ответы.</p><p><strong>Сертификат</strong>Документ появится в кабинете. Его можно скачать или распечатать.</p><p><strong>Следующий этап</strong>Проходной результат откроет подачу исследовательской работы.</p><a class="text-link" href="/preparation" data-route="preparation">Вернуться к подготовке</a></aside></div></div>`;
}
