# Kurumsal veritabanı ve API bağlantıları

Bu sürümde personel ve kimlik doğrulama için HTTP adaptörleri, gerçekleşen çağrılar için servis ve SQLite kayıt deposu bulunur. Kurum adresleri, veri sözleşmesi ve SSO yöntemi henüz sağlanmadığından gerçek kurum bağlantısı yapılmış değildir. Kurumda OIDC/SAML kullanılıyorsa kimlik adaptörü o protokole uyarlanmalıdır; mevcut adaptör HTTPS giriş + kullanıcı bilgisi servisi bekler.

## Çalışma modu

Varsayılan yerel demo modudur. Kurumsal modda ayrı, yeni bir çalışma veritabanı kullanın; sentetik demo veritabanını kurumsal verinin üzerine kopyalamayın. Ortam değişkenlerini hem `sunucu:app` hem `arayuz.py` işlemlerinde aynı ayarlayın.

| Değişken | İşlev |
|---|---|
| `WFM_DEMO_MODE=false` | Sentetik personel, çağrı, örnek talep ve geçmiş tahmin üretimini kapatır. |
| `WFM_WORKSPACE_DB_PATH` | Tahmin, çağrı, talep, vardiya, onay ve denetim kayıtlarının SQLite dosyası. |
| `WFM_AUTH_DB_PATH` | Yerel kimlik deposu. Kurumsal girişte demo parolasına geri dönüş yapılmaz. |
| `BACKEND_URL` | Arayüzün yerel WFM servis adresi; varsayılan `http://127.0.0.1:8001`. |
| `WFM_PERSONNEL_API_URL` | Personel listesi için HTTPS GET adresi. |
| `WFM_DIRECTORY_TOKEN` | Gerekirse personel servisi Bearer belirteci. |
| `WFM_IDENTITY_MODE=api` | Kurumsal kimlik adaptörünü açar. |
| `WFM_AUTH_API_URL` | `{username, password}` JSON alanlarıyla HTTPS POST. Yanıt: `{access_token}`. |
| `WFM_AUTH_USERINFO_URL` | Kurum belirteciyle HTTPS GET; doğrulanmış personel profili döner. |
| `WFM_JWT_SECRET` | Kurumsal modda zorunlu, rastgele ve güçlü uygulama imzalama anahtarı. |

Personel veya kurumsal kimlik adresi ayarlanırsa demo varsayılan olarak kapanır; yine de `WFM_DEMO_MODE=false` açıkça ayarlayın. Özel anahtarları kaynak koduna veya ZIP'e yazmayın. Kurum erişim belirteci ve parola denetim kayıtlarına kaydedilmez. Uygulama kurumsal girişten sonra 15 dakikalık kendi oturum belirtecini üretir. Yetki değişikliği yeni işlemlerde kontrol edilir; kurum hesabının iptalinin uygulamaya yansıması için oturumun yenilenmesi gerekir.

## Personel sözleşmesi

GET yanıtı tüm personellerin listesi veya `{items: [...]}` olmalıdır. Sayfalı servis verilirse tüm sayfaları okuyan adaptör eklenmelidir. Gerekli alanlar: `employee_id` (sabit iç kimlik), `sicil_no` (metin; baştaki sıfırlar korunur), `username`, `full_name`, `position`.

`employee_id` yoksa sicil numarası iç kimlik olarak kullanılır. Bundan sonra aynı personelin kimliğini değiştirmeyin; sicil numarası değişebiliyorsa ayrıca sabit `employee_id` sağlayın. `kullanici_adi`, `ad_soyad`, `registry_no`, `rol` eşdeğer alanları da okunur.

Planlamada ayrıca `team_lead`, `manager`, `location`, `work_type`, `language`, `is_active`, `employment_start`, `employment_end`, `company` gerekir. `company` için `sirket` eşdeğeri de okunur; işe giriş tarihi kıdem kartını besler. Tarihler ISO `YYYY-MM-DD`; ayrılma tarihinden itibaren çalışma/giriş kapatılır. Rol kodları `agent`, `tl`, `manager`, `wfm`, `moderator`; ekrandaki karşılıkları Müşteri Temsilcisi, Takım Lideri, Yönetici, Planlama, Müdür. Çalışma grupları `fulltime`, `akademi`, `dis_kaynak`; diller `tr`, `en`, `ar`. İlişkiler bu sürümde lider/yönetici adıyla eşleşir; kurumdan sabit lider/yönetici kimlikleri gelirse adaptörde eşleştirme yapılmalıdır.

