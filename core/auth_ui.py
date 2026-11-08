"""Uyumluluk dosyası. Asıl kod: ortak/kimlik_gorunumu.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.kimlik_gorunumu')
