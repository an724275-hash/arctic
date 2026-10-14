import cities from './cities.json';
import { escapeHtml as e } from './ui.js';

export const regions = [...new Set(cities.map(city => city.region))].sort((a,b) => a.localeCompare(b,'ru'));
export function geographyFields() {
  return `<div class="field-grid"><div class="form-field"><label for="region">Регион</label><select id="region" name="region" required><option value="">Выбери регион</option>${regions.map(region=>`<option>${e(region)}</option>`).join('')}</select></div><div class="form-field city-field"><label for="city">Город или населённый пункт</label><input id="city" name="city" type="text" required minlength="2" maxlength="150" autocomplete="off" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="city-options" aria-describedby="city-hint" placeholder="Начни вводить, например Нер"><div id="city-options" role="listbox" aria-label="Подсказки городов" hidden></div><span id="city-hint" class="form-caption">Выбери подсказку или введи населённый пункт полностью.</span></div></div>`;
}
export function updateCities(input) {
  const list = document.querySelector('#city-options');
  const query = input.value.trim().toLocaleLowerCase('ru-RU');
  const region = document.querySelector('#region').value;
  const matches = query.length < 2 ? [] : cities.filter(city => (!region || city.region===region) && city.name.toLocaleLowerCase('ru-RU').includes(query)).sort((a,b)=>Number(b.name.toLocaleLowerCase('ru-RU').startsWith(query))-Number(a.name.toLocaleLowerCase('ru-RU').startsWith(query))).slice(0,8);
  list.innerHTML = matches.map(city=>`<button type="button" role="option" aria-selected="false" data-city="${e(city.name)}" data-region="${e(city.region)}"><strong>${e(city.name)}</strong><small>${e(city.region)}</small></button>`).join('');
  list.hidden = !matches.length;
  input.setAttribute('aria-expanded',String(Boolean(matches.length)));
}
export function selectCity(button) {
  document.querySelector('#city').value = button.dataset.city;
  document.querySelector('#region').value = button.dataset.region;
  document.querySelector('#city-options').hidden = true;
  document.querySelector('#city').setAttribute('aria-expanded','false');
  document.querySelector('#city').focus();
}
export function cityKeys(event) {
  const list = document.querySelector('#city-options');
  if (!list || !event.target.closest('.city-field')) return;
  if (event.key==='Escape') { list.hidden=true; document.querySelector('#city').setAttribute('aria-expanded','false'); }
  if (!['ArrowDown','ArrowUp'].includes(event.key) || list.hidden) return;
  event.preventDefault();
  const options = [...list.querySelectorAll('button')];
  const current = options.indexOf(document.activeElement);
  options[(current+(event.key==='ArrowDown'?1:-1)+options.length)%options.length]?.focus();
}
