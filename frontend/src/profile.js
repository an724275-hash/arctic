import {request,getSession,setSession} from './api.js';
import {escapeHtml as e,heading,icon} from './ui.js';
import {geographyFields} from './geography.js';

function guardianFields(user) {
  if (!user.birth_date || user.role !== 'participant') return '';
  const birth = new Date(`${user.birth_date}T00:00:00`), today = new Date();
  const age = today.getFullYear() - birth.getFullYear() - (today.getMonth() < birth.getMonth() || today.getMonth() === birth.getMonth() && today.getDate() < birth.getDate() ? 1 : 0);
  if (age >= 18) return '';
  return `<fieldset class="profile-guardian"><legend>Законный представитель</legend><div class="form-field"><label for="profile-guardian-name">Фамилия, имя и отчество</label><input id="profile-guardian-name" name="guardian_name" value="${e(user.guardian_name || '')}" required maxlength="200" autocomplete="off"></div><div class="form-field"><label for="profile-guardian-email">Электронная почта</label><input id="profile-guardian-email" name="guardian_email" type="email" value="${e(user.guardian_email || '')}" required maxlength="254" autocomplete="off"></div><label class="check-field"><input id="profile-guardian-consent" name="guardian_consent" type="checkbox"><span>Я законный представитель участника и подтверждаю изменение моих данных.</span></label></fieldset>`;
}

