"""Yalnızca demo modunda kullanılacak geçici uygulama zamanı yardımcısı."""
from datetime import datetime, time
from zoneinfo import ZoneInfo
import pandas as pd


def now(state=None):
    """Gerçek zamanı veya kullanıcı tarafından seçilen demo zamanını döndürür."""
    state=state or {}
    if state.get('demo_clock_enabled') and state.get('demo_clock_date'):
        day=pd.Timestamp(state['demo_clock_date']).date()
        clock=state.get('demo_clock_time') or time(10,0)
        if isinstance(clock,str):clock=time.fromisoformat(clock)
        return datetime.combine(day,clock)
    return datetime.now(ZoneInfo('Europe/Istanbul')).replace(tzinfo=None)


def today(state=None):
    return now(state).date()


def completed_week_end(state=None):
    """Bugünkü haftanın başlangıcından önceki pazar: güvenli sentetik geçmiş kesimi."""
    day=today(state)
    from datetime import timedelta
    return day-timedelta(days=day.weekday()+1)
