"""Uyumluluk dosyası. Asıl kod: ortak/off_dagilimi.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.off_dagilimi')
