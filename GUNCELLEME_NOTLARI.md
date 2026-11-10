# WFM — Faz 2 / 10 Kasım 2026 / 8. güncelleme

## Çağrı verisi ve analiz
- Veri Kaynağı'nda işlenecek sütunlar seçilir; tarih ve sayısal çağrı sütunu zorunludur. Kaynak veri korunur, kaldırılmış sütunlar yeniden seçilebilir. Tarih kapsamı seçimiyle birlikte çalışır.
- Grafik İzleme: seçilen dönem, önceki dönem günlük ortalama değişimi, veri bulunan gün oranı, günlük eğilim, 7 günlük ortalama, geçmiş 4 aynı hafta günü referansı, yoğun 5 gün, interval verisinde gün×saat ısı haritası ve eşik dışı sapmalar. 30 dakikalık kaynakta slotlar gerçek saatlere çevrilir. Eksik günler 0 sayılmaz.
- Kayıt Seçim'de Çağrı Adetleri, Gün Tabloları'nın yanındaki alt sekmedir; sayfa altında tekrar edilmez. Interval ekranına geri dönme maddesi kullanıcının açıklamasıyla kapsam dışıdır.
- Ana başlık 📈 Güncel Takip Analizi oldu. Canlı İzleme altında Servis Seviyesi İzleme ve Tahmin İzleme ayrıldı; diğer analizler korunur. AHT ekranda gösterilmez.
- İki takip görünümü aynı düzendedir. Kullanıcı kabul edilen farkı belirler: tahminde mutlak yüzde farkı, SL'de hedefe göre mutlak yüzde puan farkı. Sınır dahilindekiler yeşil, dışındakiler fark arttıkça koyu kırmızı; ölçüm dışı ve eksik veri gridir. Genel başarı yalnızca ölçülen, yüzdesi hesaplanabilen dilimlerden gelir. SL = hedef sürede karşılanan / gelen çağrı.

## Vardiya ve statü kuralları
- Plan dönemindeki alt bölüm yeniden tasarlandı: ayrı başlangıç/bitiş, renkli dönem özeti ve onay rozeti. Uzun açıklama ve tekrarlanan başlık kaldırıldı.
- Mesai Kuralları'nda üst iki kutu aynı boyda; Dış Kaynak, Akademi, Full Time aynı satırdaki eş boy kartlardır. Full Time ve Dış Kaynak süreleri düzenlenebilir; kaydedilen süre eski 10 saat migrasyonu tarafından ezilmez. 11 saat dinlenme ve en fazla 6 ardışık gün korunur.
- Statü Kuralları ayrı Yemek, Mola, Koçluk, Cuma pencereleridir. Grupların süre hakları girilir; kullanıcı yemek başlangıç/bitiş penceresi seçmez. Sistem vardiya içinde hattın durumuna göre saatleri seçer. Eski teknik shrinkage açıklaması kaldırıldı.
- Mola hakkı çalışılan saat aralığına göre tanımlanır (alt sınır dahil, üst sınır hariç); toplam süre, bir mola üst süresi ve bir saatlik mola üst sınırı ayrı kontrol edilir. Otomatik yerleşen molalar kişisel mola hakkından düşer.
- Aylık koçluk varsayılan 60 dakika, parça varsayılan 15 dakikadır. Önceki yayınlarda planlanan koçluklar düşülür; kişi başına günde en fazla bir parça atanır. Uygun kapasite yoksa mola/koçluk ertelenir ve uyarı oluşur. Kısa dönemde hedef tamamlanmazsa sonraki dönemlerde kalan hedef devam eder.
- Yemek çalışma vardiyası içinde zorunlu süre olarak yerleştirilir; uygun pencere yoksa yayın engeli doğar. Mola/koçluk yeni kapasite açığı oluşturmadan yerleşir. Yemek/mola/koçluk yayın onayları tamamlandığında personelin İzleme ve Takip ekranlarında görünür; taslak henüz personele açıklanmaz.
- **Bu sürümde shrinkage yemek, mola ve koçluk dahil toplam kayıptır.** Planlı statü kaybı shrinkage bütçesi içindeyse ikinci kez düşülmez. Bütçeyi aşan kısmı ek açık olarak görünür. Net kapasite = brüt atanan − max(brüt atanan × shrinkage, planlı statü kaybı). Karşılaştırma tabloları önceki brüt ihtiyaç birimini korur. Önceki sürümün “diğer kayıplar + ayrıca yemek” yaklaşımının yerini bu alır; oranları buna göre gözden geçirin.
- Boş statü/mola/shrinkage hücrelerinde alanı belirten uyarı gösterilir; eksik satır sessizce silinmez. Boş saat/tarih alanlarında kod hatası yerine doldurma mesajı gösterilir.

