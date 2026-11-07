# WFM

Python 3.10+ gerekir. Proje kökünde:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend:app --host 127.0.0.1 --port 8001
```

Ayrı terminalde aynı sanal ortamla:

```bash
streamlit run ui.py
```

Varsayılan API adresi `http://127.0.0.1:8001`; `BACKEND_URL` ile değiştirilebilir.
Mevcut demo giriş bilgileri giriş ekranında listelenir. Otomatik plan oluşturma
WFM, yönetici ve moderatör rolleri içindir.

## Otomatik vardiya planlama

1. Çağrı Tahmini bölümünden tahmin üret, Mesai Planı → Personel Hesap bölümünde
   30 dakikalık personel ihtiyacını hesapla.
2. Vardiya Planı → Plan Dönem Seçimi ekranında dönemi onayla.
3. Mevcut Plan → Mesai Kuralları bölümündeki grup kurallarını ayarla.
4. Oluştur & Kontrol & Yayınla bölümünden personelleri API'den al veya CSV/XLSX
   yükle. Zorunlu sütunlar `employee_id`, `full_name`, `work_type`;
   talep/ders/sınav kayıtları için mevcut hesapla aynı `username` de gerekli.
   Çalışma tipleri: `fulltime`, `akademi`, `dis_kaynak`. Kimlikler benzersiz olmalı.
5. Tüm Vardiyalar → Gece / Yıllık İzin ekranlarında kesin kayıtları gir.
   Talepler bölümünden son kararları ver; WFM/TL kuyruğunda bekleyen talepler
   uygulanmaz. Vardiya Saatleri bölümünden elle atamalar yapılabilir.
6. Oluştur bölümünde grup sırasını kaydet ve varsa ders dönemini seç.
   **Otomatik Vardiya Taslağı Oluştur** düğmesine bas.
7. 30 dakikalık ihtiyaç/atama/eksik/fazla tablosunu ve çakışmaları incele.
   Taslak Vardiya Saatleri ekranına aktarılır. Elle değiştirdikten sonra yeniden
   oluştur; elle kayıtlar korunur, otomatik kayıtlar yeniden hesaplanır.
8. Çakışmasız planı yayınla. Personel açığı varsa ekranda açıkla yayınlama seçimi
   gerekir. Yayınlanan plan Tüm Vardiyalar ve Benim Vardiyam ekranlarına bağlanır.

### Hesaplama davranışı ve sınırlar

- Öncelik: gece/yıllık izin → onaylı talepler → elle atamalar → otomatik doldurma.
  Çakışmada ilk kayıt korunur ve sorun raporlanır. Sabit kayıtlar kurala aykırıysa
  silinmez; sorun çözülene kadar yayınlama engellenir.
- Motor grupları kullanıcı sırasıyla işler. Her aday vardiyada karşılanan açık
  sayısını artırır, eşitlikte fazla personeli azaltır ve gündüz tercihini gözetir.
  Personeller arasında daha az çalışana öncelik verir. Bu yöntem tüm olasılıkları
  çözen bir optimizasyon modeli değildir; en iyi planı garanti etmez.
- Çalışma süresi, haftalık gün, dinlenme, başlangıç/bitiş sınırları ve dolu ders
  saatleri kontrol edilir. Hafta takvim haftasıdır (Pazartesi–Pazar); önceki ve
  sonraki kayıtlar da gün/dinlenme hesabına katılır. Akademi süresi maksimum
  olduğundan 30 dakika ile tanımlı maksimum arasında aday vardiyalar denenir.
- Gece vardiyaları motor tarafından sıfırdan üretilmez, kesin kayıtlardan alınır.
  Dil bazlı gece sayıları ve gece saat aralığı kontrol edilir; eksik/fazla kesin
  kayıt varsa plan kontrolünde gösterilir.
  İhtiyaç tablosu toplam sayı içerdiği için dil/lokasyon bazlı ayrı ihtiyaç
  optimizasyonu yapılmaz.
- Sınavın bitiş saati veride olmadığı için sınav günü tamamen kapatılır.
  Dersler seçilen yıl/döneme göre haftanın ilgili saatlerini kapatır.
- İhtiyaç karşılaştırması shrinkage eklenmiş `Planlanan Agent` sütununadır.
  Mola saatleri ayrıca modellenmemiştir. Otomatik soft kural esnetmesi yapılmaz.
- Yıllık izin, belirli saatli gece/mesai ve bayram talepleri otomatik işlenir.
  Vardiya değişimi ve serbest metin talepleri için henüz otomatik dönüşüm yoktur;
  uygulanamayan onaylı kayıtlar açıkça raporlanır ve yayınlamayı engeller.
