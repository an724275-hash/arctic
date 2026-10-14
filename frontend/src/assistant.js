import { request, getSession } from './api.js';
import './assistant.css';

export function assistantPanel() {
  return `<section class="assistant-panel" aria-labelledby="assistant-title"><h2 id="assistant-title">Спроси об Арктике</h2><p>GigaChat поможет понять тему и составить план исследования. Ответы могут содержать ошибки: проверяй факты по источникам.</p><form id="assistant-form"><label for="assistant-question">Твой вопрос</label><textarea id="assistant-question" name="question" rows="3" minlength="3" maxlength="1000" required placeholder="Например, почему белые медведи зависят от морского льда?"></textarea><p class="assistant-privacy">Не указывай имя, телефон, адрес или другие личные данные. Помощник недоступен во время теста.</p><label class="assistant-consent"><input name="consent" type="checkbox" required><span>Разрешаю отправить текст вопроса в GigaChat для ответа</span></label><button class="button" type="submit">Задать вопрос</button><p class="assistant-answer" role="status" aria-live="polite"></p></form></section>`;
}

export function installAssistant() {
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