export function avatar(s,className='account-avatar') {
  const src=s.user?.avatar_kind==='photo' && s.profilePhoto ? s.profilePhoto : s.user?.avatar_kind==='sakha'?'/assets/sakha-bear.webp':'/assets/arctic-bear.webp';
  return `<span class="${className}"><img src="${e(src)}" alt="Аватар ${e(s.user?.full_name||'участника')}"></span>`;
}
export function profileView(s) {
  const u=s.user;
  return `${heading('Настройки профиля','Проверь имя, учебное заведение и город. Эти данные используются для участия и сертификатов.')}<div class="profile-layout"><section class="panel"><form data-profile-form="details" class="project-form"><div class="form-field"><label for="profile-name">Фамилия, имя и отчество</label><input id="profile-name" name="full_name" required minlength="2" maxlength="200" autocomplete="name" value="${e(u.full_name)}"></div><div class="form-field"><label>Почта для входа</label><p class="profile-email">${e(u.email)} · ${u.email_verified?'подтверждена':'не подтверждена'}</p></div>${u.birth_date?`<div class="form-field"><span class="material-label">Дата рождения</span><p class="profile-email">${e(new Date(`${u.birth_date}T00:00:00`).toLocaleDateString('ru-RU'))}</p></div>`:''}<div class="form-field"><label for="profile-school">Учебное заведение</label><input id="profile-school" name="school" maxlength="250" value="${e(u.school||'')}"></div>${geographyFields().replaceAll(' required','')}<div class="form-field"><label for="profile-grade">Класс</label><select id="profile-grade" name="grade"><option value="">Не указан</option>${Array.from({length:11},(_,i)=>`<option value="${i+1}" ${u.grade===i+1?'selected':''}>${i+1}</option>`).join('')}</select></div>${guardianFields(u)}<fieldset class="avatar-options"><legend>Аватар без загрузки фото</legend>${[['bear','Белый мишка','/assets/arctic-bear.webp'],['sakha','Мишка Саха','/assets/sakha-bear.webp']].map(([kind,label,src])=>`<label><input type="radio" name="avatar_kind" value="${kind}" ${u.avatar_kind===kind?'checked':''}><img src="${src}" width="96" height="96" alt=""><span>${label}</span></label>`).join('')}</fieldset><div class="form-message" role="alert"></div><button class="button" type="submit">Сохранить профиль ${icon('check')}</button></form></section><aside class="stack"><section class="panel profile-photo-panel">${avatar(s,'profile-avatar')}<h2>Твой образ в кабинете</h2><p>Можно выбрать мишку или загрузить собственную фотографию. Фото доступно только после входа в твой аккаунт.</p><form data-profile-form="photo" class="project-form"><div class="form-field"><label for="profile-photo">Фотография</label><input class="photo-input" id="profile-photo" name="photo" type="file" accept="image/jpeg,image/png,image/webp" required><label for="profile-photo" class="photo-upload">${icon('upload')}<strong>Выбрать фотографию</strong><span data-photo-name>Файл ещё не выбран</span></label><span class="form-caption">JPG, PNG или WebP. До 3 МБ и 4096×4096 пикселей.</span></div><div class="form-message" role="alert"></div><button class="button secondary" type="submit" disabled>Сохранить фотографию</button></form></section><section class="field-guide"><h2>Почта и безопасность</h2><p>${s.capabilities?.email_delivery?'Для восстановления пароля используй почту своего аккаунта.':'Если забыл пароль, обратись к организатору конкурса.'} Смена аватара не влияет на тесты и проекты.</p><a class="text-link" href="${s.capabilities?.email_delivery?'/#forgot-password':'/contacts'}" data-route="${s.capabilities?.email_delivery?'forgot-password':'contacts'}">${s.capabilities?.email_delivery?'Восстановление пароля':'Связаться с организатором'} ${icon('arrow')}</a></section></aside></div>`;
}
export function createProfile(s,ui) {
  let busy=false,detailsDirty=false,photoDirty=false,previewUrl;
  const isDirty=()=>detailsDirty||photoDirty;
  async function photo(){if(s.profilePhoto){URL.revokeObjectURL(s.profilePhoto);s.profilePhoto=null;}if(s.user?.avatar_kind==='photo'){const blob=await request('/users/me/avatar',{blob:true});s.profilePhoto=URL.createObjectURL(blob);}}
  async function load(){s.user=await request('/users/me');await photo();}
  function afterRender(){if(s.route==='profile'&&document.querySelector('#region')){document.querySelector('#region').value=s.user.region||'';document.querySelector('#city').value=s.user.city||'';}}
  async function submit(form){
    if(busy||!form.reportValidity())return;
    const data=new FormData(form),button=form.querySelector('[type=submit]'),message=form.querySelector('.form-message');
    const controls=[...form.querySelectorAll('input,select,button')];
    const disabled=controls.map(control=>control.disabled);
    controls.forEach(control=>control.disabled=true);
    busy=true;button.disabled=true;message.textContent='Сохраняем…';
    try {
      if(form.dataset.profileForm==='photo') {
        const file=data.get('photo');if(file.size>3*1024*1024)throw new Error('Выбери фото до 3 МБ.');
        const body=new FormData();body.append('file',file);s.user=await request('/users/me/avatar',{method:'PUT',body});
        photoDirty=false;
        form.reset();
        form.querySelector('[data-photo-name]').textContent='Файл ещё не выбран';
        document.querySelectorAll('[name=avatar_kind]').forEach(input=>input.checked=false);
        if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null;}
      }else{const body={full_name:data.get('full_name'),school:data.get('school')||null,city:data.get('city')||null,region:data.get('region')||null,grade:data.get('grade')?Number(data.get('grade')):null};if(form.elements.guardian_name){body.guardian_name=data.get('guardian_name').trim();body.guardian_email=data.get('guardian_email').trim();body.guardian_consent=data.get('guardian_consent')==='on';}if(data.get('avatar_kind'))body.avatar_kind=data.get('avatar_kind');s.user=await request('/users/me',{method:'PATCH',body});}
      if(form.dataset.profileForm==='details') {
        detailsDirty=false;
        const consent=form.querySelector('[name=guardian_consent]');
        if(consent){consent.checked=false;consent.required=false;}
      }
      setSession({...getSession(),user:s.user});await photo();
      if(!photoDirty)document.querySelector('.profile-avatar')?.replaceWith(avatarNode('profile-avatar'));
      message.textContent='Сохранено.';
      ui.toast(form.dataset.profileForm==='photo'?'Фотография сохранена.':'Профиль сохранён.');
    }catch(error){message.textContent=error.message;}finally{
      busy=false;controls.forEach((control,i)=>control.disabled=disabled[i]);
      if(form.dataset.profileForm==='photo')button.disabled=!form.querySelector('[type=file]').files.length;
    }
  }
  function avatarNode(className){const template=document.createElement('template');template.innerHTML=avatar(s,className);return template.content.firstElementChild;}
  function preview(input){
    const form=input.closest('form'),file=input.files[0],message=form.querySelector('.form-message');
    if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null;}
    message.textContent='';
    if(file && (file.size>3*1024*1024 || !/\.(jpe?g|png|webp)$/i.test(file.name))){message.textContent='Выбери JPG, PNG или WebP размером до 3 МБ.';input.value='';}
    const selected=input.files[0];form.querySelector('[data-photo-name]').textContent=selected?selected.name:'Файл ещё не выбран';
    photoDirty=Boolean(selected);
    form.querySelector('[type=submit]').disabled=!selected;
    if(selected){previewUrl=URL.createObjectURL(selected);document.querySelector('.profile-avatar img').src=previewUrl;message.textContent='Предпросмотр. Нажми «Сохранить фотографию», чтобы обновить аватар.';}
    else document.querySelector('.profile-avatar')?.replaceWith(avatarNode('profile-avatar'));
  }
  return {load,photo,afterRender,submit,preview,input:event=>{const form=event.target.closest('[data-profile-form=details]');if(!form)return;detailsDirty=true;const consent=form.elements.guardian_consent;if(consent)consent.required=form.elements.guardian_name.value.trim()!==(s.user.guardian_name||'')||form.elements.guardian_email.value.trim()!==(s.user.guardian_email||'');},canLeave:()=>{if(busy)return false;if(isDirty()&&!window.confirm('Уйти без сохранения профиля?'))return false;detailsDirty=false;photoDirty=false;return true;},reset:()=>{detailsDirty=false;photoDirty=false;busy=false;if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null;if(s.profilePhoto)URL.revokeObjectURL(s.profilePhoto);s.profilePhoto=null;},get busy(){return busy;},get dirty(){return isDirty();}};
}