- Hazır çalışma alanında talepler, içerik ekleri, işlem geçmişi, okul kayıtları,
  sabit vardiyalar, kurallar, planlar, tahmin seçenekleri ve seçili planlama
  kaynağı `data/wfm_demo.db` içinde kalıcıdır. Personel/giriş bilgileri mevcut
  `data/auth_demo.db` içindedir. Üretim veritabanı bağlantısı ayrı adaptör olarak
  eklenebilir. CSV çıktıları indirilebilir.
- Plan girdisi değiştiğinde eski sonuçla yayınlama engellenir. Oluşturma yalnızca
  seçilen dönem taslağını, yayınlama yalnızca seçilen dönem yayınını değiştirir.

## Doğrulama

```bash
python -m unittest discover -s tests -v
```

`engine.py` veri kaynağından ve Streamlit'ten bağımsızdır.
`planning_data.py` mevcut API/oturum kayıtlarını motor girdilerine dönüştürür;
veritabanı geçişinde bu katman değiştirilebilir.


## Hazır veritabanı ve hesaplarla deneme

Girişten sonra `data/wfm_demo.db` yoksa otomatik oluşturulur. Bu dosya mevcutsa
kullanıcının değişiklikleri korunur; başlangıç verileri her girişte sıfırlanmaz.

- İki yıl (730 gün) sentetik günlük çağrı/AHT geçmişi.
- 35.040 adet 30 dakikalık çağrı/AHT kaydı; slot toplamları günlük toplamla aynıdır.
- Mevcut personel veritabanıyla eşleşen örnek TL/WFM kuyrukları, karar geçmişi,
  ders ve sınav bildirimleri, gece/yıllık izin kayıtları ve geçmiş vardiyalar.
- Gerçek geçmiş üzerinde eğitilen beş modelden RMSE'ye göre seçilmiş dört
  tahmin, hazır interval profili ve bir haftalık başlangıç personel ihtiyacı.

**Demo Veritabanı** menüsünden rol ve hesap seçip **Bu Demo Hesabına Geç** ile
personel → ilgili TL → WFM akışını deneyebilirsiniz. Örnek veri olduğu ekranda
belirtilir. Çağrı CSV'si ve SQLite dosyası aynı sayfadan indirilebilir.
Model karşılaştırması sentetik skorlar göstermez: son tarih dilimi test olarak
ayrılır, tüm modeller aynı test örnekleriyle ölçülür. Eğitilmiş Python nesneleri
veritabanından pickle olarak yüklenmez; yeni oturumda demo modelleri yeniden
eğitilir. Üretilmiş tahmin seçenekleri veritabanında saklanır.

## Talep kayıtları

Personel, TL ve planlama ekranları aynı talep merkezini kullanır. Tek kayıt
numarası, okunur Türkçe başlıklar, gerçek kişi adları, tarih/saat aralığı,
gönderim anındaki ders/sınav/bayram içeriği ve değiştirilemeyen işlem geçmişi
birlikte gösterilir. Serbest açıklama düz metin olarak işlenir.

- Personel kendi adına talep gönderir veya bekleyen talebini geri çeker.
- TL onaylayıp planlamaya iletir ya da gerekçeyle reddeder.
- Vardiya değişiminde ilgili iki TL'nin onayı tamamlanmadan WFM'e geçmez.
- WFM onaylayıp plana alır veya gerekçeyle reddeder. Onay, planın gerçekten
  oluşturulduğu anlamına gelmez; otomatik motor onaylı kayıtları tüketir.
- Güncellenen okul bildirimlerinin eski kopyaları silinmez; yeni kayıtla
  değiştirildiği işaretlenir. Aynı kayda iki eski tarayıcıdan karar verilirse
  ikinci işlem sürüm kontrolüyle reddedilir.

## Dört model ve planlama tahmini

**Çağrı Tahmini → Model Kur** altında modelleri aynı eğitim/test ayrımıyla
karşılaştırın. Sıralama RMSE artan, eşitlikte MAE artandır. **Tahmin** sekmesinde
tek düğmeyle ilk dört modelin aynı tarih aralığındaki tahminlerini üretin.
30 dakikalık modelde her gelecek günün 48 slotu üretilip günlük toplam alınır.

