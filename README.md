# WFM

**Faz 3 / 9. güncelleme:** yönetim ajandası ve onay merkezi, koçluk ataması, yemek/mola değişimi, statü geçmişi ve shrinkage önerisi, dil bazlı planlama ve senaryo analizi. Güncel davranış ve kurallar için [GUNCELLEME_NOTLARI.md](GUNCELLEME_NOTLARI.md).

Güncel kurulum: [ILK-OKU.txt](ILK-OKU.txt). Türkçe kaynaklar: [DOSYA_HARITASI.md](DOSYA_HARITASI.md). Kurum API/veritabanı hazırlığı ve sınırları: [KURUMSAL_BAGLANTI.md](KURUMSAL_BAGLANTI.md). Eski İngilizce Python dosyaları geriye uyumluluk yönlendirmeleridir.

Python 3.10+ gerekir. Proje kökünde:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn sunucu:app --host 127.0.0.1 --port 8001
```

Ayrı terminalde aynı sanal ortamla:

```bash
streamlit run arayuz.py
```

Varsayılan API adresi `http://127.0.0.1:8001`; `BACKEND_URL` ile değiştirilebilir.
Mevcut demo giriş bilgileri giriş ekranında listelenir. Otomatik plan oluşturma
Planlama, Yönetici ve Müdür rolleri içindir.

## Otomatik vardiya planlama

1. Çağrı Tahmini bölümünden tahmin üret, Mesai Planı → Personel Hesap bölümünde
   30 dakikalık personel ihtiyacını hesapla.
2. Vardiya Planı → Plan Dönem Seçimi ekranında dönemi onayla.
3. Vardiya Kuralları → Mesai Kuralları bölümündeki grup kurallarını ayarla.
4. Personeller yerel personel deposundan veya yapılandırılmış kurum personel adaptöründen alınır. Sicil, kullanıcı adı ve sabit iç kimlik eşleşmesi gereklidir. Çalışma tipleri `fulltime`, `akademi`, `dis_kaynak`.
5. Tüm Vardiyalar → Gece / Yıllık İzin ekranlarında kesin kayıtları gir.
   Talepler bölümünden son kararları ver; WFM/TL kuyruğunda bekleyen talepler
   uygulanmaz. Vardiya Saatleri bölümünden elle atamalar yapılabilir.
6. Oluştur bölümünde grup sırasını belirle. Ders dönemi tarihe göre seçilir; varsa sınav takvimi uygulanır. Bayram önceliği ve yaz ayları Mesai Kuralları üzerinden belirlenir.
   **Otomatik Vardiya Taslağı Oluştur** düğmesine bas.
7. 30 dakikalık ihtiyaç/atama/eksik/fazla tablosunu ve çakışmaları incele.
   Taslak Vardiya Saatleri ekranına aktarılır. Elle değiştirdikten sonra yeniden
   oluştur; elle kayıtlar korunur, otomatik kayıtlar yeniden hesaplanır.
8. Çakışmasız planı Yayın Onayları ekranına gönder; iki farklı Planlama hesabı onaylar. Açık %5 üzerinde ise ayrıca Planlama Yöneticisi onaylar. Personel açığı varsa ekranda açıkla yayınlama seçimi
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

### Interval temizliği, elle giriş ve etkin ihtiyaç saatleri
İsteğe bağlı IQR aynı haftanın günü/yarım saat grubundaki dağılım paylarını eğitim
verisinde sınırlar veya aykırı günleri tamamen çıkarır. Doğrulama haftasının gerçekleri
korunur; eğitim temizliği bu gerçeklerden öğrenmez. Profilde IQR ayarı ve etkisi saklanır.
Günlük hareketli ortalamalar 7/30 takvim günü içinde hafta içi ve hafta sonu için ayrıdır.

Elle giriş hem personel hem grup seçimini destekler. Mevcut gerçek kayıtlar ve açık
izin günleri korunur; otomatik boş OFF yer tutucuları doldurulabilir. Süre, dinlenme,
okul, haftalık/üst üste gün ve dönem saati kontrollerinden geçmeyen günler kaydedilmez.
Üst üste çalışma sınırı ISO hafta sınırından bağımsızdır ve komşu geçmiş/fiks kayıtları kapsar.

