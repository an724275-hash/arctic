import {heading, button, act, escapeHtml as e} from './ui.js';

export function testEntry(s) {
  const config = s.config;
  if (!config) return `${heading('Тестирование', 'Не удалось получить настройки теста.')}<button class="button secondary" data-action="retry">Обновить</button>`;
  const attempts = s.attempts || [];
  const active = attempts.find(item => item.status === 'active');
  const remaining = Math.max(0, config.max_attempts - attempts.length);
  const stage = s.stages.find(item => item.slug === 'testing');
  const canStart = config.enabled && (!stage || stage.status === 'active') && remaining > 0;
  const latest = attempts[0];
  return `<div class="public-page">${heading('Тест по Арктике', 'Проверь знания о природе, людях и жизни на Севере.')}<section class="panel compact-panel"><h2>Перед началом</h2><p>${config.question_count} вопросов · ${Math.ceil(config.duration_seconds / 60)} минут. Для проходного результата нужно набрать ${config.pass_percent}%.</p><p>Ответы сохраняются автоматически. Время не останавливается, если закрыть страницу. После завершения увидишь результат и разбор ответов.</p><div class="form-actions">${button(active ? 'Продолжить тест' : 'Начать тест', act('start'), '', 'arrow', !active && !canStart ? 'disabled' : '')}${latest && latest.status !== 'active' ? button('Посмотреть результат', `data-result="${e(latest.id)}"`, 'secondary') : ''}</div><p class="form-caption">${!config.enabled || stage && stage.status !== 'active' ? 'Сейчас организатор не принимает новые попытки.' : remaining ? `Осталось попыток: ${remaining}.` : 'Доступные попытки использованы.'}</p></section></div>`;
}
