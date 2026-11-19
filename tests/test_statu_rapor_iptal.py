"""Kişi-adet ölçümü, tarihsel hak sürümü ve operasyonel iptal güvenliği."""
import copy,unittest
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
from test_phase7 import Base
from test_planning import row,emp,DAY,demand
from ortak.statuler import defaults,meal_plan
from ortak.statu_kapasite_raporu import fulfillment,slot_capacity,person_headcounts,capacity_visible,capacity_openings,entitlement_snapshot,published_entitlements,associate_items
from ortak.calisma_alani_deposu import connect,dumps,loads,save_keys
from ortak.statu_iptalleri import init,cancel_targets,events,targets
from ortak.mola_servisi import records

class PreferredBreakTests(unittest.TestCase):
 def test_ten_minutes_preferred_and_shorter_remainder_preserves_total(self):
  for hours in [4,4.5,5,7]:
   with self.subTest(hours=hours):
    state={'status_rules':dict(defaults(),enabled=True,automatic=True,coaching_by_leader=True)};cov=demand(slots=range(1,49));cov['İhtiyaç']=0;cov['Atanan']=1;cov['Eksik']=0;cov['Fazla']=1;end=pd.Timestamp(DAY)+pd.Timedelta(hours=8+hours);plan=[row(start='08:00',end=end.strftime('%H:%M'))];items,_,issues=meal_plan(state,plan,cov,[emp(group='akademi')]);dur=[(pd.Timestamp(x['end'])-pd.Timestamp(x['start'])).total_seconds()/60 for x in items if x['kind']=='Mola'];self.assertEqual(sum(dur),30);self.assertTrue(all(x<=10 for x in dur));self.assertIn(10,dur);self.assertFalse(issues)

class CountTests(unittest.TestCase):
 def item(self,eid='1',kind='Mola',a='10:00',b='10:10',**kw):return dict(employee_id=eid,kind=kind,date='2026-11-12',start='2026-11-12 '+a,end='2026-11-12 '+b,**kw)
 def test_three_fragments_are_one_person_and_full_thirty_minutes(self):
  rights=[{'employee_id':'1','date':'2026-11-12','kind':'Mola','required_minutes':30}];items=[self.item(a='10:00',b='10:10'),self.item(a='11:00',b='11:10'),self.item(a='12:00',b='12:10')];r=fulfillment(rights,items,'2026-11-12','2026-11-12')['Mola'];self.assertEqual((r['required_people'],r['given_people'],r['complete_people'],r['given_minutes']),(1,1,1,30))
 def test_partial_and_duplicate_records_do_not_complete_right(self):
  rights=[{'employee_id':'1','date':'2026-11-12','kind':'Mola','required_minutes':30}];r=fulfillment(rights,[self.item(),self.item()], '2026-11-12','2026-11-12')['Mola'];self.assertEqual(r['given_people'],1);self.assertEqual(r['given_minutes'],10);self.assertEqual(r['missing_minutes'],20);self.assertEqual(r['complete_people'],0)
 def test_headcounts_are_people_not_half_hour_equivalents(self):
  items=[self.item(),self.item(a='10:20',b='10:25'),self.item('2',a='10:15',b='10:25')];table=person_headcounts(items,'2026-11-12','2026-11-12');self.assertEqual(table.at[pd.Timestamp('2026-11-12 10:00'),'Mola'],2);self.assertEqual(table.at[pd.Timestamp('2026-11-12 10:30'),'Mola'],0)
 def test_capacity_is_fifteen_minute_seats_not_simultaneous_headcount(self):
  pools=[self.item('*','Koçluk Alanı',a='10:00',b='10:15',capacity=3,remaining_capacity=1,cancelled_capacity=1),self.item('*','Koçluk Alanı',a='10:15',b='10:30',capacity=2,remaining_capacity=2)]
  table=slot_capacity([],pools,'2026-11-12');r=table.loc[pd.Timestamp('2026-11-12 10:00')];self.assertEqual(r['Toplam koçluk kontenjanı'],5);self.assertEqual(r['Açık koçluk kontenjanı'],3);self.assertEqual(r['İptal koçluk kontenjanı'],1);self.assertEqual(r['Atanmış koçluk kontenjanı'],1)
 def test_roles_exclude_team_leader_and_agent(self):
  for role in ['tl','agent']:self.assertFalse(capacity_visible({'position':role}));self.assertEqual(capacity_openings({'profile':{'position':role},'workspace_db_path':'/not/a/database'},'2026-11-12','2026-11-12',{'1'}),[])
  for role in ['wfm','manager','assistant_manager','planning_manager','moderator']:self.assertTrue(capacity_visible({'position':role}))
 def test_overnight_actuals_link_to_original_shift(self):
  rows=[row(day='2026-11-12',start='22:00',end='07:00')];item={'employee_id':'1','kind':'Mola','start':'2026-11-13 02:00','end':'2026-11-13 02:10'};self.assertEqual(associate_items([item],rows)[0]['date'],'2026-11-12')
 def test_unknown_entitlement_remains_unknown(self):
  rights=[{'employee_id':'1','date':'2026-11-12','kind':'Mola','required_minutes':None}];r=fulfillment(rights,[self.item()],'2026-11-12','2026-11-12')['Mola'];self.assertEqual(r['unknown_people'],1);self.assertEqual(r['given_people'],1);self.assertEqual(r['required_people'],0)

