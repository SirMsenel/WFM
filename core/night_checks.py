"""Uyumluluk dosyası. Asıl kod: ortak/gece_kontrolleri.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.gece_kontrolleri')