**Mesai Planı → Tahmin Kaynağı** altında modelleri karşılaştırıp seçin veya
her güne ait çağrı sayısını elle düzenleyin. Kaydetmeden planlama kaynağı
değişmez. Eksik tarih, boş/negatif/sonlu olmayan değerler kabul edilmez.
Kaynak değiştiğinde eski personel hesabı ve dönem onayı geçersiz olur;
**Personel Hesap** ekranında yeniden hesaplayın.

**Geçmiş Hafta Analizi** ayrı menüsünde gelecek haftanın günleri için geçen
haftanın aynı günü, son iki haftanın aynı gün ortalaması ve son 30 gün içindeki
aynı hafta günü ortalaması gösterilir. Veri kesiminden sonraki gerçekleşmeler
hesaba katılmaz. Eksik geçmiş sıfıra çevrilmez; örnek sayıları ayrıca gösterilir.
Bu sayfa geçmişe dayalı bir referanstır, eğitilmiş model tahmini değildir.


## Haftalık interval: geçmiş pencereler ve takvim etkileri

Mesai Planı → İnterval, 30 dakikalık SQLite çağrı geçmişini otomatik açar.
CSV/XLSX kaynağı da seçilebilir. Hedef hafta Pazartesi–Pazar olarak seçilir.
Eksik slotlu veya toplamı sıfır günler dağılım hesabından çıkarılır; sıfır çağrı
olarak doldurulmaz. Bir slotta birden fazla kuyruk satırı varsa çağrılar toplanır.

- Aday pencereler: son 14 gün, 1/3/6/12 takvim ayı ve tüm geçmiş.
- Her gün önce kendi toplamına bölünür; yüksek hacimli günler otomatik olarak
  düşük hacimli günleri bastırmaz. Yakınlık ağırlığı:
  `1 / (1 + log(1 + yaş_gün / 7))`.
- Adaylar son tamamlanmış ve yedi günü tam haftada doğrulanır. Bu haftanın
  gerçekleşmeleri kendi tahmininin eğitiminde kullanılmaz.
- Hata, 7 × 48 hücrede ortalama mutlak dağılım farkıdır (yüzde puan).
  Başarı ağırlığı `1 / max(MAE, 0.01)` ile hesaplanıp toplamı %100 yapılır.
  Aynı doğrulama haftası ağırlık kalibrasyonunda da kullanıldığından birleşim
  eğrisi bağımsız bir gelecek başarı garantisi değildir.
- Ekstre kesim, son ödeme, bayram/arife/bayram sonrası, resmi tatil ve Ramazan
  çağrı tahminiyle aynı takvimden alınır. En az iki benzer geçmiş gün varsa
  yakınlık ağırlıklı benzer-gün dağılımı temel hafta günü dağılımına katılır.
  Etki payı `min(0.7, n/(n+4))` olur. Yetersiz benzer gün sayısı ekranda yazılır;
  olmayan etki uydurulmaz. Takvim tanımları mevcut 2020–2030 dönemidir.
- Personel hesabında gerçekten kullanılan haftalık profil tarihleriyle saklanır.
  Sonraki doğrulamada bu profil varsa onun hatasına göre iyileşme gösterilir;
  kayıt yoksa önceki haftanın gerçekleşen dağılımı açıkça referans gösterilir.
- Profil her gün için toplamı %100 olan 48 dilim içerir. Tarihli profil başka
  haftalara sessizce tekrarlanmaz. Personel hesabı seçili profil haftasıyla sınırlıdır.

Başarı tablosu, takvim benzer-gün açıklamaları, ısı haritası ve günlük eğriler
ayrı alt görünümlerdir. Profili kaydedip aktif ettikten sonra personel ihtiyacını
yeniden hesaplayın. Aktif profil değiştiğinde eski ihtiyaç ve dönem onayı geçersiz olur.

## Kullanım ve hız güncellemeleri

Alt ekranlar yalnızca seçildiklerinde çalışır; tüm sekmeler arka planda birlikte
hesaplanmaz. SQLite çağrı okumaları kısa süreli önbelleğe alınır; demo modelleri
veriye göre önbelleğe alınır ve her oturuma bağımsız kopyalanır. İnterval sonuçları
veri/hafta/referans girdisine göre önbelleğe alınır. Veritabanını Yenile düğmesi
önbelleği temizler. İlk açılışın model yükleme/eğitim maliyeti vardır.

Feature Engineering'in tarih, 30 dk etiketleri, banka, günlük lag/rolling ve
intraday lag/rolling gruplarında ayrı Tümünü Seç / Seçimi Temizle düğmeleri vardır.
Seçim, ilgili grubun kutularını anında günceller; diğer grupları bozmaz.

