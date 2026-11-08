"""Kurumsal mod, eski dosya uyumu ve talepten yayınlanan değişim işlemleri."""
import copy,os,sqlite3,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
from datetime import timedelta
import pandas as pd
from test_round5 import make_state
from test_planning import DAY,row
from ortak.calisma_alani_deposu import connect,save_keys,loads,put_request
from ortak.talep_servisi import create_request,act
from ortak.kurumsal_baglanti import KurumsalPersonelSaglayici,KurumsalKimlikSaglayici

class IntegrationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name);self.s=make_state(self.path/'w.db',self.path/'auth.db')
 def tearDown(self):self.temp.cleanup()
 def response(self,value):return Mock(json=Mock(return_value=value),raise_for_status=Mock())
 def test_corporate_bootstrap_creates_no_demo_records(self):
  from ortak.ornek_veri import bootstrap
  with patch.dict(os.environ,{'WFM_DEMO_MODE':'false'}):bootstrap(self.s,self.s['workspace_db_path'])
  self.assertTrue(self.s['production_mode']);self.assertEqual(self.s['cf_source'],'Çağrı Veritabanı')
  with connect(self.s['workspace_db_path']) as db:
   self.assertEqual(db.execute('SELECT COUNT(*) FROM calls_daily').fetchone()[0],0)
   self.assertEqual(db.execute('SELECT COUNT(*) FROM requests').fetchone()[0],0)
  self.assertNotIn('cf_model_candidates',self.s)
 def test_directory_contract_aliases_and_duplicates(self):
  person={'sicil_no':'S10','kullanici_adi':'user','ad_soyad':'Name','rol':'Planlama'}
  with patch.dict(os.environ,{'WFM_PERSONNEL_API_URL':'https://intranet.example/personnel'}),patch('ortak.kurumsal_baglanti.requests.get',return_value=self.response({'items':[person]})) as get:
   result=KurumsalPersonelSaglayici().list_people();self.assertEqual(result[0]['position'],'wfm');self.assertEqual(result[0]['employee_id'],'S10');self.assertFalse(get.call_args.kwargs['allow_redirects'])
   get.return_value=self.response({'items':[person,person]})
   with self.assertRaises(ValueError):KurumsalPersonelSaglayici().list_people()
 def test_identity_token_is_used_for_verified_profile_but_not_returned(self):
  env={'WFM_AUTH_API_URL':'https://intranet.example/login','WFM_AUTH_USERINFO_URL':'https://intranet.example/me'}
  with patch.dict(os.environ,env),patch('ortak.kurumsal_baglanti.requests.post',return_value=self.response({'access_token':'SECRET'})),patch('ortak.kurumsal_baglanti.requests.get',return_value=self.response({'sicil_no':'S1','username':'u','full_name':'N','position':'agent','password':'hidden'})) as get:
   result=KurumsalKimlikSaglayici().authenticate('u','p');self.assertNotIn('password',result);self.assertNotIn('access_token',result);self.assertEqual(get.call_args.kwargs['headers']['Authorization'],'Bearer SECRET')
 def test_remote_directory_rejects_insecure_url(self):
  with patch.dict(os.environ,{'WFM_PERSONNEL_API_URL':'http://intranet.example/personnel'}):
   with self.assertRaises(ValueError):KurumsalPersonelSaglayici().list_people()
 def test_old_imports_resolve_to_same_module_for_patch_compatibility(self):
  import backend,sunucu,core.request_service,ortak.talep_servisi,modules.shift_planing.engine,modules.vardiya_plani.vardiya_motoru
  self.assertIs(backend,sunucu);self.assertIs(core.request_service,ortak.talep_servisi);self.assertIs(modules.shift_planing.engine,modules.vardiya_plani.vardiya_motoru)
 def swap_request(self):
  self.s['published_shift_plan']=[row('1',DAY,'OFF',None,None),row('2',DAY,'WORK','08:00','17:00'),row('1',DAY+timedelta(days=1),'WORK','08:00','17:00'),row('2',DAY+timedelta(days=1),'OFF',None,None)];save_keys(self.s)
  self.s['profile']={'position':'agent','employee_id':'1','username':'u1','full_name':'Person A','team_lead':'Lead'}
  req=create_request(self.s,{'type':'Vardiya Değişim Talebi','start_date':str(DAY),'end_date':str(DAY+timedelta(days=1)),'targets':[self.s['employees_cache'][1]],'note':'Dengeli OFF değişimi','swap_dates':[str(DAY),str(DAY+timedelta(days=1))]})
  self.s['profile']={'position':'tl','username':'lead','full_name':'Lead'};req=act(self.s,req,'forward')
  self.s['profile']={'position':'wfm','username':'planner'};return req
 def test_approved_swap_changes_published_rows_with_audit_in_one_transaction(self):
  req=self.swap_request();new=act(self.s,req,'apply')
  self.assertEqual(new['status'],'Uygulandı');self.assertTrue(new['change_id'])
  self.assertEqual(next(r for r in self.s['published_shift_plan'] if r['employee_id']=='1' and r['date']==str(DAY))['shift_code'],'WORK')
  with connect(self.s['workspace_db_path']) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM shift_change_batches').fetchone()[0],1)
 def test_stale_request_rolls_back_published_change(self):
  req=self.swap_request();old=copy.deepcopy(self.s['published_shift_plan']);changed=dict(req);changed['events']=req['events']+[{'action':'Another reviewer'}];put_request(changed,req['version'],self.s['workspace_db_path'])
  with self.assertRaises(ValueError):act(self.s,req,'apply')
  self.assertEqual(self.s['published_shift_plan'],old)
  with connect(self.s['workspace_db_path']) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM shift_change_batches').fetchone()[0],0)
 def test_agent_cannot_submit_sick_report(self):
  self.s['profile']={'position':'agent','employee_id':'1','username':'u1'}
  with self.assertRaises(ValueError):create_request(self.s,{'type':'Rapor Bildirimi','start_date':str(DAY)})
 def test_team_leader_submits_report_on_behalf_of_team_only(self):
  new=create_request(self.s,{'type':'Rapor Bildirimi','start_date':str(DAY),'report_employee_id':'1'})
  self.assertEqual(new['queue'],'WFM');self.assertEqual(new['submitted_by'],'lead');self.assertEqual(str(new['employee_id']),'1')
  with self.assertRaises(ValueError):create_request(self.s,{'type':'Rapor Bildirimi','start_date':str(DAY),'report_employee_id':'3'})

if __name__=='__main__':unittest.main()
