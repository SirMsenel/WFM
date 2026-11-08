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
