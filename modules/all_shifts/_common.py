"""Uyumluluk dosyası. Asıl kod: modules/tum_vardiyalar/ortak.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('modules.tum_vardiyalar.ortak')
