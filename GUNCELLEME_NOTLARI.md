# WFM — Faz 4 / 11 Kasım 2026 / 10. güncelleme

## Geçmiş veri ve personel hesabı
- Demo modunda en az altı aylık, hafta hafta günlük/30 dakikalık tahmin ve oran arşivi eklenir. Tahminler hedef haftadan önceki aynı gün kayıtlarından üretilen sentetik karşılaştırma örnekleridir; geçmişte yapılmış gerçek tahmin gibi tarihlenmez. Gerçekleşen çağrı/AHT/SL örnekleri ve personel vardiya geçmişi korunur.
- Sentetik statü geçmişi güncellendi: hafta sonu yemek/mola süreleri daha düşük; yemek, mola ve koçluk kayıtları mevcut. Yalnızca source=synthetic satırları yenilenir; kurumdan alınan actual kayıtları korunur. Kurumsal modda bu üretimler çalışmaz.
- Kayıp önerisi her hafta günü ve her yarım saat için ayrı hesaplanır: birleştirilmiş statü süresi / vardiya süresi. Çakışan statüler çift sayılmaz. Çalışma yoksa oran üretilmez ve mevcut varsayılan korunur. Sonuçlar iki ondalık gösterilir; gün grafiği ve açık sütun adları eklendi. Aktarılan gün filtresi elle düzenleme/kaydetmede korunur. %95 üzerindeki öneriler uygulanırken %95'e sınırlanır.
- Interval artık doğrudan veritabanından beslenir. Profil listesi aktif profil vurgusu, kart içi aktif yapma ve çoklu silme seçimi sunar.

## Vardiya ve kapasite
- Ayrı Çalışma Süreleri alt ekranı kaldırıldı. Personel Özeti içindeki süre tanımlama alanı korunur; sağda seçilen tarihlere ait çalışma ve hedef dönemi kalan süre kartları, altında grup grafiği bulunur. Kalan süre hedef dönemine aittir ve tarihleri ayrıca gösterilir.
- Grup sırası açık, numaralı seçim düğmeleriyle yönetilir. Otomatik Taslağı Sıfırla yalnızca seçili dönem/personellerde otomatik taslak atamalarını siler; elle/kesin kayıtları, yayın ve onay geçmişini silmez.
- Gece Kuralları'na 8 saatlik GECE vardiyası toplam mola süresi eklendi (varsayılan 60 dakika). İlk/son saat ve saatlik mola sınırları korunur. Sayaca dahil olmayan dilimler mola kapasite maliyetini engellemez. Tek mola en fazla 15 dakika; uygunluğa göre 10/5 dakikalık parçalar da denenir.
- Eksik tablosunda kırmızı eksik kişi, koyulaşan yeşil + ise fazla kişi gösterilir. Öneriler kısa dolu aralıkları birleştirebilir: Kapasite ve Ek Mesai içindeki varsayılan 1 yarım saatlik köprü; fazla personel, dinlenme, okul, grup/dönem süre sınırları korunur. Elle blok seçimi gerçek saat aralıklarını gösterir.
- Statülerin shrinkage bütçesine sığıp sığmadığı ek kartlarla gösterilir. Yalnızca bütçeyi aşan statü kaybı ayrıca kapasiteden düşülür.
- Yayın Yönetimi'nde takvimin hücreleri doğrudan düzenlenir. Değerler 08:00–17:00, Gece 00:00–08:00 veya OFF/izin adı olabilir. Gerekçe ve Kaydet ile kural kontrolü, denetim, statü yeniden planlama ve bildirim aynı işlemde çalışır. Düzenleme Planlama içindir; diğer takvimler salt okunurdur.

## Koçluk ve haftalık ajanda
- Otomatik planda aylık hedef ve kapasiteye göre kişiye uygun koçluk alanları ayrılır. Bunlar henüz kesin görüşme değildir. Koçluk alanları kapasite kaybına dahildir ve yayın onayı snapshot'ıyla birlikte yayınlanır; lider atayana kadar personelin planlı statülerine eklenmez.
- Ajandada lider 7 günlük çalışma saatlerini tek seferde kaydeder. Personeli seçince yayınlanmış koçluk alanları ile kendi çalışma aralığının kesişimi tarih/saat kartlarında görünür. Seçilen alana atama tek işlemde yapılır; aynı alan ikinci kez kullanılamaz. Başka görüşme, hat kapasitesi, ekip yetkisi ve aylık hedef son anda tekrar kontrol edilir.
- Haftayı değiştirmek atanmış görüşmeleri çalışma dışında bırakamaz. Alt bölümde haftalık vardiya biçiminde kendi çalışma/görüşme takvimi vardır. Yayın geri alınırsa ayrılmış alanlar da kaldırılır; hücre değişiminde ilgili kişinin alanları yeniden değerlendirilir.

