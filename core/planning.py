"""Uyumluluk dosyası. Asıl kod: ortak/planlama.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.planlama')