Geçmiş Hafta Analizi → Günlük ve 30 Dakikalık ayrı görünümlerdir. Günlük grafikler
yalnız tarih gösterir; 30 dakikalık grafikler saat ve 7 × 48 ısı haritası kullanır.
Talep detayları açılır seçim kutusu yerine listedeki satıra tıklanarak açılır.

Vardiya Saatleri'nde seçilen personel ve tarihler için taslak silinebilir;
son 20 elle işlem geri alınabilir. Geri alma sadece değişen kayıtları saklar,
başka birinin sonradan değiştirdiği kaydı ezmez. Kesin gece/izin ve onaylı talep
kaynakları bu ekran üzerinden silinmez; kaynak ekranından düzeltilir.

Sınavlar kişinin kullanıcı adı/employee_id eşleşmesi ve Sınav Takvimi'ndeki Tarih
alanıyla bulunur. Bitiş saati bulunmadığından sınav günü tamamen kapatılır.
Gece ve yıllık izinler kesin kayıt, onaylı talep ve mevcut yayınlanmış kayıtlardan
otomatik alınır; oluşturma ekranındaki kontrol alanında sayıları görülebilir.

### Vardiya çalışma alanı güncellemesi
İnterval ekranında önerilen grafik ve 48 saat aralığı × 7 gün ağırlık tablosu birlikte
sunulur. Profil yönetimi işaretli satırlardan yapılır; alt profil görselleri korunur.
Personel listesi **Personel Takip → Personel Listesi** altındadır. Mevcut Plan özetinde
şehir merkezlerine göre şematik harita, dil ve çalışma biçimi halka grafikleri bulunur.

**Vardiya Saatleri** seçili plan dönemini kullanır. Onaylı talepler, gece kayıtları,
yıllık/evlilik/mazeret/doğum/ücretsiz izin ve raporlar takvimde görülür; elle girişler
silinebilir veya geri alınabilir. İhtiyaç karşılama özeti ve tarih/dilim bazlı eksikler
hem bu ekranda hem oluşturma sonucunda gösterilir.

Otomatik planlama dolu yarım saate ilave personel yerleştirmez. Bu nedenle sabit
vardiya süreleri ve uygunluklar bazı açıkların kapanmasını engelleyebilir; açıklar
gizlenmez. Kesin ve elle atanan kayıtlar korunur, bunların fazlası ayrıca raporlanır.
Sınav günleri tamamen kapatılır; diğer günlerde tarihine uygun ders dönemi kullanılır
(Ocak önceki Güz, Şubat–Ağustos Bahar, Eylül–Aralık Güz). Dış kaynak süresi 10 saattir;
eski kayıtlı 11 saat değeri açılışta diğer kurallar korunarak güncellenir.

### Çalışma süreleri ve yayın kontrolü
Mesai Kuralları değişiklikleri **Kaydet ve Uygula** ile yürürlüğe girer. Seçili dönemin
kesin/elle gece kayıtları isteğe göre yeni gece aralığına uyarlanır; dönem dışındaki
kayıtlar ve onaylı taleplerin açık saatleri korunur. Gece vardiyasının süre üst sınırı
tanımlanan gece aralığıdır; Akademi'nin gündüz süre sınırı ayrıca uygulanır.
Bütün personeller için en az 11 saat dinlenme kontrol edilir.

İngilizce ve Arapça personeller bağımsız anahtarlarla planlamaya dahil edilir;
hariç tutulanların atamaları ihtiyaç karşılama hesabına eklenmez ve önceki yayınları
silinmez. İhtiyaç toplam havuzdur; dil bazında ayrı çağrı talebi bu ekranda üretilmez.
Grup önceliği düğmelere tıklama sırasıyla kurulur. Gece sayısı uyarıları açık onayla
kabul edilebilir; kayıt çakışmaları, dinlenme ve süre ihlalleri yayınlamayı engeller.
Düğmenin yanında engelin nedeni ve yapılacak işlem gösterilir.

**Mevcut Plan → Çalışma Süreleri** her grubun her kişisi için aylık/özel dönem saat
üst sınırı tanımlar. Motor bu sınırı kalan ihtiyaçla birlikte gözetir, hedefi doldurmak
için ihtiyaç fazlası üretmez. Aynı grup için çakışan hedef aralıklarına izin verilmez.
Dönem çalışma saatleri takvim sınırlarına göre hesaplanır; gece vardiyasının ilgili
güne düşen saatleri sayılır. Dönem ortalaması kişi başı toplam saat, günlük ortalama
ise seçili dönemin bütün takvim günleri üzerinden hesaplanır.