03:00–08:00 hariç tutma seçeneği ihtiyaç özetini, eksik/fazla matrisini ve otomatik
atamanın hedefini etkiler. Hariç dilimler tabloda gri çizgiyle gösterilir; veri yokluğu
sıfır açık olarak gösterilmez. 07:00 girişli vardiyalar halen oluşturulabilir. Çalışma
bütçeleri ve 11 saat dinlenme gerçek vardiya sürelerinden hesaplanır.

Eksikleri kabul ederek yayınlama artık ayrı bir checkbox gerektirmez: düğme doğrudan
veritabanına yazar ve gerçek yayınlanan vardiya takvimini gösterir. Genel talepler
vardiya ataması değildir ve yayın engeli oluşturmaz; gerçek kural ihlalleri engeldir.
Çalışma saatleri geçmişi plan döneminden bağımsız seçilir ve yalnızca yayınlanmış kayıtları kullanır.

### Sürümlü tahmin, gerçekleşen beslemesi ve güncel takip
`core/forecast_ledger.py` kullanılan tahminleri 30 dakikalık satırlar olarak SQLite'ta
saklar. Her kayıtta oluşturma zamanı, model ve profil bilgisi bulunur. Günlük tahmin,
48 satırın toplamından hesaplanabilir. Aynı içerik yeniden kullanıldığında aynı sürüm
korunur; farklı tahmin yeni sürüm olur. Kayıtlar 12 haftadan sonra silinmez.
Dağılım seçimi de ayrıca `profile_versions` içinde tarihli ve değişmez saklanır.
Önceki çalışma alanındaki kayıtlar ilk açılışta taşınır; ilk seçim zamanı bilinmiyorsa
bu bilgi açıkça işaretlenir. Eski gerçekleşmelerden yeni bir geçmiş tahmin uydurulmaz.

**Geçmiş Hafta Analizi → Güncel Takip** ilk alt ekrandır. Görünürken 30 saniyede bir
veritabanını okuyarak 48 dilimde tahmin/gerçekleşen çağrı ve farkı gösterir. Veri gelmeyen
dilim 0 sayılmaz. Fark yüzdesi `(gerçekleşen - tahmin) / tahmin × 100` şeklindedir;
tahmin 0 ise yüzde tanımsızdır. WAPE toplam mutlak hatanın gerçekleşen çağrı toplamına
oranıdır. İsteğe bağlı 03:00–08:00 hariç tutma ölçümü etkiler, saklanan veriyi değiştirmez.
Dağılım başarısında tamamlanmış günler kullanılır; ölçülen saatler içinde hem tahmin
payları hem gerçekleşen paylar %100'e normalize edilir.

İnterval hücreleri elle değiştirilebilir. Değişen hücreler sabitlenir. Artış önce
03:00–08:00'ın serbest paylarından, yetmezse diğer serbest hücrelerden orantılı düşülür.
Azalışın boşalttığı pay öncelikle 03:00–08:00'a eklenir. Sabitlenen paylar %100'ü aşarsa
veya dengeleme mümkün değilse işlem reddedilir; başka günlerin payları değiştirilmez.
Kaydetmeden önce gün toplamı ve dengelenecek fark görülebilir.

Kimlik doğrulamalı servisler (WFM/yönetici/moderatör):
- `GET /forecast-ledger/runs`: kayıtlı tahmin sürümleri.
- `GET /forecast-ledger/runs/{run_id}/slots`: değişmez 30 dakikalık tahmin satırları.
- `POST /actuals/intervals`: gerçekleşen çağrı beslemesi.

POST gövdesi örneği:
```json
{"rows":[{"tarih":"2026-11-02","slot":17,"cagri_sayisi":125,"aht_sec":300}]}
```
`tarih` yerel gün, `slot` 1–48 aralığında yarım saat numarasıdır (17 = 08:00–08:30).
Slot verilmezse tarih/saat alanından çıkarılır. Zaman dilimli zaman damgaları İstanbul'a
çevrilir. `aht_sec` isteğe bağlıdır. Kısmi gün kabul edilir. Aynı tarih/dilim yeniden
beslenirse o dilimin gerçekleşeni güncellenir, diğer dilimler korunur. Dosyada yinelenen
aynı tarih/dilim reddedilir. Çağrılar negatif olmayan tam sayı olmalıdır.
İsteklerde `/auth/login` ile alınan token `Authorization: Bearer ...` başlığına konur.

