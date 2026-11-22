# Ortak / Eksik Aksiyonlari — bu ekranın / servisin uygulama kodu.
"""Eksik İhtiyaç Aksiyonları — kural ihlali olmadan uygulanabilen somut öneriler."""
import pandas as pd
from ortak.planlama import preview_plan
from modules.vardiya_plani.planlama_verileri import collect_inputs,fingerprint
from modules.vardiya_plani.vardiya_motoru import generate_plan,bounds


def suggestions(state,day,start_slot,end_slot,source_mode='Her ikisi',allowed_groups=None):
    from ortak.donem_kilitleri import assert_can_plan
    assert_can_plan(state);current=preview_plan(state,True)
    staff,fixed,history,unavailable,_=collect_inputs(state)
    existing={(str(r['employee_id']),str(r['date'])):r for r in current['source_rows'] if not(r.get('source')=='auto' and r.get('shift_code')=='OFF')}
    capacity=state.get('shift_rules',{}).get('capacity',{});allow=max(int(capacity.get('max_overstaff',0)),int(capacity.get('recommendation_overstaff_limit',5)));minimum=float(capacity.get('min_overtime_hours',.5));a=(int(start_slot)-1)*30;b=int(end_slot)*30;accepted=[];rejected=[]
    for person in staff:
        eid=str(person['employee_id']);old=existing.get((eid,str(day)));rule=state['shift_rules']['work_type'][person['work_type']]
        if allowed_groups and person['work_type'] not in allowed_groups:continue
        maximum=int(float(rule.get('shift_total_hours_max',rule.get('shift_total_hours',7)))*60)
        if old and source_mode=='Boş günü olanlar':continue
        if not old and source_mode=='Mevcut vardiyayı uzat':continue
        begin,finish=a,max(b,a+round(minimum*60));kind='Boş güne blok mesai'
        if old:
            if old.get('source') in {'fixed_external','approved_request','published_fixed'} or not bounds(old):continue
            interval=bounds(old);oa=int((pd.Timestamp(interval[0])-pd.Timestamp(day)).total_seconds()/60);ob=int((pd.Timestamp(interval[1])-pd.Timestamp(day)).total_seconds()/60)
            if a>ob+60 or b<oa-60:continue
            begin=min(a,oa);finish=max(ob,finish);kind='Mevcut vardiyaya ek mesai'
            if person['work_type']=='fulltime' and capacity:maximum=max(maximum,round((float(rule.get('shift_total_hours',9))+float(capacity.get('max_extension_hours',3)))*60))
        if finish-begin>maximum:finish=begin+maximum
        if finish<b or finish<=begin:continue
        # Aynı başlangıçla, grubun izin verdiği en uzun süreye kadar alternatif
        # bitişler denenir. Böylece akademi gibi esnek gruplar yalnızca ilk açık
        # kapanınca durmaz; +5 kişiye kadar kontrollü fazlayla bloğu tamamlar.
        oldspan=bounds(old) if old else None;best=None
        for candidate_finish in range(finish,min(1440,begin+maximum)+1,30):
            row={'employee_id':eid,'date':str(day),'shift_code':'MESAI','start':f'{begin//60:02d}:{begin%60:02d}','end':f'{candidate_finish//60%24:02d}:{candidate_finish%60:02d}','source':'capacity_candidate','note':'Eksik ihtiyaç için blok mesai'}
            span=bounds(row);gain=0;bad=False
            for r in current['coverage'].itertuples():
                t=pd.Timestamp(r.Tarih)+pd.Timedelta(minutes=(int(r.Slot)-1)*30)
                was=oldspan and pd.Timestamp(oldspan[0])<=t and t+pd.Timedelta(minutes=30)<=pd.Timestamp(oldspan[1])
                added=pd.Timestamp(span[0])<=t and t+pd.Timedelta(minutes=30)<=pd.Timestamp(span[1]) and not was
                if added:
                    if r.Atanan+1>r.İhtiyaç+allow:bad=True;break
                    if r.Eksik>0:gain+=min(1.,float(r.Eksik))
            if not bad and gain and (best is None or gain>best[0] or gain==best[0] and candidate_finish>best[1]):best=(gain,candidate_finish,row)
        if best is None:continue
        gain,_,row=best
        base=[r for (i,d),r in existing.items() if i==eid and d!=str(day)]
        ctx=state['plan_ctx'];result=generate_plan([person],__import__('ortak.plan_ihtiyaci',fromlist=['demand']).demand(state),state['shift_rules'],list(state['shift_rules']['work_type']),ctx['start'],ctx['end'],fixed=base+[row],history=[r for r in history if str(r['employee_id'])==eid],unavailable=unavailable,auto_fill=False,hour_targets=state.get('group_hour_targets',[]),reject_invalid_sources=('capacity_candidate',))
        errors=[r for r in result['issues'] if r.get('source')=='capacity_candidate' and r.get('severity')!='warning'];rejected.extend(errors)
        if not errors:accepted.append({'row':row,'before':old,'person':person,'kind':kind,'gain':gain/2})
    return sorted(accepted,key=lambda p:-p['gain']),rejected