class SnapshotTests(Base):
 def test_publication_rights_do_not_change_with_current_rules(self):
  from ortak.yayin_servisi import init_publications
  self.s['status_rules']=dict(defaults(),enabled=True);rows=[row()];people=[emp()];saved=entitlement_snapshot(self.s,rows,people);init_publications(self.s['workspace_db_path'])
  with connect(self.s['workspace_db_path']) as db:db.execute('INSERT INTO publication_batches VALUES(?,?,?,?)',('pub','2026-11-12','active',dumps({'status_rights':saved})))
  self.s['status_rules']['groups']['fulltime']['break_rules']=[{'min_hours':0,'max_hours':24,'minutes':60}];rights,missing=published_entitlements(self.s,rows,people);self.assertEqual(missing,0);self.assertEqual(next(x['required_minutes'] for x in rights if x['kind']=='Mola'),30)

class CancellationTests(Base):
 def setUp(self):
  super().setUp();self.day=(pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None)+pd.Timedelta(days=2)).normalize();self.a=self.day+pd.Timedelta(hours=12);self.s['profile']={'position':'wfm','username':'planner1','full_name':'Planning'};self.s['published_shift_plan']=[row(str(i),day=self.day.date()) for i in range(1,4)];self.s['status_rules']=dict(defaults(),enabled=True,automatic=True,coaching_by_leader=True);save_keys(self.s);init(self.s['workspace_db_path'])
  self.meal={'employee_id':'1','date':str(self.day.date()),'kind':'Yemek','start':str(self.a),'end':str(self.a+pd.Timedelta(minutes=30)),'status':'Planlı'}
  with connect(self.s['workspace_db_path']) as db:db.execute('INSERT INTO planned_breaks VALUES(?,?,?)',('meal','pub',dumps(self.meal)))
 def test_future_cancellation_is_soft_and_audited_and_notifies_owner(self):
  out=cancel_targets(self.s,['status:meal'],'Hat yoğunluğu');self.assertEqual(out[0]['cancelled_minutes'],30);self.assertEqual(records(self.s)[0]['status'],'İptal');self.assertEqual(len(events(self.s)),1);self.assertEqual(out[0]['before']['start'],self.meal['start'])
  self.s['profile']={'position':'agent','username':'u1','employee_id':'1'}
  from ortak.bildirimler import items
  self.assertTrue(any(r['Konu']=='Statü iptali' and 'Hat yoğunluğu' in r['İçerik'] for r in items(self.s)))
 def test_ongoing_keeps_elapsed_plan_and_only_cancels_remainder(self):
  with patch('ortak.statu_iptalleri.now_local',return_value=self.a+pd.Timedelta(minutes=10)):out=cancel_targets(self.s,['status:meal'],'Anlık sorun')
  self.assertEqual(out[0]['cancelled_minutes'],20);rows=records(self.s);active=[r for r in rows if r['status']!='İptal'];self.assertEqual(len(active),1);self.assertEqual(pd.Timestamp(active[0]['end'])-pd.Timestamp(active[0]['start']),pd.Timedelta(minutes=10));self.assertEqual(len(rows),2)
 def test_forbidden_roles_and_blank_reason(self):
  for role in ['agent','tl']:
   self.s['profile']['position']=role
   with self.assertRaises(ValueError):cancel_targets(self.s,['status:meal'],'Yoğunluk')
  self.s['profile']['position']='wfm'
  with self.assertRaises(ValueError):cancel_targets(self.s,['status:meal'],' ')
  self.assertFalse(events(self.s));self.assertEqual(records(self.s)[0]['status'],'Planlı')
 def test_completed_cannot_be_canceled(self):
  with patch('ortak.statu_iptalleri.now_local',return_value=self.a+pd.Timedelta(minutes=31)):
   with self.assertRaisesRegex(ValueError,'geçmiş'):cancel_targets(self.s,['status:meal'],'Yoğunluk')
 def test_bulk_failure_rolls_back_all_targets(self):
  with self.assertRaises(ValueError):cancel_targets(self.s,['status:meal','status:missing'],'Yoğunluk')
  self.assertFalse(events(self.s));self.assertEqual(records(self.s)[0]['status'],'Planlı')
 def test_stale_selection_is_rejected(self):
  expected={r['id']:r for r in targets(self.s)}
  with connect(self.s['workspace_db_path']) as db:
   changed=dict(self.meal,end=str(self.a+pd.Timedelta(minutes=20)));db.execute("UPDATE planned_breaks SET payload=? WHERE id='meal'",(dumps(changed),))
  with self.assertRaisesRegex(ValueError,'başka oturumda'):cancel_targets(self.s,['status:meal'],'Yoğunluk',expected)
 def test_two_operators_cannot_cancel_twice(self):
  def run(name):
   s=copy.deepcopy(self.s);s['profile']['username']=name
   try:return cancel_targets(s,['status:meal'],'Hat sorunu')
   except ValueError:return None
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,['a','b']))
  self.assertEqual(sum(bool(r) for r in results),1);self.assertEqual(len(events(self.s)),1)
 def test_open_capacity_closes_without_reopening_or_losing_audit(self):
  from ortak.kocluk_alanlari import init as init_pool,read
  init_pool(self.s['workspace_db_path']);p=dict(self.meal,employee_id='*',kind='Koçluk Alanı',pool=True,eligible_employee_ids=['1','2'],languages=['tr'],capacity=3,remaining_capacity=3,end=str(self.a+pd.Timedelta(minutes=15)))
  with connect(self.s['workspace_db_path']) as db:db.execute('INSERT INTO coaching_openings VALUES(?,?,?,?,?)',('pool','pub','*','Açık',dumps(p)))
  out=cancel_targets(self.s,['pool:pool'],'Koçlukları durdur');self.assertFalse(read(self.s));self.assertEqual(out[0]['cancelled_capacity'],3);self.assertEqual(out[0]['cancelled_minutes'],45);pool=capacity_openings(self.s,self.day.date(),self.day.date(),{'1'})[0];self.assertEqual(pool['remaining_capacity'],0);self.assertEqual(pool['cancelled_capacity'],3)
 def test_coaching_cancellation_removes_agenda_and_releases_monthly_usage(self):
  from ortak.ajanda_servisi import init as init_agenda
  from ortak.statu_planlayici import coaching_used
  init_agenda(self.s['workspace_db_path']);p=dict(self.meal,kind='Koçluk',start=str(self.a+pd.Timedelta(hours=2)),end=str(self.a+pd.Timedelta(hours=2,minutes=15)))
  with connect(self.s['workspace_db_path']) as db:
   db.execute('INSERT INTO planned_breaks VALUES(?,?,?)',('coach','pub',dumps(p)));db.execute('INSERT INTO manager_agenda VALUES(?,?,?,?,?,?,?)',('coach','lead','1',p['start'],p['end'],'Koçluk',dumps({'name':'Person A'})))
  cancel_targets(self.s,['status:coach'],'Hat yoğunluğu');self.assertEqual(coaching_used(self.s),{})
  with connect(self.s['workspace_db_path']) as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM manager_agenda WHERE id='coach'").fetchone()[0],0)
 def test_cancelled_meeting_cannot_be_booked_again_in_same_window(self):
  from ortak.kocluk_alanlari import init as init_pool,eligible
  from ortak.ajanda_servisi import add_work,add_coaching
  init_pool(self.s['workspace_db_path']);start=self.a+pd.Timedelta(hours=2);finish=start+pd.Timedelta(minutes=15);coach=dict(self.meal,kind='Koçluk',start=str(start),end=str(finish));pool=dict(coach,employee_id='*',pool=True,eligible_employee_ids=['1','2'],languages=['tr'],capacity=2,remaining_capacity=2)
  with connect(self.s['workspace_db_path']) as db:db.execute('INSERT INTO planned_breaks VALUES(?,?,?)',('coach','pub',dumps(coach)));db.execute('INSERT INTO coaching_openings VALUES(?,?,?,?,?)',('pool','pub','*','Açık',dumps(pool)))
  cancel_targets(self.s,['status:coach'],'Hat sorunu');self.s['profile']={'position':'tl','username':'lead','full_name':'Lead','employee_id':'90'};self.s['sp_staffing_result_df']=demand(slots=range(1,49),count=0).assign(Tarih=self.day.date());save_keys(self.s);add_work(self.s,self.day+pd.Timedelta(hours=8),self.day+pd.Timedelta(hours=17));self.assertFalse(eligible(self.s,'1'))
  with self.assertRaisesRegex(ValueError,'operasyonel'):add_coaching(self.s,'1',start,15,opening_id='pool')
 def test_pending_status_swap_is_invalidated(self):
  from ortak.statu_degisimleri import init as init_swaps
  init_swaps(self.s['workspace_db_path']);p={'id':'swap','before':[{'id':'meal'}],'owner':'u1','peer':'u2','team_lead':'Lead','reason':'Değişim','created_at':str(self.day)}
  with connect(self.s['workspace_db_path']) as db:db.execute('INSERT INTO status_swap_requests VALUES(?,?,?,?)',('swap','Karşı personel onayı',1,dumps(p)))
  cancel_targets(self.s,['status:meal'],'Hat sorunu')
  with connect(self.s['workspace_db_path']) as db:r=db.execute("SELECT status,version FROM status_swap_requests WHERE id='swap'").fetchone();self.assertEqual(tuple(r),('İptal',2))

