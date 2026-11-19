"""Canlı analiz: gerçekleşen hizmet seviyesi ve aynı Erlang parametreleriyle ihtiyaç."""
import pandas as pd
from ortak.calisma_alani_deposu import connect
from ortak.sabit_demo import init_history
from modules.mesai_plani.personel_ihtiyaci import erlang_c_required_agents,erlang_c_metrics_for_m


def actual_metrics(state,frame):
    path=state['workspace_db_path'];init_history(path)
    with connect(path) as db:ops=pd.read_sql_query('SELECT tarih,slot,answered,answered_target,staffed FROM interval_operations',db);aht=pd.read_sql_query('SELECT tarih,slot,aht_sec FROM calls_interval',db)
    out=frame.merge(ops,on=['tarih','slot'],how='left').merge(aht,on=['tarih','slot'],how='left')
    out['Gerçek SL (%)']=100*out.answered_target/out.actual.replace(0,float('nan'))
    params=state.get('staffing_parameters',{});required=[];modeled=[]
    for r in out.itertuples():
        if pd.isna(r.actual) or pd.isna(r.aht_sec):required.append(None);modeled.append(None);continue
        target=float(params.get('target_sl',.8));seconds=float(params.get('target_time',20));occ=float(params.get('occ_target',.85))
        required.append(erlang_c_required_agents(float(r.actual),float(r.aht_sec),1800,target,seconds,occ)['m'])
        modeled.append(100*erlang_c_metrics_for_m(float(r.actual),float(r.aht_sec),1800,int(r.staffed),seconds)[1] if pd.notna(r.staffed) else None)
    predicted=[]
    for row in out.itertuples():
        calls=float(row.predicted);aht=float(params.get('aht',300));seconds=float(params.get('target_time',20));target=float(params.get('target_sl',.8));occ=float(params.get('occ_target',.85))
        agents=erlang_c_required_agents(calls,aht,1800,target,seconds,occ)['m'];predicted.append(100*erlang_c_metrics_for_m(calls,aht,1800,agents,seconds)[1] if agents else 100.)
    out['Tahmini SL (%)']=predicted
    out['Gerçekleşene göre net ihtiyaç']=required;out['Erlang model SL (%)']=modeled
    return out
