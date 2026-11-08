from copy import deepcopy
from datetime import date
from core.workspace_store import save_keys

LOCKED={'fixed_external','approved_request'}


def key(row):
    return str(row['employee_id']),str(row['date'])


def edit_shifts(state,additions=(),deletions=()):
    from core.planning_guard import assert_can_plan
    if state.get('plan_ctx'):assert_can_plan(state)
    from modules.shift_planing.engine import bounds
    rows={key(r):deepcopy(r) for r in state.get('draft_shift_plan',[])}
    deleted={tuple(map(str,k)) for k in deletions}
    added={key(r):deepcopy(r) for r in additions}
    touched=sorted(deleted|set(added))
    for k in touched:
        if k in rows and rows[k].get('source') in LOCKED:
            raise ValueError('Gece/izin veya onaylı talep kaydını kendi kaynak ekranından değiştirin.')
    for row in added.values():
        date.fromisoformat(str(row['date']))
        bounds(row)
    before=[deepcopy(rows.get(k)) for k in touched]
    removed={tuple(map(str,k)) for k in state.get('plan_removed_assignments',[])}
    removed_before=[k in removed for k in touched]
    for k in deleted:
        rows.pop(k,None)
    rows.update(added)
    after=[deepcopy(rows.get(k)) for k in touched]
    if before==after:
        return 0
    removed.update(deleted);removed.difference_update(added)
    removed_after=[k in removed for k in touched]
    history=list(state.get('shift_edit_history',[]))
    # Store only affected rows. One manual edit must not serialize the full roster.
    history.append({'keys':[list(k) for k in touched],'before':before,'after':after,
                    'removed_before':removed_before,'removed_after':removed_after})
    state.update(draft_shift_plan=list(rows.values()),plan_removed_assignments=[list(k) for k in sorted(removed)],shift_edit_history=history[-20:])
    save_keys(state)
    return len(touched)


def undo_edit(state):
    history=list(state.get('shift_edit_history',[]))
    if not history:
        raise ValueError('Geri alınacak işlem yok.')
    entry=history[-1]
    rows={key(r):r for r in state.get('draft_shift_plan',[])}
    removed={tuple(map(str,k)) for k in state.get('plan_removed_assignments',[])}
    keys=[tuple(k) for k in entry['keys']]
    if [rows.get(k) for k in keys]!=entry['after'] or [k in removed for k in keys]!=entry['removed_after']:
        raise ValueError('Etkilenen kayıt başka bir işlemle değişti; eski işlem güvenle geri alınamıyor.')
    for k,old,was_removed in zip(keys,entry['before'],entry['removed_before']):
        if old is None:
            rows.pop(k,None)
        else:
            rows[k]=deepcopy(old)
        if was_removed:
            removed.add(k)
        else:
            removed.discard(k)
    state.update(draft_shift_plan=list(rows.values()),plan_removed_assignments=[list(k) for k in sorted(removed)],shift_edit_history=history[:-1])
    save_keys(state)