class LeaderSlotsUITests(Base):
 def test_leader_selects_fifteen_minute_box_without_capacity_and_tracking_gets_meeting(self):
  from ortak.ajanda_servisi import add_work
  from ortak.kocluk_alanlari import init as init_pool
  from streamlit.testing.v1 import AppTest
  day=(pd.Timestamp.now(tz='Europe/Istanbul').tz_localize(None)+pd.Timedelta(days=14)).normalize();self.s['profile']={'position':'tl','username':'lead','full_name':'Lead','employee_id':'90'};self.s['published_shift_plan']=[row(str(i),day=day.date()) for i in range(1,4)];self.s['sp_staffing_result_df']=demand(slots=range(1,49),count=0).assign(Tarih=day.date());self.s['status_rules']=dict(defaults(),enabled=True,automatic=True,coaching_by_leader=True,operation_reserve_rate=0.);save_keys(self.s);init(self.s['workspace_db_path']);init_pool(self.s['workspace_db_path']);add_work(self.s,day+pd.Timedelta(hours=8),day+pd.Timedelta(hours=17))
  with connect(self.s['workspace_db_path']) as db:
   for n in [0,15]:
    a=day+pd.Timedelta(hours=12,minutes=n);p={'employee_id':'*','date':str(day.date()),'kind':'Koçluk Alanı','start':str(a),'end':str(a+pd.Timedelta(minutes=15)),'pool':True,'eligible_employee_ids':['1','2'],'languages':['tr'],'capacity':2,'remaining_capacity':2,'operation_reserve_count':0.};db.execute('INSERT INTO coaching_openings VALUES(?,?,?,?,?)',('pool'+str(n),'pub','*','Açık',dumps(p)))
  at=AppTest.from_string('from modules.ajanda import render\nrender()',default_timeout=30)
  for k,v in self.s.items():at.session_state[k]=v
  at.session_state['agenda_week']=day.date();at.run();self.assertFalse(at.exception);self.assertEqual(len([b for b in at.button if str(b.key).startswith('agenda_slot_')]),2);self.assertFalse(any('kontenjan' in m.value.lower() for m in list(at.markdown)+list(at.caption)));self.assertFalse(any(b.key=='agenda_assign_coach' for b in at.button))
  next(b for b in at.button if str(b.key).startswith('agenda_slot_')).click().run();self.assertFalse(at.exception);at.button(key='agenda_assign_coach').click().run();self.assertFalse(at.exception);assigned=[r for r in records(self.s) if r['kind']=='Koçluk' and r['status']!='İptal'];self.assertEqual(len(assigned),1);self.assertEqual(pd.Timestamp(assigned[0]['end'])-pd.Timestamp(assigned[0]['start']),pd.Timedelta(minutes=15))
  tracking=AppTest.from_string('from modules.takip.benim_vardiyam import render\nrender()',default_timeout=30)
  for k,v in self.s.items():tracking.session_state[k]=v
  tracking.session_state['profile']={'position':'agent','username':'u1','employee_id':'1'};tracking.session_state['my_shift_range_v2']=(day.date(),day.date());tracking.run();self.assertFalse(tracking.exception);markup=''.join(m.value for m in tracking.markdown);self.assertIn('tracking-status-mini',markup);self.assertIn('Koçluk',markup)