## İzleme, takip ve görünüm
- Giriş bildirimi ekran ortasında ve sınırlı yükseklikte açılır; küçük ekranlarda içerik kaydırılır.
- İzleme bugün/vardiya/statü saatlerini ortak başlıkta ayırır. Mola kapasite grafiği kaldırıldı; kişi üst sınırdan daha kısa mola isteyebilir.
- İzleme → Personel Bilgileri: tarih bazlı çalışma, OFF ve planlı statü/koçluk özeti. Müşteri Temsilcisi kendisini, lider kendi ekibini görür. Performans skoru üretilmez; ileride gerçek skor kaynağı bağlanabilir.
- Takip bölümünde ayırıcı çizgiler ve planlı statülerin renkli satır listesi eklendi. Statü analizi gün bazında toplam saat grafiği, açık kişi-eşdeğeri açıklaması ve renkli kullanım özeti kartları sunar. Analiz tablolarında ondalıklar iki basamak gösterilir.

## Kullanım
Eski süreçleri durdurup ZIP'i yeni klasöre çıkarın. Kendi verilerinizi korumak için eski data/auth_demo.db ve data/wfm_demo.db dosyalarının kopyalarını yeni klasöre alın; ilk açılışta yeni tablolar eklenir. Ayrıntılı macOS komutları ILK-OKU.txt içinde.
Kurum API/statü/kimlik entegrasyonu henüz canlı değildir; bu sürümdeki geçmişler örnektir. Vardiya motorunun kural tabanlı yöntemi ve çağrı tahmini modelleri değiştirilmedi.

---

# WFM — Faz 3 / 11 Kasım 2026 / 9. güncelleme

## Yetki, bildirim ve yönetim
- Moderatör kullanıcı geçişinde hedef hesabın gerçek rol/yetkileri ve ekip kapsamı kullanılır; Müşteri Temsilcisi, Takım Lideri, Planlama ve Yönetici Yardımcısı geçişleri API düzeyinde kontrol edildi. İşlemler gerçek kayda yazılır; asıl moderatör aktörü denetimde korunur. Aynı gerçek kişinin farklı hesap görünümleri iki bağımsız yayın onayı sayılmaz.
- Her girişte/switch işleminde o kullanıcıya ait okunmamış bildirimler renkli karşılama penceresinde gösterilir. Okundu bilgisi kullanıcıya özeldir; bildirim kutusuna geçilebilir.
- Yeni 📥 Onay Merkezi: Plan Yayın Onayları, Personel İşlemleri, Personel Talepleri, Statü Değişimleri. Yetkili rol kendi kararlarını verir. Yönetici, Yönetici Yardımcısı ve Takım Lideri için 📆 Ajanda eklendi.
- `assistant_manager` = Yönetici Yardımcısı rolü eklendi. Demo hesabı `yonetici_yardimcisi / 1234`; kurumsal modda bu hesap üretilmez. Müdür/Planlama rollerinin eski iş akışları korunur.
- Ajandaya kişi kendi çalışma aralıklarını girer. Koçluk için liderin çalışma aralığı, personelin yayınlanmış vardiyası, başka görüşmeler/statüler, hat kapasitesi ve aylık koçluk hedefi birlikte kontrol edilir. Takım lideri kendi ekibine; üst roller yetkili oldukları kapsama atama yapar. Görüşme personelin takvimine ve bildirimine düşer.