Personel ekleme/ayrılma iş akışı TL → ilgili Yönetici → Planlama şeklinde yerelde tamamlanır. Kurumsal modda talepler ve onay geçmişi saklanır, ancak son HR yazma işlemi kurum yazma servisi tanımlanana kadar engellenir. Böylece yalnızca yerel bir değişiklik yapıp kurumda tamamlanmış gibi görünmez. Ayrılan personelin geçmişi silinmez.

## Çağrı besleme

`POST /actuals/intervals` planlama rollerine açık uygulama Bearer belirteciyle çalışır. JSON gövde örneği:

```json
{"rows":[{"tarih":"2026-11-09","slot":17,"cagri_sayisi":120,"aht_sec":250}]}
```

`slot` 1–48; 1=00:00–00:30, 17=08:00–08:30. `tarih` yarım saat başlangıcı da olabilir; saat varsa slotla tutarlı olmalıdır. Bir dilim tekrar gönderilirse gerçekleşen güncellenir, diğer dilimler korunur. Tamamlanmamış günün günlük toplamı tam gün sayılmaz. Günlük toplamı yeniden hesaplamak için 48 dilimi gönderin. Yalnızca günlük çağrı geçmişi ayrı kurumsal kaynaktaysa günlük okuma adaptörü ayrıca bağlanacaktır; günlük toplamları uydurma 30 dk veriye çevirmeyin.

Üretilen/seçilen günlük tahminler interval hesabından bağımsız `daily_forecasts` tablosunda saklanır. Kullanılmış tahmin ve dağılımlar `forecast_runs`, `forecast_slots`, `profile_versions` tablolarında sürümlüdür. Gerçekleşenlerin değişmesi eski tahminleri ezmez. `GET /forecast-ledger/runs`, `/forecast-ledger/runs/{id}/slots` servisleri geçmişi okur. Ayrıntılı şema: `ortak/tahmin_kayit_servisi.py`.

## Dosyalar ve geçiş sınırı

- `ortak/personel_deposu.py`: personel okuma ve sicil eşleştirme.
- `ortak/kurumsal_baglanti.py`: kurum HTTP adaptörleri.
- `ortak/calisma_alani_deposu.py`: kalıcı çalışma verisi.
- `ortak/vardiya_degisimleri.py`: atomik değişim kontrolü ve denetim kaydı.
- `sunucu.py`: uygulama servisleri ve giriş doğrulaması.

Bu, yerel prototipten kurum sistemine geçiş hazırlığıdır. Mevcut dosya yükleme/personel uçları dahil tüm servislerin kurum ağına açılması öncesinde kurumun erişim, SSO ve veri saklama politikalarıyla birlikte servis yetkilendirmesi tamamlanmalıdır. PostgreSQL/SQL Server bağlantısı ve kurum HR yazma servisi bu sürümde kurulmuş değildir. SQLite dosyaları aynı makinedeki iki uygulama sürecinin ortak deposudur; çok sunuculu kullanım için ortak sunucu veritabanı adaptörü gerekir.

## 7. faz ek alanlar
Personelde `gender` alanı (örnek değerler Kadın/Erkek) Cuma erkek filtresi için isteğe bağlıdır. `employment_start`, `employment_end`, `company`, `sicil_no`, `username` alanları korunur. Yeni rol `planning_manager` = Planlama Yöneticisi.

`POST /actuals/intervals` satırları `tarih`, `slot` (1–48), `cagri_sayisi`, isteğe bağlı `aht_sec`, `answered`, `answered_target`, `staffed` alır. Sayımlar negatif olamaz; `answered_target <= answered <= cagri_sayisi`. `staffed` o dilimdeki gerçek etkin personel sayısıdır. SL hedef sürede karşılanan/gelen üzerinden hesaplanır. Yetkili Planlama hesabı gerekir. Kurumsal akış bu uç noktaya henüz bağlanmış değildir.

