# Ortak / Calisma Modu — bu ekranın / servisin uygulama kodu.
"""Çalışma Modu — sentetik demo ile kurumsal veriyi birbirinden ayırır."""
import os


def demo_enabled():
    configured=os.environ.get('WFM_DEMO_MODE')
    if configured is not None:return configured.strip().lower() in {'1','true','yes'}
    return os.environ.get('WFM_IDENTITY_MODE','demo')!='api' and not bool(os.environ.get('WFM_PERSONNEL_API_URL'))
