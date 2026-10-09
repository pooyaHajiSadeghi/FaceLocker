"""Build on Windows x64. App sources are data; CV dependencies are installed at first run."""
import os
from pathlib import Path
import struct
import subprocess
import sys
from bootstrap import APP_FILES,payload_file

def main():
    if os.name!='nt' or struct.calcsize('P')!=8 or sys.version_info[:2]!=(3,10):
        raise RuntimeError('Build FaceLocker.exe on Windows using Python 3.10 x64.')
    root=Path(__file__).resolve().parent.parent
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed',
             '--name','FaceLocker','--distpath',str(root/'dist'),'--workpath',str(root/'build'),
             '--specpath',str(root/'build'),'--collect-all','customtkinter','--collect-all','PIL']
    for name in APP_FILES:
        command+=['--add-data',f'{payload_file(root,name)};payload']
    command+=[str(root/'src'/'launcher.py')]
    subprocess.run(command,cwd=root,check=True)
    exe=root/'dist'/'FaceLocker.exe'
    if not exe.is_file():raise RuntimeError('Build did not produce FaceLocker.exe.')
    print('Ready:',exe)

if __name__=='__main__':main()
