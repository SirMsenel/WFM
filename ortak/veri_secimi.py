"""Çağrı veri kaynağı için kayıpsız sütun seçimi."""
import pandas as pd

def select_columns(source,columns):
    if not columns:raise ValueError('En az bir sütun seçin; tarih ve çağrı sayısı sütunları gerekli.')
    if any(c not in source for c in columns):raise ValueError('Seçilen sütun kaynakta bulunamadı; seçimi yenileyin.')
    result=source.loc[:,list(dict.fromkeys(columns))].copy()
    from ortak.cagri_tahmin_servisi import date_column
    try:date=date_column(result)
    except ValueError:raise ValueError('Tarih sütununu da seçin.')
    if date is None:raise ValueError('Tarih sütununu da seçin.')
    numeric=[c for c in result if c!=date and pd.api.types.is_numeric_dtype(result[c])]
    if not numeric:raise ValueError('Çağrı sayısını içeren sayısal sütunu da seçin.')
    return result