## Statü planlama, geçmiş veri ve değişimler
- Vardiyanın ilk/son saatinde mola verilmez. Her grubun başlangıç/bitimden kaç dakika korunacağı Statü Kuralları → Mola altında değiştirilebilir (varsayılan 60/60). Otomatik mola, kişisel mola talebi ve mola değişimi bu kuralları kullanır; saatlik kullanım sınırı da korunur.
- Yemek otomatik yerleştirilir. Yemek hakkı Yok ise yemek süresi ve minimum çalışma koşulu sıfırlanır. Farklı yemek süresi uygulanacak hafta günleri ve süreleri seçilebilir; Cuma veya başka bir gün uzatılabilir.
- Cuma 12–14 aralığını kapsayan vardiyalarda kadınlara öncelik verilebilir. Ayrıca bilinen Erkek personel için kesin engel isteğe bağlıdır. Tercih varsayılan açık, kesin engel kapalıdır; bilinmeyen cinsiyet tahmin edilmez. Kurumsal kayıtta cinsiyet Kadın/Erkek olarak eşleştirilmelidir.
- Koçluk varsayılan olarak takım liderinin ajandasından atanır. İstenirse Statü Kuralları'ndan eski otomatik parçalama seçeneği kullanılabilir. Aylık varsayılan kişi başı 60 dakika ve önceki yayınlarda kullanılan süreler korunur.
- Yemek/mola değişimi aynı gün, ekip, çalışma grubu, dil ve eş süreyle yapılır. Önce karşı personel, ardından ilgili takım lideri veya Planlama onaylar. Son karar sırasında güncel vardiya ve statüler tekrar kontrol edilir; çakışma/ilk-son saat/saatlik mola sınırı ihlali kabul edilmez. Onay öncesinde saatler değişmez.
- Sentetik modda 1 Ocak–9 Kasım 2026 vardiya geçmişinden yaklaşık 116 bin yemek/mola/koçluk gerçekleşmesi üretilir. Bunlar gerçek kullanım değildir; source=synthetic etiketi taşır. Yeni örnekler bir defa eklenir, mevcut kullanıcı yayınları ezilmez. Gerçek kullanım ayrı status_actuals tablosuna API ile beslenebilir.
- Personel Hesap'ta geçmiş kullanım aralığı seçilip yarım saatlik shrinkage önerisi alınabilir; dilim kurallarına aktarılıp elle değiştirilebilir. Öneri kayıtlı statü süresi / kayıtlı çalışma süresidir. Çakışan statüler iki kez sayılmaz; kayıtlı olmayan kayıplar bu orana dahil değildir. Eksik kurum kayıtlarıyla tam kayıp tahmini olduğu varsayılmamalıdır.
- Dilim tablosundaki oran açıkça Shrinkage (%) olarak adlandırıldı; hesapta bu oran kullanılır. Toplam shrinkage içinde planlı statüyü ikinci kez düşmeme kuralı korunur.

## Mesai planı ve canlı/geçmiş analiz
- Interval özel gün etkileri çağrı tahmininin aynı ekstre/son ödeme/bayram/arife/resmi tatil/Ramazan takvimini kullanır. Hedef tarihten sonraki gerçekleşmeler eğitime girmez. Aynı özel dönemin yeterli benzer günü varsa dağılım şekline etki eder; yetersizse temel dağılım korunur. Bu ortak takvim test edildi.
- Öneri gerekçeleri geçmiş pencerelerin katkısı ve anlaşılır pay-fark kartlarıyla gösterilir. “Gerçek %4, öneri %5 → 1 puan fark” açıklaması eklendi; özel günler vurgulu kartlardır.
- Çağrı adedi görünümü tek matristir: ilk satır günlük toplam, altında 48 yarım saat. Gün toplamları ayrı küçük düzenleme alanından değiştirilebilir; ikinci veri tablosu yoktur. Kayıt Seçim de aynı görünümü kullanır; aktif profiller renklendirildi.
- Servis seviyesi izleme tablosu/grafiği/kartında Tahmini SL gösterilir. Yeni kullanılan tahmin sürümleri Erlang parametrelerini arşivler. Tahmini SL, gerçekleşen AHT'den veya sonradan değişen ayarlardan yeniden türetilmez. Eski sürümde özgün parametre yoksa tahmini SL boş ve açıklamalı gösterilir; uydurulmaz.
- İzleme seçimleri daha kısa, yan yana yerleştirildi. Yeni Statü Dağılımları ekranında Canlı/Geçmiş ve Planlanan/Gerçekleşen ayrımı vardır. Yarım saat dağılımı, kullanım adedi × ortalama süre ve toplam kişi-saat kartları gösterilir. Sentetik gerçekleşme açıkça etiketlenir. Geçmiş kapsamda ayrılmış personeller de yetki kapsamıyla okunabilir.