### Yayın kilidi, talepler ve yayın yönetimi
Yayınlanmış tarih/dil kapsamı ikinci planı kabul etmez. Türkçe/İngilizce/Arapça seçimi
ayrı yapılabilir; farklı dillerin yayınları birbirinin yerine yazılmaz. `publication_batches`
her yayının satırlarını arşivler. Yayınlama ve geri alma SQLite işlemi içinde güncellenir;
başka oturumun değiştirdiği yayın üzerine yazılamaz. **Yayın Yönetimi** yayınlanmış
bir tabloyu geri alabilir veya düzenlenebilir taslağa taşıyabilir. İşlem yalnızca seçilen
yayının personel/dil/tarih anahtarlarını etkiler. Başka dilin vardiyaları korunur.

Seçili dönemin açık talepleri TL veya WFM aşamasında olsa da atama ve oluşturmayı
durdurur. İlgili tarih/dil/personel kapsamı ve dönemlik ders bildirimleri dikkate alınır.
Talep onayından sonra izin/gece/mesai kayıtları kaynaktan doğrudan içe alınır ve eski
alt öncelikli elle girişlerin yerini alır. Kesin kaynaklar arasındaki gerçek çakışma
saklanmaz; açıkça düzeltilmesi gerekir. Genel talepler vardiya oluşturmaz. Vardiya
değişiminde iki liderin onayı sonrası WFM onayında iki tarafın saatleri sabitlenir;
daha sonraki taslak değişikliği onaylanmış değişimin anlamını değiştirmez. Eski ve
iki taraflı saat kaydı bulunmayan değişimler otomatik uydurulmaz, yeniden değerlendirilir.

Sınav saatine göre çalışma seçeneği kapalıyken sınav günü bütünüyle kapalıdır. Açılırsa
başlangıç/bitişi bilinen sınavın saatleri dışında ihtiyaç, süre ve dinlenme uygunsa atama
yapılır. Eksik veya hatalı saat bilgisi bütün günü kapalı tutar. Gece kuralları kaydedildikten
sonra eksik tarih/dil sayıları popup ile bildirilir. Dolu/uyuşmayan taslak kayıtları açık
seçimle silinebilir; kesin ve onaylı kaynaklar kendi kaynak ekranlarından değiştirilir.

### Ortak takvim ve takip görünümü
Kesim/son ödeme hesapları `core/billing_calendar.py` üzerinden FE ve tahminde aynıdır.
Mevcut proje kuralı: kesimler ayın 9/16/24/31'i; 31 olmayan ayın ek kesimi sonraki ayın
1'idir. Son ödeme kesim +9 gündür; hafta sonuna gelirse pazartesiye taşınır. Resmi tatil
için ek erteleme bu kurala dahil değildir. Önceden kısa ayın sonraki ayına ait 1. gün,
yanlışlıkla aynı ayın 1. günü olarak hesaplanabiliyordu; bu ve FE/tahmin uyumsuzluğu giderildi.

Hareketli ortalamalar her hafta günü için son 7/30 aynı gün gözlemini kullanır (son
7 Pazartesi vb.). İki grafik hafta içi/hafta sonu sunumudur; hesaplar ayrı yedi gündür.
Takım lideri okul kayıtlarında yalnızca kendi ekibini, WFM/yönetici bütün personelleri,
personel kendi bilgilerini görür. Takip ekranı yalnızca yayınlanmış vardiyalardan saatleri
hesaplar: Sabah 08–13, İkindi 13–17, Akşam 17–00, Gece 00–08. Gece adedi GECE kodlu,
00–07 içinde başlayan veya gece yarısını gerçekten aşarak 00–08 içinde çalışan vardiyaları
sayar; 07 girişleri veya tam 00'da biten akşam vardiyası gece adedi değildir. Süreler seçili
tarih aralığına kırpılır; izin ve raporlar ayrı statülerdir. Akademi ücret örneğinin 11–00
yoğun saat hesabı korunur. Statü ve başlangıç/bitiş saatleri ortak renk kurallarını kullanır.
