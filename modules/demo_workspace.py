"""Uyumluluk dosyası. Asıl kod: modules/ornek_calisma_alani.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('modules.ornek_calisma_alani')
