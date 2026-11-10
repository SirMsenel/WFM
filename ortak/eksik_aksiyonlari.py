# Ortak / Eksik Aksiyonlari — bu ekranın / servisin uygulama kodu.
"""Eksik İhtiyaç Aksiyonları — kural ihlali olmadan uygulanabilen somut öneriler."""
import pandas as pd
from ortak.planlama import preview_plan
from modules.vardiya_plani.planlama_verileri import collect_inputs,fingerprint
from modules.vardiya_plani.vardiya_motoru import generate_plan,bounds


def suggestions(state,day,start_slot,end_slot,include_existing=True):
    from ortak.donem_kilitleri import assert_can_plan
    assert_can_plan(state);current=preview_plan(state,True)
    staff,fixed,history,unavailable,_=collect_inputs(state)
    existing={(str(r['employee_id']),str(r['date'])):r for r in current['source_rows'] if not(r.get('source')=='auto' and r.get('shift_code')=='OFF')}
    capacity=state.get('shift_rules',{}).get('capacity',{});allow=int(capacity.get('max_overstaff',0));minimum=float(capacity.get('min_overtime_hours',.5));a=(int(start_slot)-1)*30;b=int(end_slot)*30;accepted=[];rejected=[]
    for person in staff:
        eid=str(person['employee_id']);old=existing.get((eid,str(day)));rule=state['shift_rules']['work_type'][person['work_type']]
        maximum=int(float(rule.get('shift_total_hours_max',rule.get('shift_total_hours',7)))*60)
        if old and not include_existing:continue
        begin,finish=a,max(b,a+round(minimum*60));kind='Boş güne blok mesai'
        if old:
            if old.get('source') in {'fixed_external','approved_request','published_fixed'} or not bounds(old):continue
            interval=bounds(old);oa=int((pd.Timestamp(interval[0])-pd.Timestamp(day)).total_seconds()/60);ob=int((pd.Timestamp(interval[1])-pd.Timestamp(day)).total_seconds()/60)
            if a>ob+60 or b<oa-60:continue
            begin=min(a,oa);finish=max(ob,finish);kind='Mevcut vardiyaya ek mesai'
            if person['work_type']=='fulltime' and capacity:maximum=max(maximum,round((float(rule.get('shift_total_hours',9))+float(capacity.get('max_extension_hours',3)))*60))
        if finish-begin>maximum:finish=begin+maximum
        if finish<b or finish<=begin:continue
        row={'employee_id':eid,'date':str(day),'shift_code':'MESAI','start':f'{begin//60:02d}:{begin%60:02d}','end':f'{finish//60%24:02d}:{finish%60:02d}','source':'capacity_candidate','note':'Eksik ihtiyaç için blok mesai'}
        span=bounds(row);oldspan=bounds(old) if old else None;gain=0;bad=False
        for r in current['coverage'].itertuples():
            t=pd.Timestamp(r.Tarih)+pd.Timedelta(minutes=(int(r.Slot)-1)*30)
            was=oldspan and pd.Timestamp(oldspan[0])<=t and t+pd.Timedelta(minutes=30)<=pd.Timestamp(oldspan[1])
            added=pd.Timestamp(span[0])<=t and t+pd.Timedelta(minutes=30)<=pd.Timestamp(span[1]) and not was
            if added:
                if r.Atanan+1>r.İhtiyaç+allow:bad=True;break
                if r.Eksik>0:gain+=1
        if bad or not gain:continue
        base=[r for (i,d),r in existing.items() if i==eid and d!=str(day)]
        ctx=state['plan_ctx'];result=generate_plan([person],state['sp_staffing_result_df'],state['shift_rules'],list(state['shift_rules']['work_type']),ctx['start'],ctx['end'],fixed=base+[row],history=[r for r in history if str(r['employee_id'])==eid],unavailable=unavailable,auto_fill=False,hour_targets=state.get('group_hour_targets',[]),reject_invalid_sources=('capacity_candidate',))
        errors=[r for r in result['issues'] if r.get('source')=='capacity_candidate' and r.get('severity')!='warning'];rejected.extend(errors)
        if not errors:accepted.append({'row':row,'before':old,'person':person,'kind':kind,'gain':gain/2})
    return sorted(accepted,key=lambda p:-p['gain']),rejected