## Talepler ve yayın
- Bekleyen talebi es geçme işlemi uyarı penceresinin içinde de kullanılabilir. Planlamacı gerekçe yazarak devam eder; talepler kendiliğinden onaylanmaz. Yayınlanmış dönem kilidi es geçilemez.
- Geçmiş bir günü içeren yayın geri alınamaz veya taslağa taşınamaz. Bugün/future başlangıçlı yayında önceki geri alma kontrolleri korunur.
- Aynı dönemle kesişen aynı dil için onay bekleyen plan varsa ikinci taslak gönderilemez. Kontrol veritabanında eşzamanlı gönderimlere karşı da yapılır; reddedilen ikinci gönderim ilk taslağın kaynaklarını kaydetmez.
- Onaylayanların adı, kullanıcı adı, rolü ve onay zamanı tüm yetkili oturumlarda veritabanından okunur. Planlama Yöneticisi onayı da listede görünür. Son gerekli onaydan sonra plan **otomatik yayınlanır**; ekranda açık başarı mesajı çıkar. Tüm Vardiyalar ve kişisel Takip ekranlarından görülür.
- İki farklı gerçek Planlama hesabı, açık %5 üzerindeyse ayrıca Planlama Yöneticisi gerekir. Moderatörün hesap görünümünü değiştirmesi bağımsız ikinci kişi sayılmaz.

## Takip, takvim ve bildirimler
- Benim Vardiyam sayfa içi başlığı kaldırıldı. Toplam saat/çalışma/OFF/rapor/izin kartları renkli modern tasarıma geçti. Kişisel vardiya tablosu ortak shift takvimini kullanır; ayrı Durum sütunu yoktur.
- Tüm Vardiyalar başlıkları modern Vardiya Planı formatına geçti; yıl, ay ve ortak personel araması tek satıra alındı. Tek arama konum sekmelerine de uygulanır.
- Planlama Talep Merkezi'nin büyük üç özet kutusu küçük renkli durum rozetleri oldu. Sol üst personel kartında ad/kullanıcı adı taşması azaltıldı.
- Sol menüde 🔔 Bildirimler ve Ayarlar → Bildirimler bulunur. Kapsama uygun talep sonucu, plan onay durumu, yayınlanan vardiya ve uygulama görüşüne yanıt listelenir. Konu/okunmamış filtreleri ve kişiye özel okundu durumu kalıcıdır. Kullanıcı başkasının bildirimini okundu yapamaz.
- Uygulama görüşleri yetkili Planlama/Müdür tarafından yanıtlanabilir; yanıt bildirim kutusuna düşer. Anonim şikâyetin sahibi kendi yanıtını görür; diğer personeller göremez. E-posta/kurum mesajlaşması entegrasyonu eklenmemiştir.

## Güncelleme
Yeni ZIP'i ayrı klasöre açın, eski `data/auth_demo.db` ve `data/wfm_demo.db` kopyalarını aktarın. İki uygulama terminalini kapatıp yeni klasörden açın. Eski bekleyen taslaklar yeni hesap/kurallar yüzünden güncelliğini kaybedebilir; bu durumda eski taslağı reddedip yeni kurallarla yeniden oluşturun. Ayrıntılı macOS komutları ILK-OKU.txt içinde.

