"""Startup handshake and restoring an existing visible Windows window."""
import ctypes
import json
import os
from pathlib import Path

def report_ready():
    path=os.environ.get('FACELOCKER_READY_FILE')
    if not path:return
    destination=Path(path)
    temporary=destination.with_suffix('.tmp')
    temporary.write_text(json.dumps({'pid':os.getpid()}),encoding='utf-8')
    os.replace(temporary,destination)
    print('[startup] Window ready',flush=True)

def activate_existing():
    if os.name!='nt':return False
    api=ctypes.WinDLL('user32',use_last_error=True)
    callback_type=ctypes.WINFUNCTYPE(ctypes.c_int,ctypes.c_void_p,ctypes.c_ssize_t)
    api.EnumWindows.argtypes=[callback_type,ctypes.c_ssize_t];api.EnumWindows.restype=ctypes.c_int
    api.GetWindowTextW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_int]
    api.IsWindowVisible.argtypes=[ctypes.c_void_p];api.IsWindowVisible.restype=ctypes.c_int
    api.ShowWindow.argtypes=[ctypes.c_void_p,ctypes.c_int]
    api.SetForegroundWindow.argtypes=[ctypes.c_void_p];api.SetForegroundWindow.restype=ctypes.c_int
    found=[]
    @callback_type
    def visit(handle,_):
        title=ctypes.create_unicode_buffer(256);api.GetWindowTextW(handle,title,256)
        if title.value=='FaceLocker' and api.IsWindowVisible(handle):
            found.append(handle);return 0
        return 1
    api.EnumWindows(visit,0)
    if not found:return False
    api.ShowWindow(found[0],9)
    return bool(api.SetForegroundWindow(found[0]))
