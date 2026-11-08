"""Uyumluluk dosyası. Asıl kod: modules/takip/ders_programi.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('modules.takip.ders_programi')
