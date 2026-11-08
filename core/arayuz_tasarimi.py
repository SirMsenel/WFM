"""Uyumluluk dosyası. Asıl kod: ortak/arayuz_tasarimi.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.arayuz_tasarimi')
