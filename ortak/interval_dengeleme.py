# Ortak / Interval Dengeleme — bu ekranın / servisin uygulama kodu.
import numpy as np
import pandas as pd


def rebalance_profile(base,edited,pinned=()):
    """Pin manual cells; consume 03–08 first, then other unpinned slots."""
    from modules.mesai_plani.interval_dagilimi import matrix_table
    original=matrix_table(base);values=edited.apply(pd.to_numeric,errors='coerce')
    if values.shape!=original.shape or not values.columns.equals(original.columns) or not values.index.equals(original.index):raise ValueError('7 gün × 48 yarım saat yapısı korunmalı.')
    if not np.isfinite(values.to_numpy()).all() or ((values<0)|(values>100)).any().any():raise ValueError('Bütün paylar 0–100 arasında olmalı.')
    pins=set(tuple(p) for p in pinned)
    for c in values:
        for i in range(48):
            if abs(values[c].iloc[i]-original[c].iloc[i])>1e-9:pins.add((c,i+1))
    for c in values:
        locked=[i for i in range(48) if (c,i+1) in pins]
        if values[c].iloc[locked].sum()>100+1e-9:raise ValueError(f'{c}: sabitlediğin paylar %100’ü aşıyor.')
        groups=[[i for i in range(6,16) if i not in locked],[i for i in range(48) if i not in locked and i not in range(6,16)]]
        delta=float(values[c].sum()-100)
        if delta>1e-9:
            for indices in groups:
                available=float(values[c].iloc[indices].sum());take=min(delta,available)
                if available:values.loc[values.index[indices],c]*=(available-take)/available
                delta-=take
                if delta<1e-9:break
            if delta>1e-7:raise ValueError(f'{c}: diğer dilimlerden yeterli pay düşülemiyor.')
        elif delta< -1e-9:
            receivers=groups[0] or groups[1]
            if not receivers:raise ValueError(f'{c}: eksik payı eklemek için sabitlenmemiş bir hücre bırakın.')
            weights=values[c].iloc[receivers].to_numpy();weights=weights/weights.sum() if weights.sum() else np.ones(len(receivers))/len(receivers)
            values.loc[values.index[receivers],c]+=(-delta)*weights
    result=base.copy()
    for index,r in result.iterrows():result.loc[index,'Oran(%)']=values[r['Gün']].iloc[int(r.Slot)-1]
    return result,sorted(pins)
