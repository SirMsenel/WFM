# Türkçe dosya haritası

Uygulama `arayuz.py`, servis `sunucu.py` üzerinden çalışır. Ekran dosyaları `modules/` altında Türkçe adlandırılmıştır. `ortak/` ortak kuralları ve kayıt servislerini içerir.

Eski İngilizce yollar yalnızca uyumluluk dosyalarıdır; değişiklik yaparken aşağıdaki asıl dosyaları kullanın. Python dosya adlarında Türkçe karakter yerine ASCII kullanılmıştır. İçerikte başlıklar Türkçedir; kurum API alanları ve veri kolonları uyumluluk için korunur.

| Önceki yol | Asıl dosya |
|---|---|
| `backend.py` | `sunucu.py` |
| `core/academic_view.py` | `ortak/okul_gorunumu.py` |
| `core/api_client.py` | `ortak/servis_istemcisi.py` |
| `core/arayuz_tasarimi.py` | `ortak/arayuz_tasarimi.py` |
| `core/auth_ui.py` | `ortak/kimlik_gorunumu.py` |
| `core/billing_calendar.py` | `ortak/odeme_takvimi.py` |
| `core/calisma_modu.py` | `ortak/calisma_modu.py` |
| `core/charts.py` | `ortak/grafikler.py` |
| `core/conflict_cleanup.py` | `ortak/cakisma_temizleme.py` |
| `core/data_cache.py` | `ortak/veri_onbellegi.py` |
| `core/defaults.py` | `ortak/varsayilan_kurallar.py` |
| `core/demo_data.py` | `ortak/ornek_veri.py` |
| `core/eksik_aksiyonlari.py` | `ortak/eksik_aksiyonlari.py` |
| `core/forecast_ledger.py` | `ortak/tahmin_kayit_servisi.py` |
| `core/forecast_service.py` | `ortak/cagri_tahmin_servisi.py` |
| `core/interval_edit_ui.py` | `ortak/interval_duzenleme_ekrani.py` |
| `core/interval_editing.py` | `ortak/interval_dengeleme.py` |
| `core/interval_service.py` | `ortak/interval_servisi.py` |
| `core/kurumsal_baglanti.py` | `ortak/kurumsal_baglanti.py` |
| `core/manual_assignments.py` | `ortak/elle_yerlestirme.py` |
| `core/navigation.py` | `ortak/gezinme.py` |
| `core/night_checks.py` | `ortak/gece_kontrolleri.py` |
| `core/off_dagilimi.py` | `ortak/off_dagilimi.py` |
| `core/ornek_gecmis_tahmin.py` | `ortak/ornek_gecmis_tahmin.py` |
| `core/personel_deposu.py` | `ortak/personel_deposu.py` |
| `core/personel_is_akisi.py` | `ortak/personel_is_akisi.py` |
| `core/personnel.py` | `ortak/personel.py` |
| `core/personnel_charts.py` | `ortak/personel_grafikleri.py` |
| `core/plan_publication.py` | `ortak/yayin_servisi.py` |
| `core/planning.py` | `ortak/planlama.py` |
| `core/planning_guard.py` | `ortak/donem_kilitleri.py` |
| `core/planning_ui.py` | `ortak/planlama_gorunumu.py` |
| `core/profiles.py` | `ortak/profil_yonetimi.py` |
| `core/request_assignments.py` | `ortak/talep_yerlestirme.py` |
| `core/request_service.py` | `ortak/talep_servisi.py` |
| `core/request_ui.py` | `ortak/talep_gorunumu.py` |
| `core/roller_ve_yetkiler.py` | `ortak/roller_ve_yetkiler.py` |
| `core/rule_service.py` | `ortak/mesai_kurallari_servisi.py` |
| `core/shift_display.py` | `ortak/vardiya_gorunumu.py` |
| `core/shift_edits.py` | `ortak/taslak_degisimleri.py` |
| `core/status_style.py` | `ortak/durum_renkleri.py` |
| `core/time_labels.py` | `ortak/saat_etiketleri.py` |
| `core/vardiya_degisimleri.py` | `ortak/vardiya_degisimleri.py` |
| `core/work_hours.py` | `ortak/calisma_sureleri.py` |
| `core/work_hours_ui.py` | `ortak/calisma_sureleri_ekrani.py` |
| `core/workspace_store.py` | `ortak/calisma_alani_deposu.py` |
| `modules/PersonelTakip/Personel_talep.py` | `modules/personel_takip/personel_talepleri.py` |
| `modules/PersonelTakip/personel_yasam_dongusu.py` | `modules/personel_takip/personel_yasam_dongusu.py` |
| `modules/PersonelTakip/personnel_list.py` | `modules/personel_takip/personel_listesi.py` |
| `modules/all_shifts/_common.py` | `modules/tum_vardiyalar/ortak.py` |
| `modules/all_shifts/_fixed_records.py` | `modules/tum_vardiyalar/kesin_kayitlar.py` |
| `modules/all_shifts/_shift_grid.py` | `modules/tum_vardiyalar/takvim.py` |
| `modules/all_shifts/academy.py` | `modules/tum_vardiyalar/akademi.py` |
| `modules/all_shifts/annual_leave.py` | `modules/tum_vardiyalar/yillik_izin.py` |
| `modules/all_shifts/foreign_language.py` | `modules/tum_vardiyalar/yabanci_dil.py` |
| `modules/all_shifts/fulltime.py` | `modules/tum_vardiyalar/tam_zamanli.py` |
| `modules/all_shifts/night.py` | `modules/tum_vardiyalar/gece.py` |
| `modules/all_shifts/outsource.py` | `modules/tum_vardiyalar/dis_kaynak.py` |
| `modules/all_shifts/vardiya_duzenleme.py` | `modules/tum_vardiyalar/vardiya_duzenleme.py` |
| `modules/all_shifts/weekend_owner.py` | `modules/tum_vardiyalar/hafta_sonu_sorumlu.py` |
| `modules/auth/login_screen.py` | `modules/kimlik/giris_ekrani.py` |
| `modules/call_forecast/components.py` | `modules/cagri_tahmini/bilesenler.py` |
| `modules/call_forecast/data_quality.py` | `modules/cagri_tahmini/veri_kalitesi.py` |
| `modules/call_forecast/data_source.py` | `modules/cagri_tahmini/veri_kaynagi.py` |
| `modules/call_forecast/feature_engineering.py` | `modules/cagri_tahmini/etken_uretimi.py` |
| `modules/call_forecast/model_report.py` | `modules/cagri_tahmini/model_raporu.py` |
| `modules/call_forecast/modeling.py` | `modules/cagri_tahmini/model_kur.py` |
| `modules/call_forecast/monitoring.py` | `modules/cagri_tahmini/grafik_izleme.py` |
| `modules/call_forecast/outlier_iqr.py` | `modules/cagri_tahmini/aykiri_deger.py` |
| `modules/call_forecast/predict_ui.py` | `modules/cagri_tahmini/tahmin.py` |
| `modules/demo_workspace.py` | `modules/ornek_calisma_alani.py` |
| `modules/shift_planing/current_plan.py` | `modules/vardiya_plani/mevcut_plan.py` |
| `modules/shift_planing/engine.py` | `modules/vardiya_plani/vardiya_motoru.py` |
| `modules/shift_planing/period.py` | `modules/vardiya_plani/donem_secimi.py` |
| `modules/shift_planing/planning_data.py` | `modules/vardiya_plani/planlama_verileri.py` |
| `modules/shift_planing/publication_management.py` | `modules/vardiya_plani/yayin_yonetimi.py` |
| `modules/shift_planing/publish.py` | `modules/vardiya_plani/olustur_kontrol_yayinla.py` |
| `modules/shift_planing/requests_tab.py` | `modules/vardiya_plani/talepler.py` |
| `modules/shift_planing/shift_hours.py` | `modules/vardiya_plani/vardiya_saatleri.py` |
| `modules/shift_planner/forecast_view.py` | `modules/mesai_plani/tahmin_kaynagi.py` |
| `modules/shift_planner/history_comparison.py` | `modules/mesai_plani/gecmis_hafta_analizi.py` |
| `modules/shift_planner/intraday_ratio.py` | `modules/mesai_plani/interval_dagilimi.py` |
| `modules/shift_planner/performance_tracking.py` | `modules/mesai_plani/guncel_takip.py` |
| `modules/shift_planner/ratio_profile_select.py` | `modules/mesai_plani/kayit_secimi.py` |
| `modules/shift_planner/staffing_forecast.py` | `modules/mesai_plani/personel_ihtiyaci.py` |
| `modules/tracking/class_schedule.py` | `modules/takip/ders_programi.py` |
| `modules/tracking/my_shift.py` | `modules/takip/benim_vardiyam.py` |
| `modules/tracking/requests_inbox.py` | `modules/takip/talep_sonuclari.py` |
| `modules/tracking/requests_submit.py` | `modules/takip/talep_ilet.py` |
| `ui.py` | `arayuz.py` |

