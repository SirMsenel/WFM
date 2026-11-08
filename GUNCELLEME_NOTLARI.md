# WFM — 8 Kasım 2026 / 6. güncelleme

## Çağrı tahmini ve mesai planı

- İşlenecek tarih aralığında kontroller hizalandı; başlangıç/bitiş tarihleri veri aralığından otomatik doluyor. Model kaydetme başlığına ayırıcı, kayıt sonrasına popup eklendi.
- Dört modelin günlük tahminleri üretildiği anda, elle girilen/seçilen tahmin de seçildiği anda SQLite'a kaydedilir. Artık interval/personel hesabı yapmayı beklemez. Yıllık ve dönemsel tahminler birbirini ezmez; Mesai Planı → Tahmin Kaynağı → Kayıtlı tahmin seç üzerinden tekrar kullanılabilir.
- Model seçimi üst tablosu başarı puanları yerine tarih bazında tahmin adetlerini gösterir. Altındaki karşılaştırma grafiği korunur.
- İstenen açıklama yazıları kaldırıldı; matris başlığı Haftanın Slot Ağırlıkları olarak sadeleştirildi. Personel Hesap'ta intervalin uygulanacağı başlangıç ve bitiş doğrudan seçilir. Bu seçim yalnızca hesaplanan ihtiyacı daraltır; kayıtlı tam günlük tahmin korunur.
- Geçmiş Hafta Analizi'ndeki teknik açıklamalar, gerçekleşen dosya yükleme alanı ve günlük çağrı sütunu seçimi kaldırıldı. Gerçekleşen çağrılar mevcut veri deposu/API üzerinden beslenmeye devam eder.

## Vardiya planı ve kurallar

- Dönem başlangıcı/bitişi ayrı kutular; ihtiyaç tablolarında gün/tarih tek satır. Fazladan açıklamalar kaldırıldı; çalışma saatleri özeti ayırıcıyla ayrıldı.
- Mesai Kuralları'nın alt bölümleri kartlara alındı. OFF dağıtım yaklaşımı seçimi kaldırıldı; grup bazında haftalık en az OFF günü seçilir. Dağıtımı sistem ihtiyaca göre yapar. Saat bütçesi ayrıca Çalışma Süreleri'ndeki kişi başına dönem üst sınırından gelir; otomatik motor ihtiyaç yokken yalnızca bütçeyi doldurmak için mesai yazmaz.
- Soft/Hard grup bitiş kuralları gerçekten ayrıldı. Hard aşımı engeldir. Soft aşımı uyarıdır; “Soft ihlalde onay iste” açıksa yayın öncesi ayrıca onay gerekir. Otomatik motor soft sınırı kendiliğinden aşmaz. Dinlenme, okul, günlük süre ve üst üste gün sınırları hard kalır.
- Her personelde en az 11 saat dinlenme ve en fazla 6 gün üst üste çalışma uygulanır. Önceki sürümlerde kaydedilmiş daha yüksek ardışık gün değerleri 6'ya çekilir.
- Talep detayındaki üç kart aynı yükseklik ve renkli başlıklara sahip. Planlama Talep Merkezi'ne Planlamaya iletilmeyi bekleyenler görünümü eklendi; ilgili lider adları görünür.
- Fazladan takvim açıklamaları, uzun eksik başlığı ve Oluştur ekranındaki tüm ham atama/30 dakika karşılaştırma alanı kaldırıldı. Ayrıntılı eksik analizi ve uygun aksiyon önerileri korundu.

## Vardiya değişim iş akışı

- Tüm Vardiyalar → Değişim Alanı → Yeni Değişiklik: personel/karşı personel ve gerçek vardiya günleri seçilir. Şimdiki ve onay sonrası takvim yan yana mantıkla iki önizleme olarak gösterilir. OFF alıp verilecek iki gün birlikte seçilir.
- Erken çıkış/geç girişte gün seçip Başlangıç/Bitiş hücresine yeni saat yazılır. Rapor girişini yalnızca TL kendi ekibi için başlatır. Yıllık/mazeret izni ayrı işlem türleridir.
- MT kendi değişimini talep eder; ilgili TL onayından sonra Planlama'ya gider. TL/Yönetici/Müdür önerileri Planlama onay kuyruğuna gider. Planlama da kendi düzenlemesini açıkça onaylar. Yayınlanmış takvimi yalnızca Planlama'nın son onayı değiştirir.
- **Vardiya değişimi** için aynı çalışma grubu ve aynı dil, eşit vardiya süresi, her personelin her takvim haftasında aynı OFF sayısı ve çalışma saati zorunludur. Saatler diğer kişinin o günkü gerçek vardiyasından alınır. Farklı haftalardaki OFF'lar toplamda dengeli görünse bile haftalık dengenin bozulması reddedilir. 7 saat ile 5 saatlik vardiya değiştirilemez. Dinlenme, ardışık gün ve okul kuralları son onayda yeniden kontrol edilir.
- Erken/geç giriş ve izin işlemleri vardiya takası değildir; çalışma saatini değiştirebilen ayrı devam/izin işlemleri olarak gerekçeyle kaydedilir.
- Gerekçe, önceki/yeni değer, talep eden, onaylayan, tarih ve işlem zamanı saklanır. Talep sonrası takvim değişmişse eski içerik uygulanmaz. Takvim, talep sonucu ve denetim kaydı aynı veritabanı işlemiyle güncellenir; hata olursa bütünüyle geri alınır.

