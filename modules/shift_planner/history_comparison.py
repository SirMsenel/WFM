from datetime import timedelta
import pandas as pd
import streamlit as st

from core.forecast_service import date_column, daily_history, weekday_comparison


def render():
    st.title("Geçmişten Haftalık Çağrı Görünümü")
    st.caption("Lag: önceki haftanın aynı günü. Rolling: son iki hafta ve son 30 gün içindeki aynı hafta günlerinin ortalaması. Bunlar geçmişe dayalı karşılaştırmalardır; model tahmini olarak etiketlenmez.")
    raw = st.session_state.get("cf_all_df")
    if raw is None or raw.empty:
        st.info("Çağrı Tahmini → Veri Kaynağı ekranından çağrı geçmişini yükleyin veya Hazır Demo Veritabanı'nı kullanın.")
        return
    date_col = date_column(raw)
    numeric = list(raw.select_dtypes(include="number").columns)
    if not date_col or not numeric:
        st.warning("Tarih ve sayısal çağrı sütunu gerekli.")
        return
    preferred = st.session_state.get("cf_target_name", "cagri_sayisi")
    target = st.selectbox("Çağrı sayısı sütunu",numeric,index=numeric.index(preferred) if preferred in numeric else 0,key="history_target")
    try:
        history = daily_history(raw,target,date_col)
        cutoff = st.date_input("Geçmiş veri kesimi",value=history.tarih.max().date(),
                               min_value=history.tarih.min().date(),max_value=history.tarih.max().date(),key="history_cutoff")
        next_monday = cutoff+timedelta(days=7-cutoff.weekday())
        start = st.date_input("Karşılaştırılacak haftanın başlangıcı",value=next_monday,min_value=cutoff+timedelta(days=1),key="history_week_start")
        table = weekday_comparison(history,start,7,cutoff)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.caption(f"Yalnızca {cutoff} ve öncesindeki gerçekleşmeler kullanılır. Eksik geçmiş sıfır sayılmaz; örnek sayıları tabloda gösterilir.")
    columns = ["Geçen hafta aynı gün","Son 2 hafta aynı gün ort.","Son 30 gün aynı gün ort."]
    st.line_chart(table.set_index("Tarih")[columns])
    st.dataframe(table,hide_index=True,use_container_width=True)
    st.download_button("Hafta Karşılaştırması CSV İndir",table.to_csv(index=False).encode("utf-8-sig"),"hafta_gecmis_karsilastirma.csv","text/csv")
    options = st.session_state.get("cf_forecast_options",[])
    if options:
        joined = table[["Tarih","Gün"]].copy()
        for item in options:
            joined = joined.merge(item["frame"][["tarih","y_pred"]].rename(columns={"tarih":"Tarih","y_pred":item["name"]}),how="left",on="Tarih")
        st.markdown("### Aynı Günlerdeki Model Tahminleri")
        st.dataframe(joined,hide_index=True,use_container_width=True)
    st.markdown("### Son Dönemin Gerçekleşen Çağrıları")
    tail = history[(history.tarih <= pd.Timestamp(cutoff)) & (history.tarih > pd.Timestamp(cutoff)-pd.Timedelta(days=60))].copy()
    tail["7 günlük hareketli ortalama"] = tail.cagri_sayisi.rolling(7,min_periods=7).mean()
    tail["30 günlük hareketli ortalama"] = tail.cagri_sayisi.rolling(30,min_periods=30).mean()
    st.line_chart(tail.set_index("tarih"))
