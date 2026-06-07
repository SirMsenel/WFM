CARD_STYLE = """
<div style="
    height: 130px;
    padding: 12px;
    border-radius: 10px;
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: center;
">
  <div style="font-size:16px; font-weight:600; color:black;">{title}</div>
  <div style="font-size:28px; font-weight:800; color:black; margin-top:6px;">{value}</div>
  {note}
</div>
"""

def card_html(bg: str, title: str, value: str, note_text: str | None = None) -> str:
    note = ""
    if note_text:
        note = f'<div style="font-size:12px; color:black; margin-top:4px;">{note_text}</div>'
    html = CARD_STYLE.format(title=title, value=value, note=note)
    return html.replace("height: 130px;", f"height: 130px; background-color:{bg};")