---

# WFM — 10 Kasım 2026 / 7. güncelleme

## Örnek veri ve kayıtlar
- Demo personeli 264 hesaba genişler; 60 ek dış kaynak, 14 ayrılmış personel, şirket, işe giriş/çıkış ve örnek cinsiyet bilgisi bulunur. Yeni kayıtlar mevcut veriyi silmeden bir defa eklenir.
- Günlük/30 dakikalık sentetik çağrı geçmişi 9 Kasım 2026 dahil biter. AHT, karşılanan çağrı, hedef sürede karşılanan çağrı, personel ve SL verileri eklenir. 1 Ocak–9 Kasım 2026 örnek vardiyaları ayrı geçmiş tablosunda tutulur; takvim ve çalışma süresi hesapları buradan okunur. Kullanıcının yayınladığı vardiyalar korunur. Bilerek geçmişe/farklı geleceğe açılmış tahmin kayıtları silinmez.
- Veri ve Kayıt Merkezi → Açıklanan Vardiyalar içinde geçmiş örnek vardiya tarayıcısı bulunur. Interval ve Kayıt Seçim ekranlarında yüzdelerin çağrı adedi karşılığı gösterilebilir; yuvarlanan adetler günlük toplamı korur.

## Planlama, statüler ve talepler
- Vardiya Kuralları altında Personel Özeti, Mesai Kuralları, Statü Kuralları ve Çalışma Süreleri bulunur. Kurallar iki sütunlu kartlardadır. Günlük maksimum alanı yerine normal vardiya, gerektiğinde akademi üst sınırı, en az vardiya, OFF tercihleri, dinlenme ve ardışık gün sınırları kullanılır.
- 07:00 Full Time kişi kotası düzeltilmiştir; ihtiyaç sıfır olsa da seçili takviye kotasına kadar erken giriş sağlanabilir. Uygun personel yoksa açıklayıcı uyarı oluşur; dinlenme/okul kuralı aşılmaz.
- Yemek süreleri ve mola talep süreleri grup bazlıdır. Yemek penceresi vardiya başlangıcına göre veya sabit saatle seçilir; kapasite açığını en az artıran saat seçilir. Gece vardiyası da kapsanır. Cuma arası tüm personele veya yalnızca örnek cinsiyeti Erkek olan personele uygulanabilir.
- Personel Hesap'ta saat aralığına göre shrinkage oranı girilebilir. Son eşleşen aralık önceliklidir; diğer saatler genel oranı kullanır. Buradaki oran diğer kayıplar içindir: planlı yemek/statüler ayrıca kapasiteden düşülür; aynı kaybı iki kez tanımlamayın.
- Grup ataması dil bazında filtrelenebilir. Başlangıç/bitiş otomatik kurallardan alınabilir veya elle seçilir. Seçili dönem küçük bir bilgi kutusunda görünür; dönem başlangıcı ve bitişi ayrı kartlardadır.
- Belirli miktar fazla kapasiteye izin veren sınır ve en az yeni ek mesai bloğu tanımlanabilir. Açık önerileri aradaki sıfır ihtiyacı geçerek blok oluşturabilir; mevcut vardiyası olanlara da ek mesai önerisi isteğe bağlıdır. Diğer hard kurallar korunur.
- Planlama, liderde bekleyen talebi gerekçeyle üstlenebilir veya gerekçeyle es geçebilir. İzin/gece/OFF benzeri talepler Simüle Et ile taslağa alınır; bu işlem kesin onay sayılmaz. Talep, yayınlanan dönemle karşılanınca kesinleşir; çok dönemli talepler kısmen planlandı olarak izlenir. Planlama gerekçeyle simülasyonu iptal edebilir. Önceden yayınlanan izin değişikliği için yayınlanmış vardiya değişim akışı kullanılmalıdır.
- Ders/sınav sonrası varsayılan ulaşım payı 30 dakikadır. Personel ulaşım sorunu seçerse en az 60 dakika ve belirttiği en erken giriş saati uygulanır. Sınav bitişi bilinmiyorsa gün kapalı kalır. Bayram/yaz öncelikleri korunur.

