import io
from PIL import Image
from test_auth import registration

API='/api/v1'

def test_registration_city_and_school_grades(client):
    result=client.post(API+'/auth/register',json=registration(city='Нерюнгри',region='Республика Саха (Якутия)',grade=11))
    assert result.status_code==201
    assert result.json()['user']['city']=='Нерюнгри'
    rejected=client.post(API+'/auth/register',json=registration(email='grade12@example.com',grade=12))
    assert rejected.status_code==422

def test_presets_and_profile_persist(client,auth_headers):
    headers=auth_headers('participant')
    result=client.patch(API+'/users/me',headers=headers,json={'avatar_kind':'sakha','city':'Нерюнгри'})
    assert result.status_code==200
    assert client.get(API+'/users/me',headers=headers).json()['avatar_kind']=='sakha'
    assert result.json()['city']=='Нерюнгри'
    assert client.patch(API+'/users/me',headers=headers,json={'avatar_kind':None}).status_code==422

def test_avatar_private_resized_and_not_metadata(client,auth_headers):
    raw=io.BytesIO()
    Image.new('RGB',(1200,900),'white').save(raw,'PNG')
    headers=auth_headers('participant')
    result=client.put(API+'/users/me/avatar',headers=headers,files={'file':('photo.png',raw.getvalue(),'image/png')})
    assert result.status_code==200
    assert result.json()['avatar_kind']=='photo'
    assert 'avatar_filename' not in result.json()
    photo=client.get(API+'/users/me/avatar',headers=headers)
    assert photo.status_code==200
    assert max(Image.open(io.BytesIO(photo.content)).size)<=512
    assert client.get(API+'/users/me/avatar').status_code==401
    assert client.get(API+'/users/me/avatar',headers=auth_headers('expert')).status_code==404
    assert client.put(API+'/users/me/avatar',headers=headers,files={'file':('fake.png',b'not an image','image/png')}).status_code==422