def render_actions(state,result,key):
    import streamlit as st
    missing=result['coverage'];missing=missing[missing.Eksik>0]
    if missing.empty:return
    with st.expander('Eksik için ne yapabilirim? · Uygun aksiyon bul'):
        daily=missing.groupby('Tarih').Eksik.agg(['sum','max'])
        st.caption('Önce OFF dağılımını ihtiyaca göre seçerek taslağı oluştur. Kalan açıklar için boş güne mesai veya mevcut vardiyayı grup üst süresine uzatma önerileri aranır; okul, dinlenme, gün ve dönem saat sınırları korunur.')
        day=st.selectbox('Aksiyon günü',sorted(missing.Tarih.astype(str).unique()),key=key+'_action_day')
        selected=missing[missing.Tarih.astype(str)==day].sort_values('Slot')
        groups=[];begin=previous=None
        for slot in selected.Slot.astype(int):
            if previous is None or slot!=previous+1:
                if previous is not None:groups.append((begin,previous))
                begin=slot
            previous=slot
        if previous is not None:groups.append((begin,previous))
        from ortak.saat_etiketleri import slot_label
        gap=st.selectbox('Eksik saat bloğu',groups,format_func=lambda g:slot_label(g[0]).split('–')[0]+'–'+slot_label(g[1]).split('–')[1],key=key+'_action_gap')
        include=st.checkbox('Mevcut vardiyası olanlara da ek mesai öner',value=False,key=key+'_include_existing')
        custom=st.checkbox('Saat bloğunu ben seçeceğim',key=key+'_custom_gap')
        if custom:
            first,last=st.slider('Atanacak saat bloğu (yarım saat dilimi)',1,48,(gap[0],gap[1]),key=key+'_custom_slots');gap=(first,last)
        signature=fingerprint(state)+str((day,gap,include));cachekey=key+'_action_result'
        if st.button('Uygun Aksiyonları Bul',key=key+'_find_actions'):
            try:
                with st.spinner('Uygunluklar kontrol ediliyor…'):options,rejected=suggestions(state,day,*gap,include_existing=include)
                state[cachekey]={'signature':signature,'options':options,'rejected':rejected}
            except ValueError as exc:st.error(str(exc))
        data=state.get(cachekey)
        if not data or data['signature']!=signature:return
        options=data['options']
        if not options:
            st.warning('Bu blok için mevcut kurallarla uygulanabilir ek atama bulunamadı. Daha fazla personel / uygun farklı grup gerekir veya OFF ve süre kuralları yeniden değerlendirilmelidir. Kurallar kendiliğinden esnetilmez.')
            if data['rejected']:
                from collections import Counter
                st.dataframe([{'Neden':r,'Personel sayısı':n} for r,n in Counter(x['Sorun'] for x in data['rejected']).items()],hide_index=True,use_container_width=True)
            return
        rows=[{'Personel':p['person']['full_name'],'Sicil':p['person'].get('sicil_no',p['row']['employee_id']),'Kullanıcı adı':p['person'].get('username'),'Aksiyon':p['kind'],'Yeni saat':p['row']['start']+'–'+p['row']['end'],'Kapatılacak personel-saat':p['gain']} for p in options]
        st.dataframe(rows,hide_index=True,use_container_width=True)
        choice=st.selectbox('Uygulanacak öneri',list(range(len(options))),format_func=lambda i:rows[i]['Personel']+' · '+rows[i]['Yeni saat'],key=key+'_action_pick')
        reason=st.text_input('Aksiyon gerekçesi',key=key+'_action_reason')
        if st.button('Öneriyi Taslağa Uygula',disabled=not reason.strip(),key=key+'_action_apply'):
            from ortak.taslak_degisimleri import edit_shifts
            row={**options[choice]['row'],'source':'manual_single','note':reason}
            try:edit_shifts(state,[row]);st.success('Öneri taslağa işlendi. Güncel karşılaştırma için otomatik taslağı yeniden oluştur veya Vardiya Saatleri ekranını aç.')
            except ValueError as exc:st.error(str(exc))
