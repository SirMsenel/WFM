from html import escape


def palette(value):
    text=str(value or '')
    if text in {'Onaylandı','Uygulandı'}:return '#dcfce7','#166534'
    if text=='Reddedildi':return '#fee2e2','#991b1b'
    if any(word in text.casefold() for word in ('bekle','iletildi','değerlendirme')):return '#fef3c7','#92400e'
    return '#edf2f7','#475569'


def cell_style(value):
    bg,fg=palette(value)
    return f'background-color:{bg};color:{fg};font-weight:600'


def badge(value):
    bg,fg=palette(value)
    return f'<span style="display:inline-block;background:{bg};color:{fg};padding:6px 12px;border-radius:20px;font-size:13px;font-weight:600">{escape(str(value or "—"))}</span>'
