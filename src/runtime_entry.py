"""Unbuffered desktop entry with early Python/native failure diagnostics."""
import faulthandler
import os
from pathlib import Path
import runpy
import sys
import traceback

def main():
    faulthandler.enable()
    if os.name=='nt':
        for key in ('TCL_LIBRARY','TK_LIBRARY','TCLLIBPATH'):
            os.environ.pop(key,None)
    root=Path(os.environ['FACELOCKER_HOME'])/'app' if '--installed' in sys.argv else Path(__file__).resolve().parent
    sys.path.insert(0,str(root))
    sys.argv=[str(root/'app.py')]
    print(f'[startup] Python {sys.version}; executable={sys.executable}',flush=True)
    print(f'[startup] Loading {root / "app.py"}',flush=True)
    try:
        runpy.run_path(str(root/'app.py'),run_name='__main__')
    except SystemExit as exc:
        print(f'[startup] SystemExit: {exc.code}',flush=True)
        return exc.code if isinstance(exc.code,int) else 0 if exc.code is None else 1
    except BaseException:
        traceback.print_exc();return 1
    print('[startup] Application returned normally',flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
