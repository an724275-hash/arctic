import {heading,escapeHtml as e,icon} from './ui.js';

export function expertSettings(s){
  const c=s.console;
  return `${heading('Направления экспертов','Выберите направления, по которым эксперт может получать новые работы. Ранее назначенные работы и оценки сохраняются.')}<div class="stack">${c.experts.items.map(expert=>`<section class="panel"><h2>${e(expert.full_name)}</h2><p class="chart-caption">${e(expert.email)}</p><form data-console-form="expert-directions" class="project-form"><input type="hidden" name="expert_id" value="${e(expert.id)}"><fieldset class="direction-options"><legend>Направления конкурса</legend>${c.nominations.filter(n=>n.is_active).map(n=>`<label class="check-field"><input type="checkbox" name="nomination_id" value="${e(n.id)}" ${c.directions.some(d=>d.expert_id===expert.id&&d.nomination_id===n.id)?'checked':''}><span>${e(n.title)}</span></label>`).join('')}</fieldset><div class="form-message" role="alert"></div><button type="submit" class="button secondary">Сохранить направления ${icon('check')}</button></form></section>`).join('')||'<p class="console-empty">Экспертов пока нет. Учётную запись создаёт администратор.</p>'}</div>`;
}