Yemekler `planned_breaks`, kişisel molalar `break_requests`, yayın onayları `plan_approvals`, sabit örnek vardiyalar `roster_history`, gerçek operasyon metrikleri `interval_operations` tablolarında tutulur. Kullanıcı geçişi yalnızca asıl moderatör tokenı ile yapılır; imzalı token gerçek aktör bilgisini taşır.

## Faz 2 hesap ve bildirim notu
Shrinkage artık yemek/mola/koçluk dahil toplam kayıp oranıdır; kurum oranının aynı tanımı kullandığını doğrulayın. Planlı statüler bütçeyi aşarsa yalnızca aşan bölüm ek kayıp oluşturur. Statü süre hakları `status_rules` içindedir; saatleri yerel planlayıcı üretir. Kurum durum/telefon sistemi entegrasyonu bu pakette kurulmaz; otomatik saatler uygulamanın kendi Takip/İzleme ekranlarına düşer.

`notification_reads` tablosu kullanıcı/bildirim bazında okundu durumunu tutar; içerikler yetkili talep/yayın/görüş kaynaklarından türetilir. E-posta veya dış mesaj servisi kurulmuş değildir.

## Faz 3
Yeni rol `assistant_manager` / Yönetici Yardımcısı; yeni cinsiyet kuralları için `gender` değerlerini Kadın/Erkek olarak eşleştirin. Moderatörün imzalı tokenındaki actor_sub gerçek işlem yapanı korur; hedef hesap yetkileri uygulanır.

`POST /actuals/statuses` yalnızca WFM/Planlama Yöneticisi tokenıyla çalışır. Gövde: `{"rows":[{"id":"kurum-kayit-1","employee_id":"sabit-ic-kimlik","kind":"Mola","start":"2026-11-09 10:00:00","end":"2026-11-09 10:15:00"}]}`. Türler Yemek/Mola/Koçluk/Cuma. Aynı id güncellenebilir; geçmiş kaynak source=actual olarak tutulur. Sicil no önce mevcut personel adaptöründeki sabit iç kimliğe eşlenmelidir. Zamanlar Türkiye yerel saatiyle tutarlı gönderilmelidir. Kurumun telefon/statü sağlayıcısına henüz bağlanmış değildir.

`status_actuals`: gerçekleşme verisi (source=actual/synthetic). `manager_agenda`: yönetim çalışması/koçluk. `status_swap_requests`: iki aşamalı statü değişim onayı. `language_demands`: work_state içinde dile özel ihtiyaç. Yeni tablo/sütunlar ilk açılışta eklenir; kurum modunda sentetik veri/hesap eklenmez. Eksik statü kayıtlarıyla elde edilen shrinkage tam devamsızlık/eğitim kaybı değildir.

Yeni tahmin kayıtlarının metadata.staffing_parameters alanı özgün Erlang ayarlarını taşır; eski kayıtlarda bu alan yoksa özgün tahmini SL bilinmiyor kabul edilir.


## Faz 4
`coaching_openings(id,publication_id,employee_id,status,payload)` yayınlanmış fakat henüz lidere atanmış görüşme olmayan koçluk kapasite alanlarını tutar. Açık alan lider atamasıyla Atandı olur; atama `manager_agenda` ve `planned_breaks` içine yazılır. İptal/yeniden planlama durumları arşivlenir. Alanlar vardiya tarih/saatinden bağımsız gerçek görüşme sayılmamalıdır. Kurum takvimi entegrasyonu ayrıca gerekir.

Gün bazlı `slot_shrinkage` kuralı örneği: `{"weekdays":[5,6],"start_slot":17,"end_slot":34,"rate":0.15}` (Pazartesi=0). Son eşleşen satır uygulanır. Geriye dönük sentetik tahminler metadata.forecast.synthetic/retrospective alanlarıyla ayırt edilir; kayıt zamanı üretim anıdır.
