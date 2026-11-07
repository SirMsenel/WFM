def slot_label(slot):
    minute=(int(slot)-1)*30
    return f'{minute//60:02d}:{minute%60:02d}–{(minute+30)//60:02d}:{(minute+30)%60:02d}'
