"""Uyumluluk dosyası. Asıl kod: ortak/vardiya_degisimleri.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.vardiya_degisimleri')
