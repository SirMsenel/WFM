from core.workspace_store import save_keys


def manage_profiles(state,names,action):
    names=list(dict.fromkeys(names))
    by_name={p['name']:p for p in state.get('sp_ratio_profiles',[])}
    if not names or any(n not in by_name for n in names):
        raise ValueError('İşlem için kayıtlı bir profil seçin.')
    if action=='activate':
        if len(names)!=1:
            raise ValueError('Aktif yapmak için yalnızca bir profil seçin.')
        profile=by_name[names[0]]
        state.update(sp_active_ratio_profile_name=names[0],sp_active_ratio_profile_df=profile['profile_df'].copy(),
                     sp_active_ratio_profile_meta=profile.get('meta',{}),sp_staffing_result_df=None,plan_ctx_confirmed=False)
    elif action=='delete':
        state['sp_ratio_profiles']=[p for n,p in by_name.items() if n not in names]
        if state.get('sp_active_ratio_profile_name') in names:
            state.update(sp_active_ratio_profile_name=None,sp_active_ratio_profile_df=None,sp_active_ratio_profile_meta=None,
                         sp_staffing_result_df=None,plan_ctx_confirmed=False)
        state['demo_initial_profile_done']=True
    else:
        raise ValueError('Bilinmeyen profil işlemi.')
    save_keys(state)
