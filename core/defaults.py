"""Uyumluluk dosyası. Asıl kod: ortak/varsayilan_kurallar.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.varsayilan_kurallar')
