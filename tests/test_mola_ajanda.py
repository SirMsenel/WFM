"""Tam otomatik hak dağıtımı, ortak kontenjan ve atomik haftalık koçluk sınırı."""
import copy,unittest
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from test_phase7 import Base
from test_planning import DAY,row,emp,demand
from ortak.statuler import defaults,meal_plan
from ortak.statu_haklari import balance,assert_complete
from ortak.calisma_alani_deposu import connect,dumps,save_keys
from ortak.ajanda_servisi import add_work,add_coaching
from ortak.kocluk_alanlari import init as init_pool,eligible,read
from ortak.mola_servisi import init as init_breaks,records

class FullAllocationTests(Base):
 def setup_plan(self,count=3,need=0):
  self.s['status_rules']=dict(defaults(),enabled=True,automatic=True,coaching_by_leader=True,shrinkage_included=False)
  people=[emp(str(i)) for i in range(1,count+1)];plan=[row(str(i)) for i in range(1,count+1)];cov=demand(slots=range(1,49));cov['İhtiyaç']=need;cov['Atanan']=count;cov['Eksik']=0.;cov['Fazla']=count-need
  return plan,cov,people
 def test_full_breaks_even_if_capacity_causes_shortage(self):
  plan,cov,people=self.setup_plan(1,1);items,out,issues=meal_plan(self.s,plan,cov,people);rights=balance(self.s,plan,people,items)
  self.assertFalse(any(r['Eksik (dk)'] for r in rights));self.assertGreater(out.Eksik.sum(),0);self.assertFalse(any(x['kind']=='Koçluk Alanı' for x in items));self.assertFalse(issues)
 def test_impossible_right_is_hard_error_and_cannot_publish(self):
  plan,cov,people=self.setup_plan(1,0);plan[0].update(start='08:00',end='10:00');items,out,issues=meal_plan(self.s,plan,cov,people)
  self.assertTrue(any(i['severity']=='error' and 'dakika eksik' in i['Sorun'] for i in issues));result={'plan':plan,'staff':people,'breaks':items}
  with self.assertRaisesRegex(ValueError,'hakkı tamamlanmalı'):assert_complete(self.s,result)
  from ortak.yayin_servisi import publish_plan
  from ortak.yayin_onaylari import submit
  for fn in [publish_plan,submit]:
   with self.assertRaisesRegex(ValueError,'hakkı tamamlanmalı'):fn(self.s,result)
 def test_full_right_not_dependent_on_legacy_automatic_flag(self):
  plan,cov,people=self.setup_plan(1,0);self.s['status_rules']['automatic']=False;items,_,_=meal_plan(self.s,plan,cov,people);self.assertFalse(any(x['Eksik (dk)'] for x in balance(self.s,plan,people,items)))
 def test_pool_shared_reserve_kept_and_no_exact_assignment(self):
  plan,cov,people=self.setup_plan(3,0);items,out,issues=meal_plan(self.s,plan,cov,people);pools=[x for x in items if x['kind']=='Koçluk Alanı']
  self.assertTrue(pools);self.assertTrue(all(r['employee_id']=='*' and len(r['eligible_employee_ids'])>1 for r in pools));self.assertGreater(out['Operasyon rezervi'].sum(),0);self.assertFalse(any(x['kind']=='Koçluk' for x in items));self.assertFalse(any(x['Eksik (dk)'] for x in balance(self.s,plan,people,items)))
  self.assertAlmostEqual(out['Mola kaybı'].sum()*.5,sum((pd.Timestamp(x['end'])-pd.Timestamp(x['start'])).total_seconds()/3600*int(x.get('capacity',1)) for x in items))
 def test_pool_also_respects_explicit_erlang_net_need(self):
  plan,cov,people=self.setup_plan(3,1);self.s['status_rules']['shrinkage_included']=True;cov['Net Agent']=2.;items,out,_=meal_plan(self.s,plan,cov,people);self.assertFalse(any(x['kind']=='Koçluk Alanı' for x in items))
 def test_pool_windows_do_not_include_meal_or_rest_for_candidates(self):
  plan,cov,people=self.setup_plan();items,_,_=meal_plan(self.s,plan,cov,people)
  for pool in [r for r in items if r['kind']=='Koçluk Alanı']:
   for eid in pool['eligible_employee_ids']:
    self.assertFalse(any(r['kind'] in {'Yemek','Mola'} and r['employee_id']==eid and pd.Timestamp(r['start'])<pd.Timestamp(pool['end']) and pd.Timestamp(pool['start'])<pd.Timestamp(r['end']) for r in items))
 def test_manual_break_is_refused_when_automatic(self):
  from ortak.mola_servisi import request
  self.s['status_rules']={'automatic':True}
  with self.assertRaisesRegex(ValueError,'elle mola seçimi kapalı'):request(self.s,pd.Timestamp(DAY),15)
 def test_night_receives_full_hour_with_first_last_hour_protected(self):
  plan,cov,people=self.setup_plan(1,1);plan[0].update(shift_code='GECE',start='00:00',end='08:00');cov['Sayaca Dahil']=False;items,_,issues=meal_plan(self.s,plan,cov,people);rest=[r for r in items if r['kind']=='Mola']
  self.assertEqual(sum((pd.Timestamp(x['end'])-pd.Timestamp(x['start'])).total_seconds()/60 for x in rest),60);self.assertTrue(all(pd.Timestamp(x['start'])>=pd.Timestamp(DAY)+pd.Timedelta(hours=1) and pd.Timestamp(x['end'])<=pd.Timestamp(DAY)+pd.Timedelta(hours=7) for x in rest));self.assertFalse(issues)

