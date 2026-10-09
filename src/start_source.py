"""Install/repair once, then run the same managed launcher and data as the EXE."""
import os
import ctypes
from pathlib import Path
import subprocess
import sys
import traceback
from bootstrap import Installer,install_root,migrate_adjacent_data
from instance import activate_existing

def main():
    root=install_root();source=Path(__file__).resolve().parent.parent
    stages={'boot_payload':'Preparing application files','boot_python':'Checking Python 3.10',
            'boot_download':'Downloading Python','boot_install':'Installing Python',
            'boot_env':'Creating the application environment','boot_packages':'Installing packages',
            'boot_models':'Preparing face models'}
    engine=Installer(root,source,lambda key,**values:print('[setup]',stages.get(key,key),values or '',flush=True))
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p];api.CreateMutexW.restype=ctypes.c_void_p
    api.CloseHandle.argtypes=[ctypes.c_void_p];api.CloseHandle.restype=ctypes.c_int
    ctypes.set_last_error(0);handle=api.CreateMutexW(None,False,'Local\\FaceLockerBootstrap_v3');error=ctypes.get_last_error()
    if not handle:raise ctypes.WinError(error)
    try:
        if error==183:
            activate_existing();print('FaceLocker is already running or being installed.',flush=True);return 0
        migrate_adjacent_data(source,root)
        print('FaceLocker 4: preparing the managed environment.',flush=True)
        python=engine.ensure()
    finally:api.CloseHandle(handle)

    return subprocess.call([str(python),'-u','-X','faulthandler',str(source/'src'/'launcher.py')],env=engine.env,cwd=source)

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:
        traceback.print_exc();raise SystemExit(1)