def render_actions(state,result,key):
    import streamlit as st
    missing=result['coverage'];missing=missing[missing.Eksik>0]
    if missing.empty:return
    with st.expander('Eksik için ne yapabilirim? · Uygun aksiyon bul',expanded=True):
        daily=missing.groupby('Tarih').Eksik.agg(['sum','max'])
        limit=int(state.get('shift_rules',{}).get('capacity',{}).get('recommendation_overstaff_limit',5))
        st.caption(f'Öneri, eksik bloğu kapatırken dilim başına en fazla +{limit} fazla personele geçebilir. Boş gün ve mevcut vardiya seçenekleri; okul, 11 saat dinlenme, 6 gün üst üste çalışma ve dönem saat sınırlarını korur.')
        day_order=missing.groupby(missing.Tarih.astype(str)).Eksik.sum().sort_values(ascending=False).index.tolist()
        day=st.selectbox('Aksiyon günü',day_order,key=key+'_action_day')
        selected=missing[missing.Tarih.astype(str)==day].sort_values('Slot')
        groups=[];begin=previous=None
        for slot in selected.Slot.astype(int):
            if previous is None or slot>previous+1+int(state.get('shift_rules',{}).get('capacity',{}).get('bridge_gap_slots',1)):
                if previous is not None:groups.append((begin,previous))
                begin=slot
            previous=slot
        if previous is not None:groups.append((begin,previous))
        from ortak.saat_etiketleri import slot_label
        mode=st.segmented_control('Saat seçimi',['Otomatik eksik blok','Tek yarım saat','Özel saat aralığı'],default='Otomatik eksik blok',key=key+'_time_mode') or 'Otomatik eksik blok'
        if mode=='Otomatik eksik blok':
            gap=st.selectbox('Tamamlanacak eksik blok',groups,format_func=lambda g:slot_label(g[0]).split('–')[0]+'–'+slot_label(g[1]).split('–')[1],key=key+'_action_gap')
        elif mode=='Tek yarım saat':
            slot=st.selectbox('Eksik yarım saat',selected.Slot.astype(int).tolist(),format_func=slot_label,key=key+'_single_slot');gap=(slot,slot)
        else:
            left,right=st.columns(2);first=left.selectbox('Başlangıç',list(range(1,49)),format_func=lambda value:slot_label(value).split('–')[0],key=key+'_custom_start');last=right.selectbox('Bitiş',list(range(1,49)),index=max(0,int(first)-1),format_func=lambda value:slot_label(value).split('–')[1],key=key+'_custom_end')
            if last<first:st.warning('Bitiş dilimi başlangıçtan önce olamaz.');return
            gap=(first,last)
        simulated=[r for r in state.get('trk_requests',[]) if r.get('queue')=='SIMULATION' and str(r.get('start_date',''))<=day<=str(r.get('end_date') or r.get('start_date','')) and r.get('type') in {'Yıllık İzin Talebi','Mazeret İzni Talebi','Ücretsiz İzin Talebi'}]
        if simulated and state.get('profile',{}).get('position')=='wfm':
            st.markdown('**İzin talebini yeniden değerlendirme seçenekleri**')
            for col,req in zip(st.columns(min(3,len(simulated))),simulated[:3]):
                with col.container(border=True):
                    st.markdown('**'+req.get('created_by_name',req.get('created_by','Personel'))+'**');st.caption(req['type']+' · '+day);reason=st.text_input('İptal gerekçesi',key=key+'_cancel_reason_'+req['id'])
                    if st.button('Talebi İptal Et ve Mesaiyi Yeniden Değerlendir',key=key+'_cancel_req_'+req['id']):
                        try:
                            from ortak.talep_servisi import act
                            act(state,req,'cancel_planning',reason);state.pop(key+'_action_result',None);st.success('Talep iptal edildi. Aşağıdan uygun aksiyonları yeniden hesaplayın.');st.rerun()
                        except ValueError as e:st.warning(str(e))
        source_mode=st.segmented_control('Personel kaynağı',['Boş günü olanlar','Mevcut vardiyayı uzat','Her ikisi'],default='Her ikisi',key=key+'_source_mode') or 'Her ikisi'
        from ortak.personel import WORK_LABELS
        work_types=list(state.get('shift_rules',{}).get('work_type',{}));allowed=st.multiselect('Çalışma grubu',work_types,default=work_types,format_func=lambda value:WORK_LABELS.get(value,value),key=key+'_work_groups')
        signature=fingerprint(state)+str((day,gap,source_mode,allowed));cachekey=key+'_action_result'
        find_clicked=st.button('Önerileri Yeniden Hesapla',key=key+'_find_actions')
        current=state.get(cachekey)
        if find_clicked or not current or current.get('signature')!=signature:
            try:
                with st.spinner('Uygunluklar kontrol ediliyor…'):options,rejected=suggestions(state,day,*gap,source_mode=source_mode,allowed_groups=set(allowed))
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
        rows=[{'Personel':p['person']['full_name'],'Sicil':p['person'].get('sicil_no',p['row']['employee_id']),'Kullanıcı adı':p['person'].get('username'),'Grup':WORK_LABELS.get(p['person'].get('work_type'),p['person'].get('work_type','—')),'Aksiyon':p['kind'],'Yeni saat':p['row']['start']+'–'+p['row']['end'],'Kapatılacak personel-saat':p['gain']} for p in options]
        from html import escape
        for offset in range(0,len(rows),3):
            for col,row in zip(st.columns(3),rows[offset:offset+3]):
                col.markdown('<div style="min-height:175px;background:#f0f7fb;border:1px solid #d5e5ec;border-radius:17px;padding:17px;margin:7px 0"><div style="display:flex;justify-content:space-between;gap:8px"><b>'+escape(row['Personel'])+'</b><span style="font-size:11px;background:#dcecf2;color:#315f73;padding:4px 7px;border-radius:8px">'+escape(row['Grup'])+'</span></div><div style="font-size:23px;color:#277e91;margin:12px 0">'+escape(row['Yeni saat'])+'</div><small>'+escape(row['Aksiyon'])+f" · {row['Kapatılacak personel-saat']:.1f} kişi-saat açık azalır</small></div>",unsafe_allow_html=True)
        choice=st.selectbox('Uygulanacak öneri',list(range(len(options))),format_func=lambda i:rows[i]['Personel']+' · '+rows[i]['Yeni saat'],key=key+'_action_pick')
        reason=st.text_input('Aksiyon gerekçesi',key=key+'_action_reason')
        if st.button('Öneriyi Taslağa Uygula',disabled=not reason.strip(),key=key+'_action_apply'):
            from ortak.taslak_degisimleri import edit_shifts
            row={**options[choice]['row'],'source':'manual_single','note':reason}
            try:edit_shifts(state,[row]);st.success('Öneri taslağa işlendi. Güncel karşılaştırma için otomatik taslağı yeniden oluştur veya Vardiya Saatleri ekranını aç.')
            except ValueError as exc:st.error(str(exc))
