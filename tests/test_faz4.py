"""Gün bazlı kayıp, gece molası, ayrılmış koçluk ve hücre değişim kontrolleri."""
import unittest
from datetime import timedelta
import pandas as pd
from test_phase7 import Base
from test_planning import DAY,row,emp,demand
from ortak.calisma_alani_deposu import connect,save_keys,dumps
from ortak.statuler import defaults,meal_plan
from ortak.statu_gecmisi import ingest,suggested_shrinkage
from ortak.ajanda_servisi import save_week,rows,add_coaching
from ortak.kocluk_alanlari import init as init_openings,read,eligible
from ortak.mola_servisi import init as init_breaks,records

FUTURE=(pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None)+pd.Timedelta(days=9)).normalize()

class WeekdayShrinkageTests(Base):
 def test_same_clock_different_weekdays_preserved(self):
  monday=FUTURE-pd.Timedelta(days=FUTURE.weekday());saturday=monday+pd.Timedelta(days=5)
  self.s['published_shift_plan']=[row(day=d.date(),start='08:00',end='09:00') for d in [monday,saturday]];save_keys(self.s)
  ingest(self.s,[{'employee_id':'1','start':str(monday+pd.Timedelta(hours=8)),'end':str(monday+pd.Timedelta(hours=8,minutes=30)),'kind':'Mola'},{'employee_id':'1','start':str(saturday+pd.Timedelta(hours=8)),'end':str(saturday+pd.Timedelta(hours=8,minutes=10)),'kind':'Mola'}])
  table,total,_=suggested_shrinkage(self.s,monday.date(),saturday.date(),by_weekday=True)
  self.assertEqual(len(table),336);self.assertAlmostEqual(table.query('Slot==17 and `Haftanın günü`==0')['Shrinkage (%)'].iloc[0],100)
  self.assertAlmostEqual(table.query('Slot==17 and `Haftanın günü`==5')['Shrinkage (%)'].iloc[0],33.33)
  self.assertTrue(table.query('Slot==1')['Shrinkage (%)'].isna().all())
 def test_weekday_rules_affect_actual_staffing(self):
  from ortak.statuler import shrinkage_for
  rules={'slot_shrinkage':[{'start_slot':1,'end_slot':48,'rate':.3,'weekdays':[0]},{'start_slot':1,'end_slot':48,'rate':.1,'weekdays':[5]}]}
  self.assertEqual(shrinkage_for(rules,'2026-11-09',20),.3);self.assertEqual(shrinkage_for(rules,'2026-11-14',20),.1)

class StatusPlacementTests(Base):
 def setup_status(self):
  self.s['status_rules']=dict(defaults(),enabled=True,automatic=True,shrinkage_included=False,coaching_by_leader=True)
  cov=demand(slots=range(1,49));cov['İhtiyaç']=0.;cov['Atanan']=1.;cov['Eksik']=0.;cov['Fazla']=1.;return cov
 def test_night_excluded_counter_still_gets_sixty_minutes(self):
  cov=self.setup_status();cov['İhtiyaç']=1.;cov['Sayaca Dahil']=False;self.s['shift_rules']['night']['break_total_minutes']=60
  items,_,issues=meal_plan(self.s,[row(code='GECE',start='00:00',end='08:00')],cov,[emp()]);rest=[x for x in items if x['kind']=='Mola'];self.assertEqual(sum((pd.Timestamp(x['end'])-pd.Timestamp(x['start'])).total_seconds()/60 for x in rest),60);self.assertFalse(any('Mola:' in i['Sorun'] for i in issues))
 def test_adaptive_break_can_be_ten_minutes(self):
  cov=self.setup_status();rule=self.s['status_rules']['groups']['fulltime'];rule.update(meal_disabled=True,break_rules=[{'min_hours':0,'max_hours':24,'minutes':10}])
  items,_,_=meal_plan(self.s,[row()],cov,[emp()]);self.assertEqual(sum((pd.Timestamp(x['end'])-pd.Timestamp(x['start'])).total_seconds()/60 for x in items if x['kind']=='Mola'),10)
 def test_coaching_is_reserved_not_assigned_and_budgeted(self):
  cov=self.setup_status();items,out,_=meal_plan(self.s,[row()],cov,[emp()]);openings=[x for x in items if x['kind']=='Koçluk Alanı'];self.assertTrue(openings);self.assertFalse(any(x['kind']=='Koçluk' for x in items));self.assertAlmostEqual(out['Mola kaybı'].sum()*.5,sum((pd.Timestamp(x['end'])-pd.Timestamp(x['start'])).total_seconds()/3600 for x in items))

