"""Own profile photos: decode, resize and discard image metadata."""
import io
from uuid import uuid4
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.orm import Session
from app.config import settings
from app.db import get_db
from app.dependencies import get_current_user
from app.models import User
from app.auth_schemas import UserOutput

router = APIRouter(tags=['Accounts'])

@router.put('/users/me/avatar',response_model=UserOutput)
async def upload_avatar(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data=await file.read(3*1024*1024+1)
    if len(data)>3*1024*1024:
        raise HTTPException(413,'Фото должно быть не больше 3 МБ')
    try:
        image=Image.open(io.BytesIO(data))
        if image.format not in {'JPEG','PNG','WEBP'} or max(image.size)>4096 or min(image.size)<1:
            raise ValueError('Invalid image')
        image.load()
        image=ImageOps.exif_transpose(image).convert('RGB')
        image.info.clear()
        image.thumbnail((512,512))
    except (UnidentifiedImageError,ValueError,OSError,Image.DecompressionBombError):
        raise HTTPException(422,'Выбери корректное фото JPG, PNG или WebP до 4096×4096 пикселей')
    folder=settings.uploads_dir/'avatars'
    folder.mkdir(parents=True,exist_ok=True)
    name=uuid4().hex+'.webp'
    image.save(folder/name,'WEBP',quality=88)
    user.avatar_filename=name
    user.avatar_kind='photo'
    db.commit()
    return user

@router.get('/users/me/avatar')
def own_avatar(user: User = Depends(get_current_user)):
    if not user.avatar_filename:
        raise HTTPException(404,'Фото ещё не загружено')
    path=settings.uploads_dir/'avatars'/user.avatar_filename
    if not path.is_file():
        raise HTTPException(404,'Фото не найдено')
    return FileResponse(path,media_type='image/webp',headers={'Cache-Control':'private, no-store'})
