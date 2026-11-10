# Ortak / Kurumsal Baglanti — bu ekranın / servisin uygulama kodu.
"""Kurumsal Bağlantı — HTTP adaptörleri; gerçek adresler yalnızca sunucu ortamından."""
import os
from urllib.parse import urlparse
import requests

ROLE_MAP={'agent':'agent','müşteri temsilcisi':'agent','mt':'agent','tl':'tl','takım lideri':'tl','manager':'manager','yönetici':'manager','wfm':'wfm','planlama':'wfm','moderator':'moderator','director':'moderator','müdür':'moderator','planning_manager':'planning_manager','planlama yöneticisi':'planning_manager'}


def _url(name):
    value=os.environ.get(name,'').strip();parsed=urlparse(value)
    if not value:raise ValueError(name+' yapılandırılmamış.')
    if parsed.username or parsed.password or not parsed.hostname:raise ValueError('Bağlantı adresi geçersiz; sırları URL içine yazmayın.')
    if parsed.scheme!='https' and not(parsed.scheme=='http' and parsed.hostname in {'localhost','127.0.0.1'}):raise ValueError('Kurumsal bağlantıda HTTPS gerekli.')
    return value


def _json(response):
    response.raise_for_status();return response.json()


def normalize_person(row):
    result={k:row.get(k) for k in ('team_lead','manager','location','work_type','language','employment_start','employment_end','company','gender')};result['username']=str(row.get('username') or row.get('kullanici_adi') or '').strip()
    result['sicil_no']=str(row.get('sicil_no') or row.get('registry_no') or row.get('employee_id') or '').strip()
    result['employee_id']=str(row.get('employee_id') or result['sicil_no'])
    result['full_name']=str(row.get('full_name') or row.get('ad_soyad') or '').strip()
    result['position']=ROLE_MAP.get(str(row.get('position') or row.get('rol') or 'agent').strip().replace('İ','i').lower())
    if not all(result.get(k) for k in ('username','sicil_no','employee_id','full_name','position')):raise ValueError('Kurumsal personelde sicil, kullanıcı adı, ad soyad ve geçerli rol gerekli.')
    result['company']=str(row.get('company') or row.get('sirket') or '')
    result['is_active']=str(row.get('is_active',True)).strip().lower() not in {'0','false','no','pasif'}
    result['is_superuser']=result['position'] in {'moderator','wfm','manager'}
    return result


class KurumsalPersonelSaglayici:
    def list_people(self):
        token=os.environ.get('WFM_DIRECTORY_TOKEN');headers={'Authorization':'Bearer '+token} if token else {}
        response=requests.get(_url('WFM_PERSONNEL_API_URL'),headers=headers,timeout=15,allow_redirects=False)
        payload=_json(response);rows=payload.get('items') if isinstance(payload,dict) else payload
        if not isinstance(rows,list):raise ValueError('Personel servisi items listesi döndürmeli.')
        result=[normalize_person(r) for r in rows]
        if any(len({r[field] for r in result})!=len(result) for field in ('sicil_no','username','employee_id')):raise ValueError('Sicil ve kullanıcı adları benzersiz olmalı.')
        return result


class KurumsalKimlikSaglayici:
    def authenticate(self,username,password):
        login_url=_url('WFM_AUTH_API_URL');me_url=_url('WFM_AUTH_USERINFO_URL')
        response=requests.post(login_url,json={'username':username,'password':password},timeout=15,allow_redirects=False)
        data=_json(response);token=data.get('access_token')
        if not token:raise ValueError('Kurumsal kimlik servisi erişim belirteci döndürmedi.')
        person=normalize_person(_json(requests.get(me_url,headers={'Authorization':'Bearer '+token},timeout=15,allow_redirects=False)))
        if not person.get('is_active',True):raise ValueError('Kurumsal hesap aktif değil.')
        person.pop('password',None);person.pop('password_hash',None);return person


def connection_status():
    return [{'Alan':'Personel listesi','Mod':'Kurumsal API' if os.environ.get('WFM_PERSONNEL_API_URL') else 'Yerel demo','Hazır':bool(os.environ.get('WFM_PERSONNEL_API_URL'))},
            {'Alan':'Kimlik doğrulama','Mod':os.environ.get('WFM_IDENTITY_MODE','demo'),'Hazır':all(os.environ.get(k) for k in ['WFM_AUTH_API_URL','WFM_AUTH_USERINFO_URL','WFM_JWT_SECRET'])},
            {'Alan':'Günlük / 30 dk çağrılar','Mod':'/actuals/intervals + SQLite kayıt adaptörü','Hazır':True}]