## 6. güncellemede eklenen kaynaklar

| Ekran / işlev | Kaynak |
|---|---|
| Günlük tahmin arşivi | `ortak/gunluk_tahmin_deposu.py` |
| Kullanıcı kayıt başlıkları | `ortak/kayit_basliklari.py` |
| Değişim formu ve önizleme | `ortak/degisim_ekrani.py` |
| Değişim önerisi ve Planlama onayı | `ortak/degisim_onaylari.py` |
| Ortak gece/izin kaynakları ve kontenjan | `ortak/kesin_kayit_deposu.py` |
| Ortak takvim | `ortak/takvim_gorunumu.py` |
| Personel/kıdem kartı | `ortak/personel_karti.py` |
| Rol ve başlangıç ekranı | `ortak/erisim.py` |
| İzleme | `modules/izleme.py` |


## 7. faz
- `ortak/sabit_demo.py`: sabit tarihli örnek personel, çağrı metrikleri, ayrı vardiya geçmişi.
- `ortak/statuler.py`, `modules/statu_kurallari.py`: yemek/statü ve dilim shrinkage.
- `modules/vardiya_kurallari.py`: kompakt Mesai Kuralları.
- `ortak/yayin_onaylari.py`, `modules/yayin_onay_ekrani.py`: iki planlamacı ve yönetici onayı.
- `ortak/talep_simulasyonu.py`: üstlenme, simüle etme, yayın anında kesinleşme.
- `ortak/mola_servisi.py`, `modules/mola_izleme.py`: atomik mola kapasitesi ve kişisel ekran.
- `ortak/canli_metrikler.py`: gerçekleşen SL/AHT ve Erlang ihtiyaçları.
- `ortak/moderator_gecis.py`, `sunucu.py /auth/switch-*`: denetimli kullanıcı görünümü.
- `ortak/gorusler.py`, `modules/similasyon.py`, `ortak/dagilim_adetleri.py`: geri bildirim, kapasite senaryoları, adet matrisi.

