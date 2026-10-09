import sys,tempfile,time,os
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import app as module
from database import write_people

A=np.eye(128,dtype=np.float32)[0]
B=np.eye(128,dtype=np.float32)[1]
class FakePipeline:
    def __init__(self,models):self.vector=A
    def start(self,index):pass
    def stop(self):pass
    def read(self):return np.zeros((480,640,3),np.uint8),[((160,100,160,160),self.vector)]
class FakeFolder:
    states={}
    def __init__(self,path):self.path=Path(path)
    @property
    def hidden(self):return self.states.get(str(self.path),False)

def batch(jobs):
    for path,hidden in jobs:FakeFolder.states[path]=hidden
    return [(path,True,'') for path,_ in jobs]

def pump(root,seconds=.25):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        root.update();time.sleep(.02)

def shot(root,name):
    root.update()

with tempfile.TemporaryDirectory() as d:
    base=Path(d);project=base/'FaceLocker';project.mkdir()
    f1=base/'Documents';f1.mkdir();f2=base/'Photos';f2.mkdir()
    old=base/'legacy.json';write_people(old,{'pooya':[A.tolist()]})
    with patch.object(module,'ROOT',project),patch.object(module,'Folder',FakeFolder),patch.object(module,'Pipeline',FakePipeline),patch.object(module,'apply_batch',batch):
        root=module.ctk.CTk();app=module.App(root);pump(root)
        shot(root,'fa_admin_initial')
        with patch.object(module.filedialog,'askopenfilename',return_value=str(old)):app.import_people()
        assert not app.admin_unlocked
        app.add_folder(str(f1));app.add_folder(str(f2));app.notebook.select(0);pump(root)
        app.desired[str(f2)]=False;app.refresh_folders()
        root.geometry('1200x740');pump(root)
        apply_button=next(c for c in app.pages['folders'].winfo_children() if isinstance(c,module.ttk.Button) and c.cget('text')==app.t('apply'))
        assert apply_button.winfo_viewable()
        assert apply_button.winfo_rooty()+apply_button.winfo_height()<root.winfo_rooty()+root.winfo_height()
        root.geometry('1360x860');pump(root)
        shot(root,'fa_folders_light');app.toggle_theme();pump(root);shot(root,'fa_folders_dark');assert module.load_state(project)['theme']=='dark';app.toggle_theme();pump(root)
        shot(root,'en_folders_light');app.toggle_theme();pump(root);shot(root,'en_folders_dark')
        app.request_batch(None);pump(root,.3);shot(root,'verification')
        assert not any(isinstance(w,module.ctk.CTkToplevel) for w in root.winfo_children())
        assert 'Pending approval' in app.status.get()
        assert app.canvas.winfo_viewable()
        pump(root,1.6)
        assert FakeFolder.states[str(f1)] is True and FakeFolder.states[str(f2)] is False
        assert app.mode=='idle'
        app.notebook.select(1);pump(root);app.enter_admin();pump(root,2)
        assert app.admin_unlocked
        app.name.set('Pooya New');app.person.set('pooya');app.rename()
        assert app.state['owner']=='Pooya New'
        app.notebook.select(0);pump(root);assert not app.admin_unlocked
        app.request_batch(False);app.stop('cancelled');pump(root,.2)
        assert FakeFolder.states[str(f1)] is True
        app.close()
print('PASS: real Tk widgets in English, import, mixed batch, verified admin entry, rename, tab auto-lock and cancellation; Win32/camera mocked')
