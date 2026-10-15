import {request} from './api.js';
import {escapeHtml as e, icon} from './ui.js';

export function registrationTeacher(state) {
  const invitation = state.mentorToken && !state.mentorError && state.mentorInvitation;
  return `<fieldset class="registration-teacher"><legend>Преподаватель</legend>${invitation ? `<div class="selected-teacher"><strong>${e(invitation.teacher_name)}</strong><p>${e(invitation.school || 'Наставник конкурса')}</p></div><input type="hidden" name="mentor_token" value="${e(state.mentorToken)}">` : `<button type="button" class="button secondary" data-teacher-picker-toggle aria-expanded="false">Добавить преподавателя ${icon('user')}</button><div data-teacher-picker hidden><div class="form-field"><label for="teacher-search">Имя преподавателя или школа</label><input id="teacher-search" type="search" maxlength="100" autocomplete="off" placeholder="Например, Иванова или школа № 1" aria-controls="registration-teacher-id"></div><div class="form-field"><label for="registration-teacher-id">Выбери своего преподавателя</label><select id="registration-teacher-id" name="teacher_id" required><option value="">Введи хотя бы две буквы для поиска</option></select></div><p class="form-caption" data-teacher-search-status role="status">В списке преподаватели, зарегистрированные на сайте.</p></div>`}<label class="check-field"><input type="checkbox" name="teacher_consent" required><span>Подтверждаю выбор преподавателя. Он сможет видеть мои конкурсные работы и результаты.</span></label></fieldset>`;
}

export function requireRegistrationTeacher(form) {
  if (form.elements.mentor_token?.value || form.elements.teacher_id?.value) return true;
  const picker = form.querySelector('[data-teacher-picker]');
  if (picker) picker.hidden = false;
  form.querySelector('[data-teacher-picker-toggle]')?.setAttribute('aria-expanded', 'true');
  form.querySelector('#teacher-search')?.focus();
  form.querySelector('[data-teacher-search-status]').textContent = 'Найди и выбери преподавателя, чтобы создать аккаунт.';
  return false;
}

export function installRegistrationTeacher() {
  let timer, generation = 0;
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-teacher-picker-toggle]');
    if (!button) return;
    button.setAttribute('aria-expanded', 'true');
    button.closest('fieldset').querySelector('[data-teacher-picker]').hidden = false;
    document.querySelector('#teacher-search').focus();
  });
  document.addEventListener('input', event => {
    if (event.target.id !== 'teacher-search') return;
    clearTimeout(timer);
    const current = ++generation, form = event.target.closest('form');
    const select = form.elements.teacher_id, status = form.querySelector('[data-teacher-search-status]');
    const query = event.target.value.trim();
    select.replaceChildren(new Option('Выбери преподавателя', ''));
    if (query.length < 2) { status.textContent = 'Введи хотя бы две буквы имени или названия школы.'; return; }
    status.textContent = 'Ищем преподавателей…';
    timer = setTimeout(async () => {
      try {
        const teachers = await request(`/public/teachers?q=${encodeURIComponent(query)}`, {auth:false});
        if (current !== generation || !select.isConnected) return;
        for (const teacher of teachers) select.add(new Option([teacher.full_name, teacher.school, teacher.region].filter(Boolean).join(' · '), teacher.id));
        status.textContent = teachers.length ? teachers.length === 20 ? 'Уточни имя или школу, если преподавателя нет среди результатов.' : 'Выбери преподавателя из списка.' : 'Преподаватель не найден. Попроси его получить аккаунт наставника у организатора или передать личную ссылку.';
      } catch (error) { if (current === generation && status.isConnected) status.textContent = error.message; }
    }, 300);
  });
}
