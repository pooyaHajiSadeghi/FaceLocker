"""Exercise CustomTkinter's actual Windows startup branch on a real Tk display."""
import importlib
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch
import customtkinter as ctk
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from window_lifecycle import show_and_confirm
from instance import report_ready
import tempfile,os,json
module=importlib.import_module('customtkinter.windows.ctk_tk')
win=SimpleNamespace(user32=SimpleNamespace(GetParent=lambda _:0),dwmapi=SimpleNamespace(DwmSetWindowAttribute=lambda *args:0))

def scenario(early_withdraw):
 root=ctk.CTk();root.geometry('360x180')
 if early_withdraw:root.withdraw()
 root.deiconify()
 result={}
 def observe():
  result.update(state=root.state(),viewable=bool(root.winfo_viewable()))
  root.quit()
 root.after(300,observe)
 with patch.object(module,'sys',SimpleNamespace(platform='win32')),patch.object(module.ctypes,'windll',win,create=True):
  root.mainloop()
 for timer in root.tk.call('after','info'):root.after_cancel(timer)
 root.destroy()
 return result
old=scenario(True);fixed=scenario(False)
assert old=={'state':'withdrawn','viewable':False},old
assert fixed=={'state':'normal','viewable':True},fixed
print('PASS: reproduced old hidden Windows window; removal of pre-loop withdraw restores mapped window')

with tempfile.TemporaryDirectory() as d:
 marker=Path(d)/'ready.json';root=ctk.CTk();root.withdraw()
 events=[]
 def ready():
  assert root.winfo_viewable();assert root.state()=='normal'
  report_ready();events.append('visible');root.quit()
 with patch.dict(os.environ,{'FACELOCKER_READY_FILE':str(marker)}):
  show_and_confirm(root,ready)
  assert not marker.exists()
  root.after(2000,root.quit);root.mainloop()
 assert events==['visible'] and marker.exists()
 root.destroy()
 print('PASS: readiness marker appears only after the Tk window is viewable')
