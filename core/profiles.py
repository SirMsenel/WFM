"""Uyumluluk dosyası. Asıl kod: ortak/profil_yonetimi.py"""
import importlib as _importlib
import sys as _sys
_sys.modules[__name__] = _importlib.import_module('ortak.profil_yonetimi')
