"""Uyumluluk dosyası. Asıl kod: ortak/ornek_veri.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.ornek_veri')
