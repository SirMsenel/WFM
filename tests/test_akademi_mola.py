"""Akademi kısa vardiya hakları, tanımsız aralık ve kesintisiz mola kontrolleri."""
import unittest
import pandas as pd
from ortak.statuler import defaults,meal_plan
from ortak.statu_planlayici import allowance,MolaKuralHatasi
from ortak.statu_haklari import balance,assert_complete
from test_planning import demand,emp,row,DAY

class AcademicBreakTests(unittest.TestCase):
 def setup_plan(self,hours=4):
  s={'status_rules':dict(defaults(),enabled=True,automatic=True,coaching_by_leader=True)};p=emp(group='akademi');end=pd.Timestamp(DAY)+pd.Timedelta(hours=8+hours);plan=[row(start='08:00',end=end.strftime('%H:%M'))];cov=demand(slots=range(1,49));cov['İhtiyaç']=1.;cov['Atanan']=1.;cov['Eksik']=0.;cov['Fazla']=0.
  return s,p,plan,cov
 def test_default_4_45_5_hour_shifts_get_full_right_in_short_pieces(self):
  for hours in [4,4.5,5]:
   with self.subTest(hours=hours):
    s,p,plan,cov=self.setup_plan(hours);items,_,issues=meal_plan(s,plan,cov,[p]);self.assertFalse(issues);rest=[r for r in items if r['kind']=='Mola'];self.assertEqual(sum((pd.Timestamp(r['end'])-pd.Timestamp(r['start'])).total_seconds()/60 for r in rest),30);self.assertTrue(all((pd.Timestamp(r['end'])-pd.Timestamp(r['start'])).total_seconds()/60<=15 for r in rest));assert_complete(s,{'plan':plan,'staff':[p],'breaks':items})
 def test_gap_is_a_blocker_not_a_zero_minute_entitlement(self):
  s,p,plan,cov=self.setup_plan(4.5);s['status_rules']['groups']['akademi']['break_rules']=[{'min_hours':0,'max_hours':4,'minutes':15},{'min_hours':5,'max_hours':24,'minutes':30}];items,_,issues=meal_plan(s,plan,cov,[p]);self.assertTrue(any(x['severity']=='error' and '4.5 saat' in x['Sorun'] for x in issues));rights=balance(s,plan,[p],items);self.assertIsNone(rights[0]['Hak (dk)']);self.assertTrue(rights[0]['Kural hatası'])
  with self.assertRaisesRegex(ValueError,'mola kuralı bulunamadı'):assert_complete(s,{'plan':plan,'staff':[p],'breaks':items})
 def test_upper_boundary_is_excluded_and_lower_boundary_included(self):
  r={'break_rules':[{'min_hours':0,'max_hours':4,'minutes':15},{'min_hours':4,'max_hours':5,'minutes':30}]};self.assertEqual(allowance(r,4),30)
  with self.assertRaises(MolaKuralHatasi):allowance(r,5)
 def test_empty_rules_and_overlaps_cannot_silently_return_zero(self):
  for rules in [[],[{'min_hours':0,'max_hours':5,'minutes':15},{'min_hours':4,'max_hours':6,'minutes':30}]]:
   with self.assertRaises(MolaKuralHatasi):allowance({'break_rules':rules},4.5)
 def test_explicit_zero_right_remains_zero(self):
  s,p,plan,cov=self.setup_plan();s['status_rules']['groups']['akademi']['break_rules']=[{'min_hours':0,'max_hours':24,'minutes':0}];items,_,issues=meal_plan(s,plan,cov,[p]);self.assertFalse(issues);self.assertFalse(any(x['kind']=='Mola' for x in items));assert_complete(s,{'plan':plan,'staff':[p],'breaks':items})
 def test_legacy_total_without_range_table_is_preserved(self):
  self.assertEqual(allowance({'break_total_minutes':20},4.5),20)
 def test_single_thirty_minute_rest_rejected_even_when_daily_total_matches(self):
  s,p,plan,_=self.setup_plan();items=[{'employee_id':'1','date':str(DAY),'kind':kind,'start':str(DAY)+f' {a}','end':str(DAY)+f' {b}'} for kind,a,b in [('Mola','09:00:00','09:30:00'),('Yemek','10:00:00','10:30:00')]]
  with self.assertRaisesRegex(ValueError,'Tek mola en fazla 15'):assert_complete(s,{'plan':plan,'staff':[p],'breaks':items})
 def test_two_touching_rest_records_cannot_disguise_a_thirty_minute_break(self):
  s,p,plan,_=self.setup_plan();items=[{'employee_id':'1','date':str(DAY),'kind':kind,'start':str(DAY)+f' {a}','end':str(DAY)+f' {b}'} for kind,a,b in [('Mola','09:45:00','10:00:00'),('Mola','10:00:00','10:15:00'),('Yemek','10:30:00','11:00:00')]]
  with self.assertRaisesRegex(ValueError,'Bitişik molalar'):assert_complete(s,{'plan':plan,'staff':[p],'breaks':items})
 def test_engine_leaves_work_between_rest_pieces_with_high_hourly_limit(self):
  s,p,plan,cov=self.setup_plan(5);r=s['status_rules']['groups']['akademi'];r.update(break_per_hour_max=60,break_rules=[{'min_hours':0,'max_hours':24,'minutes':60}]);items,_,issues=meal_plan(s,plan,cov,[p]);self.assertFalse(issues);rest=sorted([i for i in items if i['kind']=='Mola'],key=lambda i:i['start']);self.assertEqual(sum((pd.Timestamp(x['end'])-pd.Timestamp(x['start'])).total_seconds()/60 for x in rest),60);self.assertTrue(all(pd.Timestamp(a['end'])<pd.Timestamp(b['start']) for a,b in zip(rest,rest[1:])));assert_complete(s,{'plan':plan,'staff':[p],'breaks':items})
 def test_configured_one_minute_maximum_is_respected(self):
  s,p,plan,cov=self.setup_plan();r=s['status_rules']['groups']['akademi'];r.update(break_minutes=1,break_rules=[{'min_hours':0,'max_hours':24,'minutes':6}]);items,_,issues=meal_plan(s,plan,cov,[p]);self.assertFalse(issues);rest=[x for x in items if x['kind']=='Mola'];self.assertEqual(len(rest),6);self.assertTrue(all(pd.Timestamp(x['end'])-pd.Timestamp(x['start'])==pd.Timedelta(minutes=1) for x in rest));assert_complete(s,{'plan':plan,'staff':[p],'breaks':items})
 def test_fractional_minutes_are_not_rounded_down_to_zero(self):
  with self.assertRaises(MolaKuralHatasi):allowance({'break_rules':[{'min_hours':0,'max_hours':24,'minutes':.5}]},4)
