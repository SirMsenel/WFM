"""Uyumluluk dosyası. Asıl kod: ortak/okul_gorunumu.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.okul_gorunumu')
