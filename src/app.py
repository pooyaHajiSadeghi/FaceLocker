"""FaceLocker v4: English menus, verified folder batches and an admin area."""
from pathlib import Path
import argparse
import copy
import ctypes
import os
import time
import sys
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import ui as ttk
from tkinter import font as tkfont
import cv2
from database import load_state, save_state, read_people, renamed_state, valid_name, identify, validate_settings
from locker import Folder, prepare_jobs, apply_batch, VerifiedAction, validate_folder
from vision import Pipeline, download_models
from strings import text
from instance import activate_existing, report_ready
from window_lifecycle import show_and_confirm

ROOT=Path(os.environ.get('FACELOCKER_HOME',str(Path(__file__).resolve().parent.parent if Path(__file__).resolve().parent.name=='src' else Path(__file__).resolve().parent))).resolve()

class App:
    def __init__(self,root):
        self.root=root
        self.font_family='Segoe UI' if os.name=='nt' else 'DejaVu Sans'
        for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont'):
            tkfont.nametofont(name).configure(family=self.font_family,size=10)
        self.state=load_state(ROOT)
        self.theme=self.state.get('theme','light')
        ttk.appearance(self.theme,root)
        self.pipeline=None
        self.mode='idle'
        self.pending=None
        self.closed=False
        self.admin_unlocked=not bool(self.state['people'])
        self.checked=set()
        self.desired={p:True for p in self.state['folders']}
        self.task_status=('camera_off',{})
        root.title('FaceLocker')
        root.configure(fg_color=ttk.BG)
        root.geometry('1360x860')
        root.minsize(1200,740)
        root.protocol('WM_DELETE_WINDOW',self.close)
        root.bind('<Escape>',lambda _:self.stop('cancelled'))
        self.build(1 if not self.state['people'] else 0)
        root.after(120,self.tick)

    def t(self,key,**values):
        return text(key,**values)

    def raw(self,key,**values):
        return text(key,**values)

    def notify(self,key,**values):
        self.task_status=(key,values)
        message=self.raw(key,**values)
        if self.mode=='verify' and isinstance(self.pending,VerifiedAction):
            action=self.pending
            detail=self.raw('planned',hidden=sum(hidden for _,hidden in action.jobs),visible=sum(not hidden for _,hidden in action.jobs)) if action.purpose=='folders' else self.raw('admin' if action.purpose=='admin' else 'settings')
            message+=f'\n{detail}'
        self.status.set(message)

    def button(self,parent,key,callback,**pack):
        variant='danger' if key in ('delete','remove','stop') else 'secondary' if key in ('default','select_all','select_none','refresh','show_selected','lock_admin','rename','import','set_owner') else 'primary'
        widget=ttk.Button(parent,text=self.t(key),variant=variant,command=lambda:self.action(callback))
        widget.pack(**({'side':'left','padx':3,'pady':4}|pack))
        return widget

    def action(self,callback):
        try:
            callback()
        except Exception as exc:
            self.stop('cancelled')
            messagebox.showerror(self.t('error'),self.t('error_msg',detail=str(exc)),parent=self.root)

    def build(self,page=0):
        self.building=True
        for child in self.root.winfo_children(): child.destroy()
        header=ttk.Card(self.root)
        header.pack(fill='x',padx=24,pady=(20,10))
        logo=ttk.Card(header,soft=True);logo.pack(side='left',padx=(20,4),pady=18)
        ttk.Label(logo,text='',image=ttk.icon('lock',38),width=54,height=54).pack(padx=6,pady=6)
        brand=ttk.Frame(header);brand.pack(side='left',padx=14,pady=16)
        ttk.Label(brand,text='FaceLocker',font=(self.font_family,29,'bold')).pack(anchor='w')
        ttk.Label(brand,text=self.t('tagline'),text_color=ttk.MUTED,font=(self.font_family,13)).pack(anchor='w')
        self.theme_button=ttk.Button(header,text=self.t('dark_theme' if self.theme=='light' else 'light_theme'),variant='secondary',command=lambda:self.action(self.toggle_theme))
        self.theme_button.pack(side='right',padx=20)
        footer=ttk.Frame(self.root);footer.pack(side='bottom',fill='x',padx=28,pady=(0,12))
        ttk.Label(footer,text='Windows 11  /  Local webcam recognition',text_color=ttk.MUTED,font=(self.font_family,11)).pack(side='left')
        ttk.Label(footer,text='Developer · Pooya Haji Sadeghi',text_color=ttk.MUTED,font=(self.font_family,11)).pack(side='right')
        body=ttk.Frame(self.root);body.pack(fill='both',expand=True,padx=24,pady=(0,12))
        self.notebook=ttk.Notebook(body);self.notebook.pack(side='left',fill='both',expand=True,padx=(0,18))
        self.pages={}
        for key in ('folders','admin','settings','help'):
            self.pages[key]=self.notebook.add(self.t(key))
        self.build_folders()
        self.build_admin()
        self.build_settings()
        ttk.section(self.pages['help'],'Get started','Select. Verify. Hide or unhide.','lock')
        help_card=ttk.Card(self.pages['help'],soft=True);help_card.pack(fill='x',padx=16,pady=12)
        ttk.Paragraph(help_card,text=self.raw('help_text'),line_width=570).pack(fill='x',padx=20,pady=20)
        video=ttk.Card(body);video.pack(side='right',fill='y',pady=(20,0))
        ttk.section(video,'Face verification','One clear face for administrator approval.','lock')
        self.canvas=tk.Canvas(video,width=400,height=300,bg='#122b24',highlightthickness=0);self.canvas.pack(padx=16,pady=(0,8))
        status_card=ttk.Card(video,soft=True);status_card.pack(fill='x',padx=16,pady=(0,10))
        self.status=tk.StringVar(value=self.raw(*self.task_status[:1],**self.task_status[1]))
        ttk.Paragraph(status_card,textvariable=self.status,line_width=365).pack(fill='x',padx=14,pady=8)
        self.button(video,'preview',self.preview,side='top',fill='x',padx=16)
        self.button(video,'stop',lambda:self.stop('cancelled'),side='top',fill='x',padx=16)
        note=ttk.Frame(video);note.pack(fill='x',padx=20,pady=14)
        ttk.Paragraph(note,text=self.raw('auth_hint'),line_width=365,text_color=ttk.MUTED,font=(self.font_family,12)).pack(fill='x')
        self.notebook.select(page)
        self.notebook.bind('<<NotebookTabChanged>>',self.on_tab)
        self.refresh_folders();self.refresh_admin();self.blank(self.canvas)
        self.building=False

    def build_folders(self):
        page=self.pages['folders']
        ttk.section(page,'Your folders','Choose folders and set their next visibility.','folder')
        row=ttk.Frame(page);row.pack(fill='x',padx=16)
        self.button(row,'browse',self.browse)
        self.button(row,'default',self.add_default)
        self.button(row,'remove',self.remove_folders)
        table=ttk.Card(page);table.pack(fill='both',expand=True,padx=16,pady=(10,8))
        table.columnconfigure(0,weight=1);table.rowconfigure(0,weight=1)
        self.tree=ttk.Treeview(table,columns=('check','name','path','current','desired'),show='headings',height=7,selectmode='extended')
        for key,width in (('check',70),('name',130),('path',180),('current',110),('desired',110)):
            self.tree.heading(key,text='Current' if key=='current' else self.t('folder_name' if key=='name' else key))
            self.tree.column(key,width=width,minwidth=width,stretch=key=='path',anchor='center' if key!='path' else 'w')
        self.tree.grid(row=0,column=0,sticky='nsew',padx=(12,0),pady=(12,0))
        vertical=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview);vertical.grid(row=0,column=1,sticky='ns')
        horizontal=ttk.Scrollbar(table,orient='horizontal',command=self.tree.xview);horizontal.grid(row=1,column=0,sticky='ew')
        self.tree.configure(xscrollcommand=horizontal.set,yscrollcommand=vertical.set)
        self.tree.bind('<Button-1>',self.tree_click)
        self.rows={}
        row=ttk.Frame(page);row.pack(fill='x',padx=16)
        self.button(row,'select_all',self.select_all)
        self.button(row,'select_none',self.select_none)
        self.button(row,'refresh',self.refresh_folders)
        ttk.Paragraph(page,text=self.raw('folder_hint'),line_width=620,text_color=ttk.MUTED,font=(self.font_family,12)).pack(fill='x',padx=20,pady=6)
        row=ttk.Frame(page);row.pack(fill='x',padx=16)
        self.button(row,'hide_selected',lambda:self.request_batch(True))
        self.button(row,'show_selected',lambda:self.request_batch(False))
        self.button(page,'apply',lambda:self.request_batch(None),side='top',fill='x',padx=20,pady=(4,12))
        steps=ttk.Frame(page);steps.pack(fill='x',padx=16,pady=(0,12))
        for number,title in (('01','Choose folders'),('02','Verify owner'),('03','Apply visibility')):
            card=ttk.Card(steps,soft=True);card.pack(side='left',fill='x',expand=True,padx=4)
            ttk.Label(card,text=number,text_color=ttk.ACCENT,font=(self.font_family,16,'bold'),height=22).pack(side='left',padx=(12,8),pady=8)
            ttk.Label(card,text=title,font=(self.font_family,12,'bold')).pack(side='left',padx=(0,12))
        # Reserve the action rows; only the folder table grows with the window.
        layouts=[(widget,widget.pack_info()) for widget in page.pack_slaves()]
        for widget,_ in layouts:widget.pack_forget()
        for index,(widget,layout) in enumerate(layouts):
            widget.grid(row=index,column=0,sticky='nsew' if widget is table else 'ew',
                        padx=layout.get('padx',0),pady=layout.get('pady',0))
            page.grid_rowconfigure(index,weight=1 if widget is table else 0)
        page.grid_columnconfigure(0,weight=1)

    def build_admin(self):
        page=self.pages['admin']
        ttk.section(page,'Admin & face profiles','Register faces and manage your administrator.','user')
        self.admin_banner=tk.StringVar()
        banner=ttk.Card(page,soft=True);banner.pack(fill='x',padx=16,pady=(0,8))
        ttk.Paragraph(banner,textvariable=self.admin_banner,line_width=580).pack(fill='x',padx=16,pady=12)
        row=ttk.Frame(page);row.pack(fill='x',padx=16)
        self.button(row,'enter_admin',self.enter_admin)
        self.button(row,'lock_admin',self.lock_admin)
        self.admin_form=ttk.Card(page);self.admin_form.pack(fill='x',padx=16,pady=10)
        self.name=tk.StringVar(value=self.state['owner'])
        ttk.Label(self.admin_form,text=self.t('name'),font=(self.font_family,13,'bold')).pack(anchor='w',padx=16,pady=(12,0))
        self.name_entry=ttk.Entry(self.admin_form,textvariable=self.name);self.name_entry.pack(fill='x',padx=16,pady=6)
        self.button(self.admin_form,'register',self.enroll,side='top',fill='x',padx=16)
        ttk.Label(self.admin_form,text=self.t('people'),font=(self.font_family,13,'bold')).pack(anchor='w',padx=16,pady=4)
        self.person=tk.StringVar()
        self.people_box=ttk.Combobox(self.admin_form,textvariable=self.person,state='readonly');self.people_box.pack(fill='x',padx=16,pady=4)
        row=ttk.Frame(self.admin_form);row.pack(fill='x',padx=12)
        self.button(row,'rename',self.rename)
        self.button(row,'delete',self.delete)
        self.button(row,'set_owner',self.set_owner)
        self.button(self.admin_form,'import',self.import_people,side='top',fill='x',padx=16,pady=(4,12))
        self.owner_label=tk.StringVar()
        ttk.Label(page,textvariable=self.owner_label,text_color=ttk.ACCENT,font=(self.font_family,13,'bold')).pack(anchor='w',padx=20,pady=4)

    def build_settings(self):
        page=self.pages['settings']
        ttk.section(page,'Camera settings','Choose the webcam used by FaceLocker.','lock')
        card=ttk.Card(page,soft=True);card.pack(fill='x',padx=16,pady=12)
        page=ttk.Frame(card);page.pack(fill='x',padx=20,pady=20)
        ttk.Paragraph(page,text=self.raw('settings_hint'),line_width=590).pack(fill='x',pady=10)
        ttk.Label(page,text=self.t('camera_index')).pack(anchor='w')
        self.camera_index=tk.StringVar(value=str(self.state['camera_index']))
        ttk.Spinbox(page,from_=0,to=20,textvariable=self.camera_index,width=10).pack(anchor='w',pady=8)
        self.button(page,'save_settings',self.settings_save,side='top',anchor='w')

    def on_tab(self,_=None):
        if self.building: return
        page=self.notebook.index(self.notebook.select())
        if page!=1 and self.admin_unlocked:
            self.admin_unlocked=False
            if self.mode=='enroll': self.stop('cancelled')
            self.refresh_admin()

    def toggle_theme(self):
        self.require_idle()
        mode='dark' if self.theme=='light' else 'light'
        state=copy.deepcopy(self.state);state['theme']=mode;self.commit(state)
        self.theme=mode;ttk.appearance(mode,self.root);ttk.table_palette(self.tree)
        self.theme_button.configure(text=self.t('dark_theme' if mode=='light' else 'light_theme'))
        self.blank(self.canvas)

    def commit(self,state):
        save_state(ROOT,state)
        self.state=state

    def require_idle(self):
        if self.mode!='idle': raise ValueError(text('busy'))

    def require_admin(self):
        self.require_idle()
        if self.state['people'] and not self.admin_unlocked:
            raise ValueError(text('need_unlock'))

    def refresh_admin(self):
        unlocked=self.admin_unlocked or not self.state['people']
        self.admin_banner.set(self.raw('first_setup' if not self.state['people'] else 'admin_ready' if unlocked else 'admin_locked'))
        self.owner_label.set(self.t('owner_saved',name=self.state['owner']))
        names=sorted(self.state['people'])
        self.people_display={name:name for name in names}
        self.people_box.configure(values=list(self.people_display))
        if self.person.get() not in self.people_display:
            self.person.set(self.state['owner'] if self.state['owner'] in names else (names[0] if names else ''))
        for frame in (self.admin_form,*self.admin_form.winfo_children()):
            for child in frame.winfo_children():
                if isinstance(child,(ttk.Button,ttk.Entry,ttk.Combobox)):
                    child.configure(state='readonly' if unlocked and isinstance(child,ttk.Combobox) else 'normal' if unlocked else 'disabled')
        self.name_entry.configure(state='normal' if unlocked else 'disabled')
        self.people_box.configure(state='readonly' if unlocked else 'disabled')

    def browse(self):
        self.require_idle()
        path=filedialog.askdirectory(title=self.t('browse'),mustexist=True)
        if path: self.add_folder(path)

    def add_default(self):
        self.require_idle()
        path=ROOT.parent/'Locker'
        path.mkdir(exist_ok=True)  # Creation is explicit; adding does not hide it.
        self.add_folder(str(path))

    def add_folder(self,path):
        path=validate_folder(path,ROOT)
        if os.path.normcase(path) in {os.path.normcase(p) for p in self.state['folders']}:
            self.checked.add(path);self.refresh_folders();return
        state=copy.deepcopy(self.state);state['folders'].append(path);self.commit(state)
        self.desired[path]=True;self.checked.add(path);self.refresh_folders()

    def refresh_folders(self):
        ttk.table_palette(self.tree)
        self.tree.delete(*self.tree.get_children());self.rows={}
        for i,path in enumerate(self.state['folders']):
            try: current=self.t('hidden' if Folder(path).hidden else 'visible')
            except Exception: current=self.t('missing')
            iid=str(i);self.rows[iid]=path
            self.tree.insert('', 'end',iid=iid,tags=('even' if i%2==0 else 'odd',),values=('☑' if path in self.checked else '☐',Path(path).name,path,current,self.t('hidden' if self.desired.get(path,True) else 'visible')))

    def tree_click(self,event):
        if self.mode!='idle': return 'break'
        row=self.tree.identify_row(event.y);column=self.tree.identify_column(event.x)
        if row in self.rows and column in ('#1','#5'):
            path=self.rows[row]
            if column=='#1':
                self.checked.symmetric_difference_update({path})
            else: self.desired[path]=not self.desired.get(path,True)
            self.refresh_folders();return 'break'

    def select_all(self):
        self.require_idle();self.checked=set(self.state['folders']);self.refresh_folders()

    def select_none(self):
        self.require_idle();self.checked.clear();self.refresh_folders()

    def remove_folders(self):
        self.require_idle()
        paths=self.checked or {self.rows[r] for r in self.tree.selection()}
        state=copy.deepcopy(self.state);state['folders']=[p for p in state['folders'] if p not in paths]
        self.commit(state);self.checked.difference_update(paths);self.refresh_folders()

    def request_batch(self,hidden):
        self.require_idle()
        if not self.checked: raise ValueError(text('choose_folders'))
        jobs=[(p,self.desired.get(p,True) if hidden is None else hidden) for p in self.state['folders'] if p in self.checked]
        jobs=prepare_jobs(jobs,ROOT)
        self.verify('folders',jobs)

    def enter_admin(self):
        self.require_idle()
        if not self.state['people']:
            self.admin_unlocked=True;self.refresh_admin();return
        self.verify('admin')

    def lock_admin(self):
        self.stop('cancelled');self.admin_unlocked=False;self.refresh_admin()

    def start_camera(self,mode):
        self.require_idle()
        self.notify('starting')
        if self.pipeline is None: self.pipeline=Pipeline(ROOT/'models')
        self.pipeline.start(self.state['camera_index']);self.mode=mode

    def verify(self,purpose,jobs=()):
        if self.state['owner'] not in self.state['people']: raise ValueError(text('need_admin'))
        self.start_camera('verify')
        self.pending=VerifiedAction(self.state['owner'],time.monotonic(),jobs,purpose)
        self.notify('unchanged')

    def stop(self,key='camera_off',**values):
        if isinstance(self.pending,VerifiedAction): self.pending.cancel()
        self.pending=None;self.mode='idle'
        if self.pipeline is not None: self.pipeline.stop()
        self.blank(self.canvas);self.notify(key,**values)

    def blank(self,canvas):
        ttk.video_image(canvas);canvas.create_text(200,150,text=self.t('camera_off'),fill='#a0d8bf',font=(self.font_family,16,'bold'))
        self.photo=None

    def preview(self):
        self.start_camera('preview');self.notify('preview_hint')

    def enroll(self):
        self.require_admin();name=valid_name(self.name.get())
        if name in self.state['people'] and not messagebox.askyesno(self.t('confirm'),self.t('replace_confirm',name=name)):
            return
        self.start_camera('enroll')
        self.pending={'name':name,'samples':[],'anchor':None,'last':0,'bootstrap':not bool(self.state['people'])}
        self.notify('single_face')

    def rename(self):
        self.require_admin()
        state=renamed_state(self.state,self.people_display.get(self.person.get(),self.person.get()),self.name.get())
        self.commit(state);self.refresh_admin();self.notify('renamed',name=valid_name(self.name.get()))

    def delete(self):
        self.require_admin();name=self.people_display.get(self.person.get(),self.person.get())
        if name==self.state['owner']: raise ValueError(text('cannot_delete_owner'))
        if name in self.state['people'] and messagebox.askyesno(self.t('confirm'),self.t('delete_confirm',name=name)):
            state=copy.deepcopy(self.state);del state['people'][name];self.commit(state);self.refresh_admin()

    def set_owner(self):
        self.require_admin();name=self.people_display.get(self.person.get(),self.person.get())
        if name not in self.state['people']: raise ValueError(text('need_admin'))
        state=copy.deepcopy(self.state);state['owner']=name;self.commit(state);self.refresh_admin();self.notify('owner_saved',name=name)

    def import_people(self):
        self.require_admin()
        path=filedialog.askopenfilename(title=self.t('import'),filetypes=[('JSON','*.json')])
        if not path: return
        people=read_people(path)
        if not people: raise ValueError(text('empty_import'))
        duplicates=set(people)&set(self.state['people'])
        if duplicates and not messagebox.askyesno(self.t('confirm'),self.t('duplicate_confirm',count=len(duplicates))): return
        state=copy.deepcopy(self.state);bootstrap=not bool(state['people']);state['people'].update(people)
        if bootstrap:
            state['owner']=state['owner'] if state['owner'] in people else sorted(people)[0]
        self.commit(state);self.admin_unlocked=False;self.refresh_admin();self.notify('imported',count=len(people))

    def settings_save(self):
        self.require_idle()
        state=copy.deepcopy(self.state);state['camera_index']=int(self.camera_index.get());validate_settings(state)
        if not self.state['people']:
            self.commit(state);self.notify('saved');return
        self.verify('settings')
        self.pending.camera_index=state['camera_index']

    def collect(self,faces,now):
        enrollment=self.pending
        if len(faces)!=1 or faces[0][1] is None: self.notify('single_face');return
        vector=faces[0][1]
        if enrollment['anchor'] is not None and float(enrollment['anchor']@vector)<0.363:
            self.notify('face_changed');return
        if now-enrollment['last']<0.5: return
        if enrollment['anchor'] is None: enrollment['anchor']=vector.copy()
        enrollment['last']=now;enrollment['samples'].append(vector.tolist())
        self.notify('enrolling',name=enrollment['name'],count=len(enrollment['samples']),total=self.state['samples'])
        if len(enrollment['samples'])>=self.state['samples']:
            state=copy.deepcopy(self.state);state['people'][enrollment['name']]=enrollment['samples']
            if enrollment['bootstrap']: state['owner']=enrollment['name']
            self.commit(state);self.stop('registered',name=enrollment['name'])
            if enrollment['bootstrap']: self.admin_unlocked=False
            self.refresh_admin()

    def render(self,frame,faces,matches):
        rgb=cv2.cvtColor(cv2.resize(frame,(400,300)),cv2.COLOR_BGR2RGB)
        canvas=self.canvas
        ttk.video_image(canvas,rgb)
        for (box,_),(name,score) in zip(faces,matches):
            x,y,w,h=[int(v*400/640) for v in box]
            color='#60e3a2' if name in self.state['people'] else '#ff8d7e'
            label=self.t('unknown') if name=='Unknown' else self.t('closer') if name=='Move closer' else name
            canvas.create_rectangle(x,y,x+w,y+h,outline=color,width=2)
            canvas.create_text(x,max(12,y-12),text=f'{label} | {score:.2f}',anchor='w',fill=color,font=(self.font_family,11,'bold'))

    def tick(self):
        if self.closed: return
        try:
            if self.mode!='idle':
                now=time.monotonic()
                if self.mode=='verify' and self.pending.gate.expired(now): self.stop('timeout')
                else:
                    frame,faces=self.pipeline.read()
                    matches=[('Move closer',0) if feature is None else identify(feature,self.state['people'],self.state['threshold'],self.state['margin']) for _,feature in faces]
                    self.render(frame,faces,matches)
                    if self.mode=='enroll': self.collect(faces,time.monotonic())
                    elif self.mode=='verify':
                        action=self.pending
                        approved=action.consume(matches[0][0] if len(matches)==1 else 'Unknown',len(faces),time.monotonic())
                        self.notify('verifying',owner=action.owner,count=action.gate.count,seconds=max(0,int(30-(now-action.gate.started))))
                        if approved:
                            if action.purpose=='admin':
                                self.stop('admin_ready');self.admin_unlocked=True;self.notebook.select(1);self.refresh_admin()
                            elif action.purpose=='settings':
                                state=copy.deepcopy(self.state);state['camera_index']=action.camera_index
                                self.commit(state);self.stop('saved')
                            else:
                                # Revalidate the immutable jobs immediately before execution.
                                jobs=prepare_jobs(action.jobs,ROOT)
                                outcomes=apply_batch(jobs)
                                failed=[(path,error) for path,ok,error in outcomes if not ok]
                                self.stop('summary',success=len(outcomes)-len(failed),failed=len(failed));self.refresh_folders()
                                if failed:
                                    detail='\n'.join(f'{p}: {error}' for p,error in failed)
                                    messagebox.showerror(self.t('error'),detail,parent=self.root)
        except Exception as exc:
            self.stop('cancelled');messagebox.showerror(self.t('error'),self.t('error_msg',detail=str(exc)),parent=self.root)
        if not self.closed: self.root.after(120,self.tick)

    def close(self):
        if isinstance(self.pending,VerifiedAction): self.pending.cancel()
        print("[startup] Close requested",flush=True)
        self.closed=True
        if self.pipeline is not None: self.pipeline.stop()
        self.root.destroy()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--setup',action='store_true');args=parser.parse_args()
    if args.setup: download_models(ROOT/'models');return
    print("[startup] Creating main window",flush=True)
    root=ctk.CTk();mutex=None
    print("[startup] Main window created",flush=True)
    try:
        if os.name!='nt': raise RuntimeError('Use Windows 11 to run FaceLocker.')
        api=ctypes.WinDLL('kernel32',use_last_error=True)
        api.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p];api.CreateMutexW.restype=ctypes.c_void_p
        api.CloseHandle.argtypes=[ctypes.c_void_p];api.CloseHandle.restype=ctypes.c_int
        ctypes.set_last_error(0);mutex=api.CreateMutexW(None,False,'Local\\FaceLockerDesktop_v1');error=ctypes.get_last_error()
        if not mutex: raise ctypes.WinError(error)
        if error==183:
            if not activate_existing():messagebox.showinfo('FaceLocker',text('already_running'))
            report_ready();root.destroy();return
        print("[startup] Building interface",flush=True)
        App(root);show_and_confirm(root,report_ready)
        print("[startup] Entering window loop",flush=True)
        root.mainloop()
        print("[startup] Window loop returned",flush=True)
    except Exception as exc:
        traceback.print_exc()
        messagebox.showerror('FaceLocker',str(exc),parent=root);root.destroy();raise
    finally:
        if mutex: api.CloseHandle(mutex)

if __name__=='__main__': main()
