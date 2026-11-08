# Ortak / Arayuz Tasarimi — bu ekranın / servisin uygulama kodu.
"""Arayüz Tasarımı — mevcut başlık ve simgeleri koruyan ortak görsel dil."""
APP_CSS='''<style>
.stMainBlockContainer{padding-top:2.6rem!important;max-width:1580px}
section[data-testid="stSidebar"]{background:linear-gradient(170deg,#f1f7fb 0%,#fff 70%)!important;border-right:1px solid #dce8ef}
section[data-testid="stSidebar"] button{border-radius:14px!important;border-color:#e0e9f0!important;box-shadow:none!important;transition:transform .14s,background .14s}
section[data-testid="stSidebar"] button:hover{transform:translateX(3px);background:#eaf6f8!important;border-color:#74b7c2!important}
.sidebar-profile-card{background:linear-gradient(135deg,#fff,#eaf5f7)!important;border:1px solid #d5e8ed!important;box-shadow:0 8px 25px #173e5010!important;border-radius:22px!important}
.sidebar-avatar{background:#d8eef1!important;color:#0c6373!important}
.sidebar-role-badge{background:#e6f5ef!important;color:#14684e!important;border-color:#c4e6d7!important}
.active-menu-item{background:linear-gradient(100deg,#dceff3,#f1f8fa)!important;border-left:4px solid #148797!important;box-shadow:none!important}
[data-testid="stMetricValue"]{font-variant-numeric:tabular-nums;color:#234553}
[data-testid="stVerticalBlockBorderWrapper"]{border-color:#dce6ed;border-radius:16px}
</style>'''
LOGIN_CSS='''<style>
.stApp{background:radial-gradient(ellipse at 20% 10%,#d7eff3 0%,transparent 50%),radial-gradient(ellipse at 85% 85%,#e9e5f8 0%,transparent 45%),#f7fafc!important}
.login-title{font-size:32px!important;letter-spacing:-.7px;color:#14394a!important}
.login-subtitle{color:#5f7681!important;line-height:1.65}
.login-logo{background:linear-gradient(135deg,#e1f2f5,#f4edff)!important;border-radius:22px;display:inline-block;padding:14px;box-shadow:0 8px 25px #29748115}
.login-badge{background:#e6f4f5!important;color:#236978!important;border:1px solid #d4e9ec!important}
div[data-testid="stForm"]{border:0!important;background:transparent!important;padding:0!important}
button[kind="secondaryFormSubmit"]{background:linear-gradient(100deg,#117f91,#3e718f)!important;color:white!important;border:0!important;border-radius:14px!important;min-height:48px;box-shadow:0 8px 20px #117f9125!important}
</style>'''
