from copy import deepcopy
from datetime import date
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor

from core import workspace_store as store
from core.request_service import create_request,act,refresh,supersede_generated
from core.forecast_service import (reference_models,forecast_candidates,ranked_candidates,register_model,
                                  weekday_comparison,validate_forecast,activate_forecast,daily_history)
from modules.shift_planner.staffing_forecast import erlang_c_probability,calculate_staffing


class RequestFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='wfm-tests-')
        self.db=Path(self.tmp.name)/'requests.db'
        store.init_db(self.db)
        self.agent={'position':'agent','username':'person1','employee_id':'1','full_name':'Person One','team_lead':'Lead One'}
        self.state={'profile':self.agent,'workspace_db_path':str(self.db)}
        self.payload={'type':'Yıllık İzin Talebi','start_date':'2026-11-09','end_date':'2026-11-10','note':'Açıklama'}
    def tearDown(self):
        self.tmp.cleanup()
    def lead(self,name='Lead One'):
        return {'position':'tl','username':name,'full_name':name}
    def wfm(self):
        return {'position':'wfm','username':'planner','full_name':'Planlama'}
    def test_persistent_personnel_lead_planner_lifecycle(self):
        req=create_request(self.state,self.payload)
        lead={'profile':self.lead(),'workspace_db_path':str(self.db)}
        req=refresh(lead)[0]
        req=act(lead,req,'forward','Planlama kontrolü uygundur')
        self.assertEqual(req['queue'],'WFM')
        planner={'profile':self.wfm(),'workspace_db_path':str(self.db)}
        req=act(planner,refresh(planner)[0],'apply','Plana alınacak')
        self.assertEqual(req['status'],'Onaylandı')
        self.assertEqual(len(req['events']),3)
        self.assertEqual(refresh(self.state)[0]['events'][-1]['actor_name'],'Planlama')
        with store.connect(self.db) as con:
            self.assertEqual(con.execute('select count(*) from request_events').fetchone()[0],3)
    def test_rejection_requires_reason(self):
        req=create_request(self.state,self.payload)
        self.state['profile']=self.lead()
        with self.assertRaises(ValueError):act(self.state,req,'reject','')
        req=act(self.state,req,'reject','Dönem uygun değil')
        self.assertEqual(req['decision_note'],'Dönem uygun değil')
    def test_wrong_lead_and_agent_cannot_approve(self):
        req=create_request(self.state,self.payload)
        with self.assertRaises(ValueError):act(self.state,req,'forward')
        self.state['profile']=self.lead('Unrelated')
        with self.assertRaises(ValueError):act(self.state,req,'forward')
    def test_concurrent_decision_cannot_overwrite(self):
        req=create_request(self.state,self.payload)
        self.state['profile']=self.lead()
        act(self.state,req,'forward')
        with self.assertRaisesRegex(ValueError,'başka bir kullanıcı'):
            act(self.state,req,'reject','Stale browser')
    def test_attachments_are_receipts_not_live_tables(self):
        attachment={'title':'Okul','rows':[{'Saat':'08:00-10:00','Pazartesi':'Matematik'}]}
        payload={'type':'Ders Programı','note':'Ders','generated_from':'class_schedule','generated_ref':'person1::2026-Güz'}
        req=create_request(self.state,payload,attachment)
        attachment['rows'][0]['Pazartesi']='Changed'
        self.assertEqual(req['attachment']['rows'][0]['Pazartesi'],'Matematik')
        supersede_generated(self.state,'class_schedule','person1::2026-Güz')
        old=refresh(self.state)[0]
        self.assertEqual(old['status'],'Güncellendi')
        self.assertEqual(old['attachment']['rows'][0]['Pazartesi'],'Matematik')
        self.assertEqual(len(old['events']),2)
    def test_original_content_and_audit_cannot_be_rewritten(self):
        req=create_request(self.state,self.payload)
        altered=deepcopy(req);altered['note']='Another story'
        with self.assertRaises(ValueError):store.put_request(altered,req['version'],self.db)
        altered=deepcopy(req);altered['events']=[]
        with self.assertRaises(ValueError):store.put_request(altered,req['version'],self.db)
    def test_swap_requires_both_team_leads(self):
        self.state['employees_cache']=[{'employee_id':str(i),'work_type':'fulltime','language':'tr'} for i in (1,2)]
        self.state['draft_shift_plan']=[{'employee_id':eid,'date':str(day.date()),'shift_code':'WORK','start':start,'end':end} for eid,start,end in [('1','08:00','17:00'),('2','09:00','18:00')] for day in pd.date_range(self.payload['start_date'],self.payload['end_date'])]
        payload={**self.payload,'type':'Vardiya Değişim Talebi','targets':[{'employee_id':'2','team_lead':'Lead Two'}]}
        req=create_request(self.state,payload)
        self.state['profile']=self.lead()
        req=act(self.state,req,'forward')
        self.assertEqual(req['queue'],'TL_SWAP')
        self.state['profile']=self.lead('Lead Two')
        req=act(self.state,req,'forward')
        self.assertEqual(req['queue'],'WFM')
        self.assertEqual(len(req['tl_approvals']),2)
    def test_identity_is_taken_from_authenticated_profile(self):
        req=create_request(self.state,{**self.payload,'created_by':'someone_else','employee_id':'999'})
        self.assertEqual(req['created_by'],'person1')
        self.assertEqual(req['employee_id'],'1')


