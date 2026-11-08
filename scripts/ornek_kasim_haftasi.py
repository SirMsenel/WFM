#!/usr/bin/env python3
"""9–15 Kasım 2026 için sentetik çağrı verisini mevcut WFM demo veritabanına ekler.

Proje ana klasöründe: python3 ornek_kasim_haftasi.py
Özel dosya: python3 ornek_kasim_haftasi.py --db /tam/yol/wfm_demo.db
Yalnızca Python standart kütüphanesi gerekir. Mevcut 30 dk hücreleri korunur.
"""
import argparse
import math
import os
from pathlib import Path
import random
import sqlite3
from datetime import date, datetime, timedelta

START = date(2026, 11, 9)
TOTALS = [17640, 15320, 14880, 14620, 15840, 10280, 7940]


def distribute(total, slots):
    weights = [.025 + math.exp(-(((s-1)/2-11)/3.5)**2)
               + .82*math.exp(-(((s-1)/2-17)/3.7)**2) for s in slots]
    expected = [total*w/sum(weights) for w in weights]
    counts = [math.floor(n) for n in expected]
    order = sorted(range(len(slots)), key=lambda i: expected[i]-counts[i], reverse=True)
    for i in order[:total-sum(counts)]:counts[i] += 1
    return counts


def add_week(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():raise ValueError(f'Veritabanı bulunamadı: {path}. Komutu WFM proje klasöründe çalıştır.')
    db = sqlite3.connect(str(path), timeout=20)
    try:
        marker = db.execute("SELECT value FROM metadata WHERE key='synthetic'").fetchone()
        if not marker or marker[0] != 'true':raise ValueError('Bu dosya yalnızca mevcut sentetik WFM demo veritabanında çalışır.')
        backup = path.with_name(path.name+'-yedek-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        with sqlite3.connect(str(backup)) as copy:db.backup(copy)
        added = 0
        summaries = []
        db.execute('BEGIN IMMEDIATE')
        for offset, default_total in enumerate(TOTALS):
            day = str(START+timedelta(days=offset))
            existing = {int(r[0]):(r[1],r[2]) for r in db.execute('SELECT slot,cagri_sayisi,aht_sec FROM calls_interval WHERE tarih=?',(day,))}
            if any(not 1 <= s <= 48 or not math.isfinite(n) or n < 0 or int(n) != n or not math.isfinite(aht) or aht <= 0 for s,(n,aht) in existing.items()):raise ValueError(f'{day}: mevcut yarım saat verisi geçersiz; işlem geri alındı.')
            missing = [s for s in range(1,49) if s not in existing]
            if missing:
                daily = db.execute('SELECT cagri_sayisi FROM calls_daily WHERE tarih=?',(day,)).fetchone()
                total = int(daily[0]) if daily else max(default_total, sum(int(v[0]) for v in existing.values()))
                remaining = total-sum(int(v[0]) for v in existing.values())
                if remaining < 0:raise ValueError(f'{day}: mevcut günlük toplam, yarım saat toplamından küçük. İşlem geri alındı.')
                rng = random.Random(20261109+offset)
                rows = [(day,s,n,round(292+rng.gauss(0,5),2)) for s,n in zip(missing,distribute(remaining,missing))]
                db.executemany('INSERT INTO calls_interval(tarih,slot,cagri_sayisi,aht_sec) VALUES(?,?,?,?)',rows)
                added += len(rows)
            total, weighted, average, count = db.execute('SELECT SUM(cagri_sayisi),SUM(cagri_sayisi*aht_sec),AVG(aht_sec),COUNT(*) FROM calls_interval WHERE tarih=?',(day,)).fetchone()
            if count != 48:raise ValueError(f'{day}: 48 dilim tamamlanamadı.')
            aht = weighted/total if total else average
            db.execute('INSERT INTO calls_daily(tarih,cagri_sayisi,aht_sec) VALUES(?,?,?) ON CONFLICT(tarih) DO UPDATE SET cagri_sayisi=excluded.cagri_sayisi,aht_sec=excluded.aht_sec',(day,int(total),float(aht)))
            summaries.append((day,int(total),48))
        db.execute("INSERT INTO metadata(key,value) VALUES('demo_calls_2026_11_09_15','synthetic') ON CONFLICT(key) DO UPDATE SET value=excluded.value")
        last = db.execute('SELECT MAX(tarih) FROM calls_daily').fetchone()[0]
        db.execute("INSERT INTO metadata(key,value) VALUES('history_end',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(last,))
        db.commit()
        return {'db':str(path),'backup':str(backup),'added_slots':added,'days':summaries}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default=os.environ.get('WFM_WORKSPACE_DB_PATH','data/wfm_demo.db'))
    args = parser.parse_args()
    try:result = add_week(args.db)
    except (ValueError,sqlite3.Error,OSError) as exc:parser.exit(1,f'Hata: {exc}\n')
    print('9–15 Kasım 2026 SENTETİK örnek verisi hazır.')
    print('Veritabanı:',result['db']);print('İşlem öncesi yedek:',result['backup'])
    for day,total,slots in result['days']:print(f'{day} | {total:,} çağrı | {slots} yarım saat')
    print('Eklenen yarım saat:',result['added_slots'])
    print('Toplam: 7 günlük kayıt ve 336 yarım saat. Uygulamayı yeniden başlat.')
    print('Bunlar gerçek gerçekleşmeler değildir; bu hafta üzerindeki başarı karşılaştırması demo içindir.')


if __name__ == '__main__':main()
