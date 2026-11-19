"""Uyumluluk dosyası. Asıl kod: ortak/yayin_servisi.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.yayin_servisi')
