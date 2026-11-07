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
  Kurallardaki dil bazlı gece sayıları henüz ayrı bir kota kontrolüne bağlı değil.
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
