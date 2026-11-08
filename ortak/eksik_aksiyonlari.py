# Ortak / Eksik Aksiyonlari — bu ekranın / servisin uygulama kodu.
"""Eksik İhtiyaç Aksiyonları — kural ihlali olmadan uygulanabilen somut öneriler."""
import pandas as pd
from ortak.planlama import preview_plan
from modules.vardiya_plani.planlama_verileri import collect_inputs,fingerprint
from modules.vardiya_plani.vardiya_motoru import generate_plan,bounds


def suggestions(state,day,start_slot,end_slot):
    from ortak.donem_kilitleri import assert_can_plan
    assert_can_plan(state);current=preview_plan(state,True)
    staff,fixed,history,unavailable,_=collect_inputs(state);people={str(e['employee_id']):e for e in staff}
    existing={(str(r['employee_id']),str(r['date'])):r for r in current['source_rows'] if not(r.get('source')=='auto' and r.get('shift_code')=='OFF')}
    protected={'fixed_external','approved_request','published_fixed'}
    a=(int(start_slot)-1)*30;b=int(end_slot)*30;proposals=[]
    for eid,person in people.items():
        old=existing.get((eid,str(day)));rule=state['shift_rules']['work_type'][person['work_type']]
        maximum=int(float(rule.get('shift_total_hours_max',rule.get('shift_total_hours',7)))*60)
        begin,finish=a,min(b,a+maximum);kind='Boş güne ek mesai'
        if old:
            if old.get('source') in protected or not bounds(old):continue
            interval=bounds(old);old_a=int((interval[0]-pd.Timestamp(day).to_pydatetime()).total_seconds()/60);old_b=old_a+int((interval[1]-interval[0]).total_seconds()/60)
            room=maximum-(old_b-old_a)
            if room<30:continue
            if a==old_b:begin,finish=old_a,min(b,old_b+room)
            elif b==old_a:begin,finish=max(a,old_a-room),old_b
            else:continue
            kind='Vardiyayı üst süreye uzat'
        if finish<=begin:continue
        row={'employee_id':eid,'date':str(day),'shift_code':'MESAI' if not old else old['shift_code'],'start':f'{begin//60:02d}:{begin%60:02d}','end':f'{finish//60%24:02d}:{finish%60:02d}','source':'capacity_candidate','note':'Eksik ihtiyaç aksiyonu'}
        old_interval=bounds(old) if old else None;new_interval=bounds(row)
        cover=current['coverage'];blocked=False;gain=0
        for _,slot in cover.iterrows():
            stamp=pd.Timestamp(slot.Tarih)+pd.Timedelta(minutes=(int(slot.Slot)-1)*30)
            included=slot.get('Sayaca Dahil',True)
            was=bool(old_interval and old_interval[0]<=stamp and stamp+pd.Timedelta(minutes=30)<=old_interval[1])
            added=new_interval[0]<=stamp and stamp+pd.Timedelta(minutes=30)<=new_interval[1] and not was
            if added and included:
                if slot.Eksik<=0:blocked=True;break
                gain+=1
        if blocked or not gain:continue
        proposals.append({'row':row,'before':old,'person':person,'kind':kind,'gain':gain/2})
    keys={(p['row']['employee_id'],p['row']['date']) for p in proposals}
    base=[r for r in existing.values() if (str(r['employee_id']),r['date']) not in keys]
    context=state['plan_ctx']
    result=generate_plan(staff,state['sp_staffing_result_df'],state['shift_rules'],list(state['shift_rules']['work_type']),context['start'],context['end'],fixed=base+[p['row'] for p in proposals],history=history,unavailable=unavailable,auto_fill=False,hour_targets=state.get('group_hour_targets',[]),reject_invalid_sources=('capacity_candidate',))
    valid={(r['employee_id'],r['date']) for r in result['plan'] if r.get('source')=='capacity_candidate'}
    accepted=[p for p in proposals if (p['row']['employee_id'],p['row']['date']) in valid]
    rejected=[r for r in result['issues'] if r.get('source')=='capacity_candidate']
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
        signature=fingerprint(state)+str((day,gap));cachekey=key+'_action_result'
        if st.button('Uygun Aksiyonları Bul',key=key+'_find_actions'):
            try:
                with st.spinner('Uygunluklar kontrol ediliyor…'):options,rejected=suggestions(state,day,*gap)
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