class ProtectedCapacityTests(unittest.TestCase):
 def test_canceled_status_capacity_is_not_silently_reused_for_new_coaching(self):
  cfg=dict(defaults(),enabled=True,automatic=True,coaching_by_leader=True,operation_reserve_rate=0.)
  for r in cfg['groups'].values():r.update(meal_disabled=True,break_rules=[{'min_hours':0,'max_hours':24,'minutes':0}])
  s={'status_rules':cfg,'_status_call_reserve_windows':[('1',str(DAY)+' 09:00',str(DAY)+' 09:15')]};cov=demand(slots=range(1,49),count=0);cov['İhtiyaç']=0;cov['Atanan']=3;cov['Eksik']=0;cov['Fazla']=3;items,out,issues=meal_plan(s,[row(str(i)) for i in range(1,4)],cov,[emp(str(i)) for i in range(1,4)])
  # meal_plan cache is scoped to normal drafts; reconciliation uses pure planner.
  from ortak.statu_planlayici import plan
  items,out,issues=plan(s,[row(str(i)) for i in range(1,4)],cov,[emp(str(i)) for i in range(1,4)],used={});pool=next(x for x in items if x['kind']=='Koçluk Alanı' and pd.Timestamp(x['start']).strftime('%H:%M')=='09:00');self.assertEqual(pool['capacity'],2);self.assertFalse(issues)