## Takip, personel ve izleme

- Benim Vardiyam: yönetim rollerinin personel filtresi üstte; modern personel kartında ad soyad, şehir, şirket, takım lideri, yönetici, sicil/kullanıcı adı, grup ve dil bulunur.
- Ayrı kıdem kartı işe giriş tarihine göre 0–3 ay, 3–6 ay, 6–12 ay, 1–2 yıl, 2–3 yıl ve 3+ yıl renklerinden birini kullanır. Tarihi bulunmayan kişide veri bekleniyor gösterilir. Şirket alanı yerel personel kaydına ve kurumsal API eşleştirmesine eklendi.
- Vardiya tablosundaki Saat sütunu HH:MM biçimine çevrildi; istenmeyen açıklamalar kaldırıldı.
- Yönetim rollerinin ders/sınav/bayram görünümü düz liste yerine personel adı, gün/tarih, saat ve içeriği gösteren takvim kartları oldu. TL kapsamı kendi ekibi, diğer yönetim rolleri tüm personeller; MT kendi kayıtlarını düzenler.
- MT'nin Talep İlet ekranına erken çıkış ve geç giriş eklendi.
- İzleme ekranı hazır: erken çıkış/geç giriş işlemleri, rapor/yıllık izin günleri ve vardiya değişim sayıları tarih/personel filtresiyle izlenir. MT yalnızca kendisini, TL kendi ekibini, Yönetici/Planlama/Müdür tüm personelleri görebilir. Sayaçlar onaylanmış gerçek kayıtları kullanır.

## Tüm vardiyalar ve kayıt merkezi

- Tüm Vardiyalar'ın okuma kapsamı bütün roller için tüm MT vardiyalarıdır. Düzenleme/onay yetkileri bu geniş okumadan bağımsızdır. Takvimlerde yalnızca ad soyad ve tarih sütunları vardır.
- Yıl/ay seçimi kompakt iki seçici oldu. Eski büyük dönem kartı ve Düzenleme açıklamaları kaldırıldı.
- Gece/Yıllık İzin listeleri takvim görünümüne geçti. Onaylı talepler ayrıca kopyalanmadan aynı kaynak takvimde görünür ve planlamaya alınır.
- Gece başvurusunda dil/grup uygunluğu ve kontenjan kontrol edilir. Bekleyen başvurular da yer ayırır; dolu listeye başvuru yapılamaz. Ret/iptal kontenjanı serbest bırakır. Eşzamanlı başvurular için kontrol ile kayıt tek işlem içindedir. Onayda tekrar kontrol edilir; mevcut gece eksiği kontrolleri korunur.
- Veri ve Kayıt Merkezi alt ekranları: Günlük Tahminler, 30 Dakikalık Tahminler, Interval Profilleri, Açıklanan Vardiyalar, Vardiya Değişimleri, Talep Kayıtları, Personel İşlemleri, Yetki Geçmişi. Açıklanan ilk plan sürümü ve güncel hali incelenebilir.
- Tahmin/profil/yayın kayıtlarına kullanıcı başlığı verilebilir. Başlık değişikliği içerikteki tahmini veya arşivi değiştirmez.
- Alt ekran etiketi kaldırıldı. İlk girişte MT Takip'e, TL/Yönetici/Müdür İzleme'ye, Planlama Vardiya Planı'na açılır. Hesap değişiminde önceki hesabın alt ekran/personel filtreleri sıfırlanır.

## Yeni kategoriler ve kurum bağlantısı

Şehir ve şirketler personel verisinden okunur. Akademi/Dış Kaynak şehirleri sabit listeden gelmez; Rize gibi yeni şehirler filtre/takvimlere otomatik eklenir. Harita için Rize dahil il koordinatları bulunur; koordinatı tanımlı olmayan yer ayrıca belirtilir. Yeni bir **çalışma grubu** veya **rol**, şehrin aksine yeni çalışma/yetki kuralları gerektirir ve kendiliğinden mevcut gruplara eşlenmez.

Kurum API adresleri, gerçek veri şeması ve giriş protokolü hâlâ sağlanmayı bekliyor. Bu paket gerçek kurum bağlantısı yapıldığı anlamına gelmez. Ayrıntılar KURUMSAL_BAGLANTI.md içinde. Mevcut SQLite verileri korunur; şirket alanı ilk açılışta şemaya eklenir.