class CoachingOpeningTests(Base):
 def setUp(self):
  super().setUp();self.s['profile']={'position':'tl','username':'lead','full_name':'Lead','employee_id':'90'};self.day=FUTURE.date();self.a=FUTURE+pd.Timedelta(hours=12);self.s['published_shift_plan']=[row('1',day=self.day),row('2',day=self.day)];self.s['sp_staffing_result_df']=demand(slots=range(1,49)).assign(Tarih=self.day,**{'Planlanan Agent':0});self.s['status_rules']=dict(defaults(),enabled=True,shrinkage_included=False);save_keys(self.s);init_breaks(self.s['workspace_db_path']);init_openings(self.s['workspace_db_path'])
  self.week=FUTURE-pd.Timedelta(days=FUTURE.weekday());save_week(self.s,self.week,[{'Tarih':self.day,'Çalışıyor':True,'Başlangıç':'08:00','Bitiş':'17:00'}]);self.slot={'employee_id':'1','date':str(self.day),'kind':'Koçluk Alanı','start':str(self.a),'end':str(self.a+pd.Timedelta(minutes=15))}
  with connect(self.s['workspace_db_path']) as db:db.execute('INSERT INTO coaching_openings VALUES(?,?,?,?,?)',('opening','pub','1','Açık',dumps(self.slot)))
 def test_claim_once_and_show_only_after_leader_assignment(self):
  self.assertFalse(records(self.s));self.assertEqual(len(eligible(self.s,'1')),1)
  add_coaching(self.s,'1',self.a,15,opening_id='opening');self.assertFalse(read(self.s));self.assertEqual(records(self.s)[0]['kind'],'Koçluk')
  with self.assertRaises(ValueError):add_coaching(self.s,'1',self.a,15,opening_id='opening')
 def test_withdraw_removes_linked_coaching_and_agenda(self):
  from ortak.yayin_servisi import withdraw,init_publications
  add_coaching(self.s,'1',self.a,15,opening_id='opening');init_publications(self.s['workspace_db_path']);batch={'id':'pub','start':str(self.day),'end':str(self.day),'rows':self.s['published_shift_plan'],'languages':['tr']}
  with connect(self.s['workspace_db_path']) as db:db.execute('INSERT INTO publication_batches VALUES(?,?,?,?)',('pub',str(self.a),'active',dumps(batch)))
  withdraw(self.s,batch);self.assertFalse(records(self.s));self.assertFalse(any(r['kind']=='Koçluk' for r in rows(self.s)))
 def test_cannot_claim_other_person(self):
  with self.assertRaises(ValueError):add_coaching(self.s,'2',self.a,15,opening_id='opening')
  self.assertEqual(len(read(self.s)),1);self.assertFalse(records(self.s))
 def test_week_edit_keeps_scheduled_meetings_atomic(self):
  add_coaching(self.s,'1',self.a,15,opening_id='opening')
  with self.assertRaises(ValueError):save_week(self.s,self.week,[])
  self.assertTrue(any(r['kind']=='Çalışma' for r in rows(self.s)))

class PublishedGridTests(unittest.TestCase):
 def test_parser_and_invalid_times(self):
  from ortak.yayin_hucre_duzenleyici import parse_cell
  old={'employee_id':'1','date':'2026-11-16','shift_code':'MESAI','start':'08:00','end':'17:00'}
  self.assertEqual(parse_cell('OFF',old)['start'],None);self.assertEqual(parse_cell('Gece 00:00–08:00',old)['shift_code'],'GECE');self.assertEqual(parse_cell('10:00-17:00',old)['start'],'10:00')
  for text in ['','10:00–10:00','25:00–26:00','rastgele']:
   with self.assertRaises(ValueError):parse_cell(text,old)
 def test_signed_matrix_retains_excess(self):
  from ortak.planlama_gorunumu import shortage_matrix,styled_shortage_matrix
  cov=demand();cov['Eksik']=0.;cov['Fazla']=2.;matrix=shortage_matrix(cov,DAY,signed=True);self.assertEqual(matrix.min().min(),-2);self.assertIn('+2.00',styled_shortage_matrix(matrix).to_html())