class WeeklyCoachingTests(Base):
 def setUp(self):
  super().setUp();self.day=(pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None)+pd.Timedelta(days=14)).normalize();self.day-=pd.Timedelta(days=self.day.weekday())
  self.s['profile']={'position':'tl','username':'lead','full_name':'Lead','employee_id':'90'};self.s['published_shift_plan']=[row(str(i),day=self.day.date()) for i in range(1,4)];self.s['sp_staffing_result_df']=demand(slots=range(1,49),count=0).assign(Tarih=self.day.date());self.s['status_rules']=dict(defaults(),enabled=True,automatic=True,operation_reserve_rate=0.,shrinkage_included=False);save_keys(self.s);init_pool(self.s['workspace_db_path']);init_breaks(self.s['workspace_db_path']);add_work(self.s,self.day+pd.Timedelta(hours=8),self.day+pd.Timedelta(hours=17))
  self.a=self.day+pd.Timedelta(hours=12);self.b=self.day+pd.Timedelta(hours=13)
  with connect(self.s['workspace_db_path']) as db:
   for ident,t in [('pool-a',self.a),('pool-b',self.b)]:
    payload={'pool':True,'employee_id':'*','eligible_employee_ids':['1','2','3'],'languages':['tr'],'date':str(t.date()),'start':str(t),'end':str(t+pd.Timedelta(minutes=15)),'kind':'Koçluk Alanı','operation_reserve_count':0.};db.execute('INSERT INTO coaching_openings VALUES(?,?,?,?,?)',(ident,'pub','*','Açık',dumps(payload)))
 def test_second_same_week_refused_and_hidden(self):
  add_coaching(self.s,'1',self.a,15,opening_id='pool-a');self.assertFalse(eligible(self.s,'1'))
  with self.assertRaisesRegex(ValueError,'aynı hafta'):add_coaching(self.s,'1',self.b,15,opening_id='pool-b')
  self.assertEqual(len(read(self.s)),1);self.assertEqual(len(records(self.s)),1)
 def test_new_calendar_week_allows_new_meeting(self):
  add_coaching(self.s,'1',self.a,15,opening_id='pool-a');future=self.day+pd.Timedelta(days=7);time=future+pd.Timedelta(hours=12);self.s['published_shift_plan']+=[row(str(i),day=future.date()) for i in range(1,4)];self.s['sp_staffing_result_df']=pd.concat([self.s['sp_staffing_result_df'],demand(slots=range(1,49),count=0).assign(Tarih=future.date())],ignore_index=True);save_keys(self.s);add_work(self.s,future+pd.Timedelta(hours=8),future+pd.Timedelta(hours=17))
  with connect(self.s['workspace_db_path']) as db:
   payload={'pool':True,'employee_id':'*','eligible_employee_ids':['1','2'],'languages':['tr'],'date':str(future.date()),'start':str(time),'end':str(time+pd.Timedelta(minutes=15)),'kind':'Koçluk Alanı','operation_reserve_count':0.};db.execute('INSERT INTO coaching_openings VALUES(?,?,?,?,?)',('pool-next','pub2','*','Açık',dumps(payload)))
  add_coaching(self.s,'1',time,15,opening_id='pool-next');self.assertEqual(len(records(self.s)),2)
 def test_enabled_rule_allows_second_but_monthly_limit_remains(self):
  self.s['status_rules']['groups']['fulltime']['coaching_multiple_per_week']=True;save_keys(self.s);add_coaching(self.s,'1',self.a,15,opening_id='pool-a');self.assertEqual(len(eligible(self.s,'1')),1);add_coaching(self.s,'1',self.b,15,opening_id='pool-b');self.assertEqual(len(records(self.s)),2)
 def test_monthly_cap_is_not_removed_by_multiple_option(self):
  self.s['status_rules']['groups']['fulltime'].update(coaching_multiple_per_week=True,coaching_monthly_minutes=15);save_keys(self.s);add_coaching(self.s,'1',self.a,15,opening_id='pool-a')
  with self.assertRaisesRegex(ValueError,'aylık'):add_coaching(self.s,'1',self.b,15,opening_id='pool-b')
 def test_contingent_can_be_used_by_another_eligible_person(self):
  add_coaching(self.s,'2',self.a,15,opening_id='pool-a');self.assertEqual(str(records(self.s)[0]['employee_id']),'2')
 def test_two_leaders_cannot_bypass_weekly_limit(self):
  other=copy.deepcopy(self.s);other['profile']={**other['profile'],'username':'lead2','employee_id':'91'};add_work(other,self.day+pd.Timedelta(hours=8),self.day+pd.Timedelta(hours=17))
  def assign(args):
   s,t,ident=args
   try:return add_coaching(s,'1',t,15,opening_id=ident)
   except ValueError:return None
  with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(assign,[(copy.deepcopy(self.s),self.a,'pool-a'),(other,self.b,'pool-b')]))
  self.assertEqual(sum(bool(r) for r in result),1);self.assertEqual(len(records(self.s)),1)
 def test_capacity_decrements_without_assigning_entire_pool(self):
  with connect(self.s['workspace_db_path']) as db:
   payload=__import__('ortak.calisma_alani_deposu',fromlist=['loads']).loads(db.execute("SELECT payload FROM coaching_openings WHERE id='pool-a'").fetchone()[0]);payload.update(capacity=2,remaining_capacity=2);db.execute("UPDATE coaching_openings SET payload=? WHERE id='pool-a'",(dumps(payload),))
  add_coaching(self.s,'1',self.a,15,opening_id='pool-a');remaining=next(x for x in read(self.s) if x['id']=='pool-a');self.assertEqual(remaining['remaining_capacity'],1)
  other=copy.deepcopy(self.s);other['profile']={**other['profile'],'username':'lead2','employee_id':'91'};add_work(other,self.day+pd.Timedelta(hours=8),self.day+pd.Timedelta(hours=17));add_coaching(other,'2',self.a,15,opening_id='pool-a');self.assertFalse(any(x['id']=='pool-a' for x in read(self.s)));self.assertEqual(len(records(self.s)),2)
 def test_group_setting_change_is_read_again_at_assignment(self):
  self.s['status_rules']['groups']['fulltime']['coaching_multiple_per_week']=True;save_keys(self.s);stale=copy.deepcopy(self.s);add_coaching(self.s,'1',self.a,15,opening_id='pool-a');self.s['status_rules']['groups']['fulltime']['coaching_multiple_per_week']=False;save_keys(self.s)
  with self.assertRaisesRegex(ValueError,'aynı hafta'):add_coaching(stale,'1',self.b,15,opening_id='pool-b')
