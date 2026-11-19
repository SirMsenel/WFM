"""Uyumluluk dosyası. Asıl kod: ortak/calisma_modu.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.calisma_modu')
