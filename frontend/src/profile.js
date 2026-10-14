import {request,getSession,setSession} from './api.js';
import {escapeHtml as e,heading,icon} from './ui.js';
import {geographyFields} from './geography.js';

export function avatar(s,className='account-avatar') {
  const src=s.user?.avatar_kind==='photo' && s.profilePhoto ? s.profilePhoto : s.user?.avatar_kind==='sakha'?'/assets/sakha-bear.png':'/assets/arctic-bear.png';
  return `<span class="${className}"><img src="${e(src)}" alt="Аватар ${e(s.user?.full_name||'участника')}"></span>`;
}
export function profileView(s) {
  const u=s.user;
  return `${heading('Настройки профиля','Проверь данные для участия и сертификатов. Изменения имени не переоформляют документы, уже выданные ранее.')}<div class="profile-layout"><section class="panel"><form data-profile-form="details" class="project-form"><div class="form-field"><label for="profile-name">Фамилия, имя и отчество</label><input id="profile-name" name="full_name" required minlength="2" maxlength="200" autocomplete="name" value="${e(u.full_name)}"></div><div class="form-field"><label>Почта для входа</label><p class="profile-email">${e(u.email)} · ${u.email_verified?'подтверждена':'не подтверждена'}</p></div><div class="form-field"><label for="profile-school">Учебное заведение</label><input id="profile-school" name="school" maxlength="250" value="${e(u.school||'')}"></div>${geographyFields().replaceAll(' required','')}<div class="form-field"><label for="profile-grade">Класс</label><select id="profile-grade" name="grade"><option value="">Не указан</option>${Array.from({length:11},(_,i)=>`<option value="${i+1}" ${u.grade===i+1?'selected':''}>${i+1}</option>`).join('')}</select></div><fieldset class="avatar-options"><legend>Аватар без загрузки фото</legend>${[['bear','Белый мишка','/assets/arctic-bear.png'],['sakha','Мишка Саха','/assets/sakha-bear.png']].map(([kind,label,src])=>`<label><input type="radio" name="avatar_kind" value="${kind}" ${u.avatar_kind===kind?'checked':''}><img src="${src}" width="96" height="96" alt=""><span>${label}</span></label>`).join('')}</fieldset><div class="form-message" role="alert"></div><button class="button" type="submit">Сохранить профиль ${icon('check')}</button></form></section><aside class="stack"><section class="panel profile-photo-panel">${avatar(s,'profile-avatar')}<h2>Твой образ в кабинете</h2><p>Можно выбрать мишку или загрузить собственную фотографию. Фото доступно только после входа в твой аккаунт.</p><form data-profile-form="photo" class="project-form"><div class="form-field"><label for="profile-photo">Фотография</label><input class="photo-input" id="profile-photo" name="photo" type="file" accept="image/jpeg,image/png,image/webp" required><label for="profile-photo" class="photo-upload">${icon('upload')}<strong>Выбрать фотографию</strong><span data-photo-name>Файл ещё не выбран</span></label><span class="form-caption">JPG, PNG или WebP. До 3 МБ и 4096×4096 пикселей.</span></div><div class="form-message" role="alert"></div><button class="button secondary" type="submit" disabled>Сохранить фотографию</button></form></section><section class="field-guide"><h2>Почта и безопасность</h2><p>Для восстановления пароля используй проверенную почту. Смена аватара не влияет на тесты и проекты.</p><a class="text-link" href="/#forgot-password" data-route="forgot-password">Восстановление пароля ${icon('arrow')}</a></section></aside></div>`;
}
export function createProfile(s,ui) {
  let busy=false,dirty=false,previewUrl;
  async function photo(){if(s.profilePhoto){URL.revokeObjectURL(s.profilePhoto);s.profilePhoto=null;}if(s.user?.avatar_kind==='photo'){const blob=await request('/users/me/avatar',{blob:true});s.profilePhoto=URL.createObjectURL(blob);}}
  async function load(){s.user=await request('/users/me');await photo();}
  function afterRender(){if(s.route==='profile'&&document.querySelector('#region')){document.querySelector('#region').value=s.user.region||'';document.querySelector('#city').value=s.user.city||'';}}
  async function submit(form){
    if(busy||!form.reportValidity())return;
    const data=new FormData(form),button=form.querySelector('[type=submit]'),message=form.querySelector('.form-message');
    busy=true;button.disabled=true;message.textContent='Сохраняем…';
    try {
      if(form.dataset.profileForm==='photo') {
        const file=data.get('photo');if(file.size>3*1024*1024)throw new Error('Выбери фото до 3 МБ.');
        const body=new FormData();body.append('file',file);s.user=await request('/users/me/avatar',{method:'PUT',body});
      }else{const body={full_name:data.get('full_name'),school:data.get('school')||null,city:data.get('city')||null,region:data.get('region')||null,grade:data.get('grade')?Number(data.get('grade')):null};if(data.get('avatar_kind'))body.avatar_kind=data.get('avatar_kind');s.user=await request('/users/me',{method:'PATCH',body});}
      setSession({...getSession(),user:s.user});await photo();if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null;}dirty=false;ui.render();ui.toast('Профиль сохранён.');
    }catch(error){message.textContent=error.message;}finally{busy=false;button.disabled=false;}
  }
  function preview(input){
    const form=input.closest('form'),file=input.files[0],message=form.querySelector('.form-message');
    if(previewUrl){URL.revokeObjectURL(previewUrl);previewUrl=null;}
    message.textContent='';
    if(file && (file.size>3*1024*1024 || !/\.(jpe?g|png|webp)$/i.test(file.name))){message.textContent='Выбери JPG, PNG или WebP размером до 3 МБ.';input.value='';}
    const selected=input.files[0];form.querySelector('[data-photo-name]').textContent=selected?selected.name:'Файл ещё не выбран';
    form.querySelector('[type=submit]').disabled=!selected;
    if(selected){previewUrl=URL.createObjectURL(selected);document.querySelector('.profile-avatar img').src=previewUrl;message.textContent='Предпросмотр. Нажми «Сохранить фотографию», чтобы обновить аватар.';}
  }
  return {load,photo,afterRender,submit,preview,input:event=>{if(event.target.closest('[data-profile-form]'))dirty=true;},canLeave:()=>{if(busy)return false;if(dirty&&!window.confirm('Уйти без сохранения профиля?'))return false;dirty=false;return true;},reset:()=>{dirty=false;busy=false;if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=null;if(s.profilePhoto)URL.revokeObjectURL(s.profilePhoto);s.profilePhoto=null;},get busy(){return busy;},get dirty(){return dirty;}};
}
