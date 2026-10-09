"""Удаление только в Корзину: SHFileOperationW с FOF_ALLOWUNDO.

Насовсем здесь ничего не удаляется. Не Windows или Корзина недоступна - исключение,
и вызывающий код оставляет файлы на месте.
"""
import ctypes
import os
import sys

FO_DELETE = 3
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040
FOF_NOERRORUI = 0x0400


class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint),
                ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
                ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_int),
                ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p)]


def to_recycle_bin(path):
    """Переложить файл или папку в Корзину. Нет пути - ничего не делать."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return False
    if sys.platform != "win32":
        raise OSError("Корзина есть только в Windows - файл оставлен на месте: " + path)
    op = _SHFILEOPSTRUCTW()
    op.wFunc = FO_DELETE
    op.pFrom = path + "\0\0"
    op.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI
    code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if code != 0 or op.fAnyOperationsAborted or os.path.exists(path):
        raise OSError(f"в Корзину не получилось (код {code}): {path}")
    return True
