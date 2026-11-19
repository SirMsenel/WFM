"""Kullanıcının seçtiği renk paletini ortak arayüze uygular."""

PALETTES={
    'Okyanus':{'primary':'#148797','soft':'#e8f6f7','dark':'#173e50','line':'#dbe9ee'},
    'Mürdüm':{'primary':'#7656a6','soft':'#f3edfb','dark':'#3e2b59','line':'#e7ddef'},
    'Orman':{'primary':'#217b62','soft':'#eaf6ef','dark':'#174638','line':'#d8ebe1'},
    'Gece':{'primary':'#405a86','soft':'#edf1f8','dark':'#1f304b','line':'#dce3ef'},
}


def css(name='Okyanus'):
    palette=PALETTES.get(name,PALETTES['Okyanus'])
    return f'''<style>
    :root{{--wfm-primary:{palette['primary']};--wfm-soft:{palette['soft']};--wfm-dark:{palette['dark']};--wfm-line:{palette['line']};}}
    h1,h2{{color:var(--wfm-dark)!important;border-bottom-color:var(--wfm-line)!important}}
    h3,.wfm-section-label{{color:var(--wfm-primary)!important}}
    .wfm-section-rule{{background:linear-gradient(90deg,var(--wfm-primary),var(--wfm-line) 62%,transparent)!important}}
    div[data-testid="stSegmentedControl"] button[aria-pressed="true"],div.stButton > button[kind="primary"]{{background:var(--wfm-primary)!important;border-color:var(--wfm-primary)!important;color:#fff!important}}
    section[data-testid="stSidebar"]{{border-right-color:var(--wfm-line)!important}}
    </style>'''