## Faz 2
- `ortak/veri_secimi.py`: tarih/sayı kontrolüyle kaynak sütunu seçimi.
- `ortak/izleme_analitigi.py`, `modules/mesai_plani/canli_izleme.py`: tolerans, renk ve ortak takip.
- `ortak/statu_planlayici.py`: shrinkage dahil yemek/mola/aylık koçluk dağıtımı.
- `ortak/zorunlu_alanlar.py`, `ortak/modern_kartlar.py`: boş alan kontrolü ve ortak bilgi kartları.
- `ortak/bildirimler.py`, `modules/bildirim_kutusu.py`: kapsamlı bildirim kaydı ve kişi bazlı okundu durumu.

## Faz 3
- `ortak/ajanda_servisi.py`, `modules/ajanda.py`: çalışma ajandası, ekip/hat uygunluğu ve koçluk.
- `ortak/statu_degisimleri.py`, `modules/statu_degisimi.py`: karşı personel + lider onaylı yemek/mola değişimi.
- `ortak/statu_gecmisi.py`: örnek/gerçek statü verisi ve ölçülen shrinkage.
- `modules/statu_analizi.py`, `ortak/statu_kartlari.py`: dağılım ve kişisel statü kartları.
- `modules/onay_merkezi.py`, `ortak/bildirim_popup.py`: ortak onaylar ve giriş bildirimleri.
- `ortak/donem_uyarisi.py`, `ortak/plan_ihtiyaci.py`: yayınlı dönem uyarısı ve dile özel ihtiyaç.
- `modules/vardiya_plani/yabanci_dil_plani.py`, `ortak/yayin_hucreleri.py`: dil planı ve atomik hücre/statü düzeltmesi.
- `ortak/okul_shiftleri.py`, `ortak/senaryolar.py`: okul görünümü ve geçmişten senaryo hesapları.
