"""Uyumluluk dosyası. Asıl kod: ortak/elle_yerlestirme.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.elle_yerlestirme')
