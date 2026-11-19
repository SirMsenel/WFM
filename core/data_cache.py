"""Uyumluluk dosyası. Asıl kod: ortak/veri_onbellegi.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.veri_onbellegi')