## Yayın onayları
- Planı oluşturan kişi taslağı onaya gönderir; bu işlem tek başına yayınlamaz. Yayın Onayları ekranında **iki farklı gerçek Planlama hesabı** onay verir. Eksik ihtiyaç **%5 üzerinde** ise ayrıca farklı bir Planlama Yöneticisi onayı gerekir.
- Eksik yüzdesi: sayaca dahil dilimlerde kalan personel-yarım saat toplamı / ihtiyaç personel-yarım saat toplamı. Yemek/statü sonrası açık kullanılır. %5 tam sınırında ek yönetici onayı gerekmez.
- Onaylar aynı taslağa aittir. Talepler, personel revizyonu, kurallar veya ihtiyaç değişirse eski onaylı taslak yayınlanmaz. Hard ihlal yayınlanamaz; soft aşım varsa ayrıca kabul edilir.
- Yayınlanan vardiyalar ve yemekler kayıt merkezine yazılır. Mevcut yayın düzenleme/geri alma, gerekçeli eski/yeni değer kaydı ve vardiya değişim kuralları korunur.

## Canlı izleme, kişisel mola ve simülasyon
- Geçmiş Hafta Analizi ana ekranı **📈 GÜNCEL TAKİP ANALİZİ**, Güncel Takip sekmesi **Canlı İzleme** oldu. Gerçek çağrı/tahmin farklarına ek olarak gerçek SL, AHT, Erlang ihtiyacı ve personel bilgisi varsa model SL gösterilir. Gerçek SL = hedef sürede karşılanan / gelen çağrı. Sonuçlar veri/API güncellendiğinde anlamlıdır; kurum bağlantısı bu pakette kurulmuş değildir.
- Eski İzleme içeriği Takip → İşlem Özeti altında. Yeni İzleme kişisel vardiya, yemek ve kapasiteye göre mola talebi sunar. Talep yalnızca kendi yayınlanmış vardiyası içinde, grup süresiyle ve yeterli boş kapasitede alınabilir. Aynı kapasitenin eşzamanlı iki talebe verilmesi engellenir. İhtiyaç verisi yoksa onay verilmez.
- Similasyon sayfası aylık büyüme/ayrılma senaryosu ve ters Erlang kapasitesiyle personel alım önerisi üretir; aksiyonlar kaydedilir. Bu ortalama kapasite hesabıdır, gerçek çizelge optimizasyonu veya otomatik İK emri değildir. Fatura Mutabakat yalnızca ayrılmış boş sayfadır.
- Vardiya takvimleri modern renkli hücreler, sabit ad/tarih başlığı ve sayfalama kullanır.

## Moderatör ve ayarlar
- Moderatör girişinden sol panelde **Kullanıcı Görünümü · Moderatör** açılır; rol ve gerçek kullanıcı seçilip **Bu Kullanıcı Görünümüne Geç** tıklanır. Müşteri Temsilcisi/Takım Lideri/diğer rollerin gerçek görünümü kullanılır; **Moderatör Hesabına Dön** ile çıkılır.
- Görünüm sadece ekran önizlemesi değildir: hedef hesabın yetkileriyle yapılan işlemler kalıcıdır. Gerçek moderatör aktörü denetim kaydına eklenir. Aynı moderatör farklı hesap görünümleriyle iki bağımsız yayın onayı veremez.
- Ayarlar içinde Planlama'nın Yetkilendirme ekranı ve kullanıcıların Görüş/Talep alanı bulunur. Şikâyette kimlik gizlenebilir; inceleme listesinde isim görünmez, kullanıcı kendi kayıtlarını takip edebilir.
- Yeni demo hesaplar: `planlama2`, `planlama3`, `planlama_yoneticisi`; şifreleri `1234`. Mevcut `moderator / 1234` korunur. Yalnızca sentetik demo modunda üretilirler.

---

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
