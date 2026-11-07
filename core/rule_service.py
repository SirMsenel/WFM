from copy import deepcopy
from datetime import timedelta
import pandas as pd
from core.defaults import enforce_current_rules
from core.workspace_store import save_keys


def apply_rules(state,rules,sync_nights=False):
    state['shift_rules']=deepcopy(rules);enforce_current_rules(state)
    changed=0
    if sync_nights:
        general=state['shift_rules']['general'];ctx=state.get('plan_ctx') or {}
        for key in ('fixed_shift_records','draft_shift_plan','shift_overrides'):
            rows=[]
            for original in state.get(key,[]):
                row=deepcopy(original)
                if row.get('shift_code',row.get('override_type'))!='GECE' or row.get('source')=='approved_request':
                    rows.append(row);continue
                begin=pd.Timestamp(row.get('date') or row.get('start_date')).date()
                finish=pd.Timestamp(row.get('date') or row.get('end_date') or begin).date()
                left=max(begin,pd.Timestamp(ctx.get('start',begin)).date());right=min(finish,pd.Timestamp(ctx.get('end',finish)).date())
                if left>right:rows.append(row);continue
                if (row.get('start'),row.get('end'))!=(general['night_window_start'],general['night_window_end']):changed+=1
                if 'date' not in row:
                    for a,b,suffix in ((begin,left-timedelta(days=1),'before'),(right+timedelta(days=1),finish,'after')):
                        if a<=b:rows.append({**row,'id':str(row.get('id','night'))+'-'+suffix+'-'+str(a),'start_date':str(a),'end_date':str(b)})
                    row.update(start_date=str(left),end_date=str(right))
                row.update(start=general['night_window_start'],end=general['night_window_end'])
                rows.append(row)
            state[key]=rows
    save_keys(state)
    return changed