class ForecastTests(unittest.TestCase):
    def history(self):
        dates=pd.date_range('2026-01-01',periods=100)
        return pd.DataFrame({'tarih':dates,'cagri_sayisi':1000+dates.weekday*100+np.sin(np.arange(100))*10})
    def test_four_real_models_share_holdout_and_dates(self):
        state={}
        scores=reference_models(state,self.history())
        self.assertEqual(len(scores),5)
        candidates=ranked_candidates(state)
        self.assertEqual(len(candidates),4)
        self.assertEqual([x['metrics']['RMSE'] for x in candidates], sorted(scores.RMSE)[:4])
        self.assertEqual(len({x['context'] for x in candidates}),1)
        options=forecast_candidates(state,'2026-04-11','2026-04-17')
        self.assertEqual(len(options),4)
        for option in options:
            self.assertEqual(len(option['frame']),7)
            self.assertTrue((option['frame'].y_pred>=0).all())
    def test_interval_models_forecast_all_48_slots(self):
        state={}
        history=pd.DataFrame({'tarih':pd.date_range('2026-01-01',periods=96,freq='30min'),'Slot30':list(range(1,49))*2,'calls':10})
        for i in range(4):
            model=DummyRegressor(strategy='constant',constant=10+i).fit(history[['Slot30']],history.calls)
            register_model(state,str(i),model,{'RMSE':i+1.,'MAE':i+1.},history,['Slot30'],['Slot30'],'tarih',context='same')
        options=forecast_candidates(state,'2026-01-03','2026-01-04')
        self.assertEqual(options[0]['frame'].y_pred.tolist(),[480.,480.])
    def test_manual_source_invalidates_staffing_without_changing_models(self):
        state={'sp_staffing_result_df':pd.DataFrame({'x':[1]}),'cf_forecast_options':[{'id':'original'}]}
        activate_forecast(state,pd.DataFrame({'tarih':['2026-11-09'],'y_pred':[15000]}),{'model_name':'Elle'})
        self.assertIsNone(state['sp_staffing_result_df'])
        self.assertFalse(state['plan_ctx_confirmed'])
        self.assertEqual(state['cf_forecast_options'],[{'id':'original'}])

    def test_interval_slot_alias_is_rebuilt_for_every_future_slot(self):
        from sklearn.tree import DecisionTreeRegressor
        state={}
        history=pd.DataFrame({'tarih':pd.date_range('2026-01-01',periods=96,freq='30min'),'slot':list(range(1,49))*2})
        history['calls']=history.slot
        for i in range(4):
            model=DecisionTreeRegressor(random_state=i).fit(history[['slot']],history.calls)
            register_model(state,str(i),model,{'RMSE':1.,'MAE':1.},history,['slot'],['slot'],'tarih',context='same')
        options=forecast_candidates(state,'2026-01-03','2026-01-03')
        self.assertEqual(options[0]['frame'].y_pred.tolist(),[sum(range(1,49))])
    def test_bad_manual_values_rejected(self):
        for values in [[-1],[np.nan],[np.inf]]:
            with self.assertRaises(ValueError):validate_forecast(pd.DataFrame({'tarih':['2026-11-09'],'y_pred':values}))
        with self.assertRaises(ValueError):validate_forecast(pd.DataFrame({'tarih':['2026-11-09','2026-11-11'],'y_pred':[1,2]}))
    def test_lag_rolling_uses_only_observed_values(self):
        dates=pd.date_range('2026-10-01','2026-11-08')
        history=pd.DataFrame({'tarih':dates,'cagri_sayisi':np.arange(len(dates))+1})
        result=weekday_comparison(history,'2026-11-09',as_of='2026-11-08')
        self.assertEqual(result.iloc[0]['Geçen hafta aynı gün'],history.set_index('tarih').loc['2026-11-02','cagri_sayisi'])
        expected=history[history.tarih.isin(pd.to_datetime(['2026-11-02','2026-10-26']))].cagri_sayisi.mean()
        self.assertEqual(result.iloc[0]['Son 2 hafta aynı gün ort.'],expected)
        future=pd.DataFrame({'tarih':pd.to_datetime(['2026-11-09']),'cagri_sayisi':[999999]})
        pd.testing.assert_frame_equal(result,weekday_comparison(pd.concat([history,future]),'2026-11-09',as_of='2026-11-08'))
    def test_missing_lag_is_nan_not_zero(self):
        history=pd.DataFrame({'tarih':pd.to_datetime(['2026-11-01']),'cagri_sayisi':[100]})
        result=weekday_comparison(history,'2026-11-09',as_of='2026-11-08')
        self.assertTrue(pd.isna(result.iloc[0]['Geçen hafta aynı gün']))
        self.assertEqual(result.iloc[0]['2 hafta örnek sayısı'],0)
    def test_erlang_is_stable_at_large_load(self):
        result=erlang_c_probability(300,350)
        self.assertGreaterEqual(result,0)
        self.assertLessEqual(result,1)
        self.assertAlmostEqual(erlang_c_probability(1,2),1/3)


class StatePersistenceTests(unittest.TestCase):
    def test_shared_state_and_null_invalidation_survive_reload(self):
        with tempfile.TemporaryDirectory(prefix='wfm-tests-') as tmp:
            db=Path(tmp)/'state.db';store.init_db(db)
            state={'workspace_db_path':str(db),'sp_forecast_df':pd.DataFrame({'tarih':pd.to_datetime(['2026-11-09']),'y_pred':[123]}),
                   'plan_ctx':{'start':date(2026,11,9),'end':date(2026,11,15)},'sp_staffing_result_df':pd.DataFrame({'x':[1]})}
            store.save_keys(state)
            other={};store.hydrate(other,db)
            self.assertEqual(other['plan_ctx']['start'],date(2026,11,9))
            pd.testing.assert_frame_equal(state['sp_forecast_df'],other['sp_forecast_df'])
            state['sp_staffing_result_df']=None;store.save_keys(state)
            third={};store.hydrate(third,db)
            self.assertIsNone(third['sp_staffing_result_df'])


if __name__=='__main__':unittest.main()
