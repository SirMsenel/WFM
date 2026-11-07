import unittest
import pandas as pd
from streamlit.testing.v1 import AppTest


class ImprovedUITests(unittest.TestCase):
    def test_subpages_execute_only_selected_callback(self):
        at=AppTest.from_string('''
import streamlit as st
from core.navigation import sections
st.session_state.setdefault('calls',[])
def a():st.session_state['calls'].append('A')
def b():st.session_state['calls'].append('B')
sections('nav',{'A':a,'B':b})
''')
        at.run();self.assertEqual(at.session_state['calls'],['A'])
        at.session_state['nav']='B';at.run()
        self.assertEqual(at.session_state['calls'],['A','B'])
        self.assertFalse(at.exception)
    def test_feature_select_all_and_clear_do_not_change_other_groups(self):
        at=AppTest.from_string('from modules.call_forecast.feature_engineering import render\nrender()')
        raw=pd.DataFrame({'tarih':pd.date_range('2026-10-01',periods=40),'cagri_sayisi':range(100,140)})
        at.session_state['cf_full_df']=raw;at.session_state['cf_raw_df']=raw.copy()
        at.run();at.button(key='fe_all_date').click().run()
        self.assertFalse(at.exception)
        self.assertTrue(all(c.value for c in at.checkbox if c.key.startswith('cf_chk_')))
        at.button(key='fe_all_bank').click().run()
        self.assertTrue(all(c.value for c in at.checkbox if c.key.startswith('cf_bank_')))
        at.button(key='fe_clear_date').click().run()
        self.assertFalse(any(c.value for c in at.checkbox if c.key.startswith('cf_chk_')))
        self.assertTrue(all(c.value for c in at.checkbox if c.key.startswith('cf_bank_')))
    def test_request_row_detail_replaces_record_dropdown(self):
        at=AppTest.from_string('from core.request_ui import render_center\nrender_center("tl","test_requests")')
        at.session_state['profile']={'position':'tl','full_name':'Lead','username':'lead'}
        at.session_state['trk_requests']=[{'id':'REQ-ABC','created_by':'agent','created_by_name':'Personel','assigned_tls':['Lead'],
                                         'queue':'TL','status':'Beklemede','type':'Yıllık İzin Talebi','start_date':'2026-11-09',
                                         'end_date':'2026-11-09','note':'İzin','created_at':'2026-11-01','version':1,'events':[]}]
        at.run()
        self.assertFalse(at.exception)
        self.assertFalse(list(at.selectbox))
        next(b for b in at.button if b.label=='Onayla ve Planlamaya İlet').click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.session_state['trk_requests'][0]['queue'],'WFM')

if __name__=='__main__':unittest.main()
