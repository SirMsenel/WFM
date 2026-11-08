# Güncelleme notları — 8 Kasım 2026

## Planlama ve ihtiyaç

- Ana başlıklar 8 piksel aşağı alındı. Giriş ve sol panel mevcut başlık/simgeler korunarak yenilendi.
- Mesai Planı'ndaki ayrı eski kesim/son ödeme hesabı kaldırıldı. Kasım 2026 için 9 Kasım son ödeme, 10 Kasım değil; tüm ekranlar aynı takvim servisini kullanır. Takvim kuralı: kesimler 9/16/24/31, son ödeme +9 gün, hafta sonu pazartesiye kayar. Kurumun farklı bir takvimi varsa `ortak/odeme_takvimi.py` değişmelidir.
- Dönem 1–93 gün seçilebilir. İki hafta için Çağrı Tahmini'nde o tarih aralığının tahminini üretip Personel Hesap'ta ihtiyacı hesaplayın. İnterval profili varsayılan olarak haftanın günlerine göre tüm tahmin dönemine uygulanır; istenirse yalnızca profilin tarihleriyle sınırlanabilir.
- Dönem kartları sabit ölçülü; minimum/ortalama/zirve ihtiyaç ve çağrı toplamı görünür. Grafik de üç ihtiyaç ölçüsünü gösterir. Gün/tarih başlıkları kutuludur.
- Bekleyen taleplerde ve planlamayı durduran popup'ta onayı beklenen lider adları görünür.
- Ders dönemi tarihe göre seçilir, sınav günleri önceliklidir. Mesai Kuralları'nda Bayram önceliği açıksa bayram gününde ders/sınav kısıtı uygulanmaz. Varsayılan yaz ayları Haziran–Ağustos; normal dersler uygulanmaz, ayrıca girilmiş yaz sınavı varsa geçerlidir. Her vardiyada en az 11 saat dinlenme korunur.
- Grup bazlı minimum OFF ve ihtiyaca göre OFF dağılımı eklendi. OFF rezervasyonu tam takvim haftalarında uygulanır; kısa dönemlerde önceki/sonraki vardiyalarla haftalık gün/dinlenme kontrolleri sürer. Mevcut sabit kayıtlar değiştirilmez. Kaydet ve Uygula ile kuralları etkinleştirin.
- İhtiyaç varsa Full Time için tanımlı üst saate çıkılabilir; Akademi kendi üst süresine kadar değerlendirilir, Dış Kaynak 10 saattir. Kural ihlaliyle ihtiyaç kapatılmaz.
- Eksik tablosunda **Eksik için ne yapabilirim?** alanı gün ve saat bloğuna göre uygun ek mesai/süre uzatma adaylarını arar. Öneri yoksa engeller gösterilir. Seçilen öneri gerekçeyle taslağa işlenir; sonra taslak yeniden oluşturulup kontrol edilir. Motor sezgisel çalışır, küresel en iyi sonucu garanti etmez.

## Personel ve talepler

- Ekranlarda sicil no ve kullanıcı adı bulunur. Sabit iç personel kimliği kayıt ilişkileri için korunur; eski demo personelinin sicili mevcut iç kimlikten taşınır.
- Personel Ekleme / Ayrılma: TL önerir, ilgili Yönetici onaylar, Planlama sonlandırır. Ayrılma geçmiş kayıtları silmez. Gelecek işe giriş/ayrılma tarihleri vardiya uygunluğunda kontrol edilir.
- Benim Vardiyam personel kimlik kartı ve özetleri yenilendi. Normal mesai durumu **Çalışma**, saat dilimi renkleri ayrıca gösterilir. Tüm Vardiyalar aynı renk servisini kullanır.
- MT değişim talebinde yalnızca diğer Müşteri Temsilcileri ve gerçek kayıtlı vardiyalar seçilir. Birden fazla gün aynı talebe eklenir. Her kişinin OFF sayısı ve toplam saati korunmalıdır. Önizleme bu dengeyi açıklar; son onayda güncel kurallar yeniden doğrulanır.
- Rapor bildirimini/girişini yalnızca Takım Lideri kendi ekibi için yapar. Diğer roller rapor giriş yetkisi alamaz.
- Rol adları Müşteri Temsilcisi, Takım Lideri, Yönetici, Planlama, Müdür olarak birleştirildi.

## Yayınlanan vardiya ve kayıtlar

- Tüm Vardiyalar → Değişim Alanı: TL kendi ekibini, Yönetici/Planlama yetkili olduğu kayıtları düzenler. Müdür de yetkilendirilen yönetim işlemlerine erişir.
- Değişiklikte gerekçe zorunlu; eski/yeni değer, vardiya tarihi, işlemi yapan ve işlem zamanı saklanır. Vardiya değişimi her kişinin OFF/saat toplamını korur. Erken çıkış, geç giriş ve izinler ayrı devam/izin işlemleri olarak kaydedilir.
- Onaylanan dengeli değişim talebi yayınlanan vardiyalara aitse tablo, talep sonucu ve denetim kaydı aynı SQLite işleminde güncellenir. Eşzamanlı değişiklik veya geçersiz talepte işlem bütünüyle geri alınır. Taslak kayıtlarına ait onaylar planın kaynaklarına alınır.
- **Veri ve Kayıt Merkezi** yalnızca Planlama, Yönetici, Müdür içindir: günlük/30 dk tahminler, interval profilleri, vardiya değişiklikleri, talepler, personel işlemleri, yetki/denetim geçmişi.
- **Ayarlar → Yetkilendirme** Planlama tarafından yönetilir. Değişiklikler denetim kaydına yazılır; rol bazlı sabit sınırlar (rapor ve yetki yönetimi gibi) korunur.
- Sentetik alana bir geçmiş haftanın tahmin ve dağılım kaydı eklenir. Eğitim verisi hedef haftadan öncedir; kayıt bugün oluşturulduğu için geriye dönük demo olduğu açıkça belirtilir. Gerçek operasyon başarısı gibi sunulmaz.

## Kod ve kurum bağlantısı

Asıl uygulama `arayuz.py`, sunucu `sunucu.py`, ortak servisler `ortak/` altındadır. Ekran klasörleri Türkçeleştirildi. Eski yollar uyumluluk için bırakıldı. Ayrıntılar `DOSYA_HARITASI.md` dosyasında.

Personel ve kurumsal giriş HTTP adaptörleri, çağrı besleme servisi ve demo/kurum ayrımı hazırlandı. Gerçek API adresleri, kurum giriş protokolü ve veri şeması sağlanınca bağlanacak. Kurum HR yazma işlemi ve doğrudan PostgreSQL/SQL Server bağlantısı henüz kurulmadı. Ayrıntılar ve gereken ortam değişkenleri `KURUMSAL_BAGLANTI.md` dosyasında.