## Vardiya planı, yayın ve öneriler
- Personel Özeti'ndeki çalışma alanı iki parçadır: solda saat hedefi tanımı, sağda seçili aralık çalışma grafiği ve hedef dönemi için kullanılan/kalan kapasite. Saat hedefleri otomatik motorun kişi başına üst sınırı olmaya devam eder.
- Taleplerin listesi, filtreleri ve içerik kartları sadeleştirildi; istenen açıklama kaldırıldı. Grup sırası kuralları renkli kartlar, ihtiyaç halkaları daha açık başlıklar kullanır.
- Yayındaki tarih/dil için yeni ihtiyaç hesaplama veya dönem onayı denenirse popup gösterilir. Vardiya atama motorunun mevcut yayın kilidi de korunur.
- Yabancı Dil Planı alanında İngilizce/Arapça ayrı ihtiyaç matrisi kaydedilip planlanabilir. Dilin ihtiyacı ortak veriyi ezmez; diğer dilin yayını korunur. Ortak havuzdan ilk alınan ihtiyaçların kullanıcı tarafından bu dile göre düzeltilip kaydedilmesi gerekir; dil bazlı çağrı tahmini kendiliğinden üretilmez.
- Yayın Yönetimi'nde Planlama günlük/personel filtreli hücrelerden saat/statü düzenleyebilir. Gerekçe zorunludur; okul, dinlenme, grup üst süresi ve ardışık gün kuralları kontrol edilir. Planlama düzeltmesi, çalışanların karşılıklı vardiya değişiminden ayrı yetkili işlemdir; haftalık OFF/saat korunumu olağan karşılıklı değişim akışında devam eder.
- Doğrudan düzeltmede etkilenen yemek/molalar aynı işlemde yeniden planlanır. Sığan koçluk korunur; yeni vardiyaya sığmayan görüşme kaldırılır. Eski/yeni vardiya ve statüler denetim kayıtlarına yazılır, personele bildirim düşer. Rapor girişi için Takım Lideri kuralı korunur. Geçmiş yayını komple geri alma yasağı devam eder.
- Yayın Onayları/Onay Merkezi kişi-roster tablosu yerine doluluk, eksik/fazla 7×48, statü dağılımı ve onaylayan kartlarını gösterir. Çok haftalı dönemde incelenecek hafta seçilir. Kaynakları değişen taslağa yeni onay kaydedilmeden önce güncellik kontrol edilir; reddedip yeniden üretmek gerekir. Son gerekli onay yayını otomatik yapar.
- Öneriler Bloklar/Yarım saatler seçimi ve personel kartlarıyla gösterilir. Simülasyondaki izin talebi gerekçeyle iptal edilip mesai uygunluğu yeniden değerlendirilebilir. İptal otomatik mesai garantisi değildir; yeni öneriler yine çalışma kurallarına uyar.

## Kişisel İzleme ve Takip
- İzleme iç başlığı kaldırıldı; yalnızca bugünkü yayınlanmış vardiya ve planlı statüler gösterilir. Yemek/mola değişim istekleri ve karşı personel onayı buradadır.
- Takip iç başlığı, İşlem Özeti sekmesi, Akademi ücret hesabı ve saat dağılımının gereksiz başlığı kaldırıldı. Dönem seçimi ayrı kutuda; çok aylı vardiyalar ay ay alt alta takvimlerdir. Yemek/mola/koçluk saatleri kartlara dönüştü.
- Öğrenci ders programı shift görünümünde sunulur; düzenleme tablosu kapalı bir giriş alanında korunur. Ulaşım/yurt iki küçük seçim ve saat sayacıyla tanımlanır. İkisi birlikte seçilirse **uzun olan gecikme** uygulanır (kullanıcının seçimi); süreler toplanmaz. Sorun yoksa son ders/sınav bitiminden 30 dakika sonra uygunluk başlar.
- Vardiya değişimi, ek mesai, erken çıkış ve geç giriş talepleri Takip → Talep İlet listesinden çıkarıldı. Tüm Vardiyalar → Değişim Alanı ve Ek Mesai Talebi üzerinden iletilir.

## Similasyon
- Çağrı tahmini, personel sayısı, AHT, hedef SL/cevap süresi ve toplam shrinkage ile 12 aya kadar (isteğe bağlı 24) iyi/normal/kötü senaryolar karşılaştırılır. “Diğer kayıp” ifadesi kaldırıldı.
- Senaryo başlangıcından önceki son 12 aylık gün/mevsim örüntüsü ve geçmişe dönük aynı gün hata ölçümü kullanılır. İyi/kötü farkı bu hatadan türetilir; istatistiksel güven aralığı değildir. Ayrılma ve kullanıcı büyüme varsayımları uygulanır. Gerekli personel, alım önerisi ve simüle SL grafikleri gösterilir.
- 08–24 ortalama hizmet penceresi varsayımı vardır; sonuç gerçek vardiya optimizasyonu veya otomatik işe alım emri değildir. Kayıtlı tahmin olmayan günler geçmişten tamamlanır.

## Güncelleme ve bağlantı
Yeni ZIP'i ayrı klasöre çıkarın. Eski data/auth_demo.db ve data/wfm_demo.db dosyalarının kopyalarını aktarın; iki terminali kapatıp yeni klasörden çalıştırın. Şema/örnek veri bir defa güncellenir. Eski bekleyen taslaklar yeni kurallarla yeniden oluşturulmalıdır. Kurum statü/giriş/telefon bağlantısı bu pakette yapılmış değildir; API ve alanlar KURUMSAL_BAGLANTI.md içinde.

---

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
