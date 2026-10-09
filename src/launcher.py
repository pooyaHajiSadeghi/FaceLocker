"""Build this file as FaceLocker.exe; it drives first-run setup and daily launch."""
import ctypes
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import ui as ttk
from bootstrap import Installer,install_root,payload_root,migrate_adjacent_data
from strings import text
from instance import activate_existing
from window_lifecycle import show_and_confirm

class Launcher:
    def __init__(self,root):
        self.root=root;self.theme='light';self.events=queue.Queue();self.busy=False
        self.key='boot_start';self.values={}
        self.engine=Installer(install_root(),payload_root(),self.emit)
        adjacent=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent.parent
        migrated=migrate_adjacent_data(adjacent,self.engine.root)
        if not migrated and adjacent.name=='dist' and (adjacent.parent/'src'/'launcher.py').is_file():
            migrate_adjacent_data(adjacent.parent,self.engine.root)
        try:
            import json
            saved=json.loads((self.engine.root/'data'/'state.json').read_text(encoding='utf-8'))
            if saved.get('theme') in ('light','dark'):self.theme=saved['theme']
        except (OSError,ValueError):pass
        ttk.appearance(self.theme,root)
        root.title('FaceLocker');root.geometry('600x460');root.resizable(False,False)
        root.protocol('WM_DELETE_WINDOW',self.close)
        top=ctk.CTkFrame(root,corner_radius=22,fg_color=ttk.CARD,border_width=1,border_color=ttk.BORDER);top.pack(fill='both',expand=True,padx=18,pady=18)
        ttk.section(top,'FaceLocker','First-run setup · Ready for everyday use','lock')
        controls=ttk.Frame(top);controls.pack(fill='x',padx=18,pady=6)
        ttk.Button(controls,text='Toggle theme',variant='secondary',command=self.toggle_theme).pack(side='left')
        self.status=tk.StringVar();ttk.Paragraph(top,textvariable=self.status,line_width=500).pack(fill='x',padx=20,pady=(14,6))
        self.progress=ttk.Progressbar(top,mode='indeterminate');self.progress.pack(fill='x',padx=18,pady=14)
        self.hint=tk.StringVar();ttk.Paragraph(top,textvariable=self.hint,line_width=500,text_color=ttk.MUTED).pack(fill='x',padx=20)
        row=ttk.Frame(top);row.pack(fill='x',padx=18,pady=18)
        self.retry=ttk.Button(row,command=self.start);self.retry.pack(side='left',padx=3)
        self.log=ttk.Button(row,variant='secondary',command=self.open_log);self.log.pack(side='left',padx=3)
        self.quit=ttk.Button(row,variant='secondary',command=self.close);self.quit.pack(side='right')
        ttk.Label(top,text='Developer · Pooya Haji Sadeghi',text_color=ttk.MUTED,font=('Segoe UI',11)).pack(side='bottom',anchor='e',padx=20,pady=14)
        self.translate();root.after(100,self.poll);root.after(150,self.start)

    def t(self,key,**values):return text(key,**values)
    def emit(self,key,**values):self.events.put(('status',key,values))
    def translate(self):
        self.status.set(text(self.key,**self.values));self.hint.set(text('boot_hint'))
        self.retry.configure(text=self.t('boot_retry'));self.log.configure(text=self.t('boot_log'));self.quit.configure(text=self.t('boot_close'))

    def toggle_theme(self):
        self.theme='dark' if self.theme=='light' else 'light'
        ttk.appearance(self.theme,self.root)

    def start(self):
        if self.busy:return
        self.busy=True;self.retry.configure(state='disabled');self.progress.start(12)
        self.emit('boot_start')
        def work():
            try:
                self.engine.ensure();self.engine.launch()
                self.events.put(('done',None,None))
            except Exception as exc:
                self.engine.record_error();self.events.put(('error',str(exc),None))
        threading.Thread(target=work,daemon=True).start()

    def poll(self):
        try:
            while True:
                kind,key,values=self.events.get_nowait()
                if kind=='status':
                    if key=='boot_window_ready':self.progress.stop();self.root.withdraw()
                    else:self.key=key;self.values=values;self.translate()
                elif kind=='done':self.busy=False;self.root.destroy();return
                elif kind=='error':
                    self.busy=False;self.progress.stop();self.retry.configure(state='normal')
                    self.key='boot_error';self.values={'detail':key};self.translate();self.root.geometry('600x540');self.root.deiconify()
        except queue.Empty:pass
        self.root.after(100,self.poll)

    def open_log(self):
        if self.engine.log_path.exists():os.startfile(str(self.engine.log_path))
    def close(self):
        if self.busy:messagebox.showinfo('FaceLocker',self.t('boot_busy'));return
        self.root.destroy()

def main():
    root=ctk.CTk();mutex=None
    try:
        if os.name!='nt':raise RuntimeError('FaceLocker.exe requires Windows 11 x64.')
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p];api.CreateMutexW.restype=ctypes.c_void_p
        api.CloseHandle.argtypes=[ctypes.c_void_p];api.CloseHandle.restype=ctypes.c_int
        ctypes.set_last_error(0);mutex=api.CreateMutexW(None,False,'Local\\FaceLockerBootstrap_v3');error=ctypes.get_last_error()
        if not mutex:raise ctypes.WinError(error)
        if error==183:
            if not activate_existing():messagebox.showinfo('FaceLocker',text('already_running'))
            root.destroy();return
        # Prevent PyInstaller DLL search paths from contaminating external Python/installer processes.
        if getattr(sys,'frozen',False):
            api.SetDllDirectoryW.argtypes=[ctypes.c_wchar_p];api.SetDllDirectoryW.restype=ctypes.c_int
            if not api.SetDllDirectoryW(None):raise ctypes.WinError(ctypes.get_last_error())
        Launcher(root);show_and_confirm(root);root.mainloop()
    except Exception as exc:messagebox.showerror('FaceLocker',str(exc),parent=root);root.destroy();raise
    finally:
        if mutex:api.CloseHandle(mutex)

if __name__=='__main__':main()
