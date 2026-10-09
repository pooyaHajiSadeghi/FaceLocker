"""Rounded desktop widgets and shared light/dark palette."""
import tkinter as tk
from tkinter import ttk as native
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

BG=('#eef7f4','#0b1916')
CARD=('#ffffff','#142723')
TEXT=('#15372c','#e5f3ec')
MUTED=('#59736b','#a2beb2')
ACCENT=('#09865f','#16a779')
BORDER=('#d8eae3','#294b40')
SOFT=('#e9f5ef','#1b352d')
DANGER=('#b8444b','#ef9ca1')
ctk.set_default_color_theme('green')

def color(pair):return pair[1 if ctk.get_appearance_mode()=='Dark' else 0]

def appearance(mode,root):
    ctk.set_appearance_mode(mode)
    root.configure(fg_color=BG)
    style=native.Style(root);style.theme_use('clam')
    style.configure('Treeview',font=('Segoe UI',11),rowheight=46,background=color(CARD),fieldbackground=color(CARD),foreground=color(TEXT),borderwidth=0,relief='flat')
    style.configure('Treeview.Heading',font=('Segoe UI',11,'bold'),background=color(SOFT),foreground=color(MUTED),borderwidth=0,padding=(8,16),relief='flat')
    style.layout('Treeview',[('Treeview.padding',{'sticky':'nswe','children':[('Treeview.treearea',{'sticky':'nswe'})]})])
    style.map('Treeview',background=[('selected',color(ACCENT))],foreground=[('selected','#ffffff')])
    style.map('Treeview.Heading',background=[('active',color(BG))])

class Frame(ctk.CTkFrame):
    def __init__(self,parent,padding=0,**kwargs):
        super().__init__(parent,corner_radius=18,fg_color='transparent',**kwargs)

class Card(ctk.CTkFrame):
    def __init__(self,parent,soft=False,**kwargs):
        super().__init__(parent,corner_radius=20,fg_color=SOFT if soft else CARD,
                         border_width=1,border_color=BORDER,**kwargs)

class Button(ctk.CTkButton):
    def __init__(self,parent,variant='primary',**kwargs):
        kwargs.setdefault('width',120)
        secondary=variant!='primary'
        kwargs.setdefault('fg_color',SOFT if secondary else ACCENT)
        kwargs.setdefault('text_color',DANGER if variant=='danger' else TEXT if secondary else '#ffffff')
        kwargs.setdefault('hover_color',('#d8ede3','#254c3e') if secondary else ('#06704f','#138a64'))
        kwargs.setdefault('border_width',1 if secondary else 0)
        kwargs.setdefault('border_color',BORDER)
        kwargs.setdefault('font',('Segoe UI',13,'bold'))
        super().__init__(parent,corner_radius=12,height=40,**kwargs)


def icon(kind,size=24):
    """Small scalable line icons: generated locally, with light/dark colors."""
    def draw(ink):
        im=Image.new('RGBA',(96,96));d=ImageDraw.Draw(im);w=6
        if kind=='folder':
            d.rounded_rectangle((12,28,84,78),radius=9,outline=ink,width=w)
            d.line((14,28,14,19,39,19,48,28),fill=ink,width=w)
        elif kind=='user':
            d.ellipse((33,13,63,43),outline=ink,width=w)
            d.arc((17,46,79,96),180,360,fill=ink,width=w)
        elif kind=='eye':
            d.arc((10,21,86,79),180,360,fill=ink,width=w)
            d.arc((10,17,86,75),0,180,fill=ink,width=w)
            d.ellipse((37,36,59,58),outline=ink,width=w)
        else:
            for x,y,dx,dy in ((13,13,1,1),(83,13,-1,1),(13,83,1,-1),(83,83,-1,-1)):
                d.line((x,y+16*dy,x,y,x+16*dx,y),fill=ink,width=w)
            d.arc((33,24,63,60),180,360,fill=ink,width=w)
            d.rounded_rectangle((27,44,69,74),radius=6,outline=ink,width=w)
            d.ellipse((44,53,52,61),fill=ink)
        return im
    return ctk.CTkImage(draw('#09865f'),draw('#7ce2b6'),size=(size,size))


def section(parent,title,subtitle,kind='folder'):
    row=Frame(parent);row.pack(fill='x',padx=16,pady=(10,8))
    ctk.CTkLabel(row,text='',image=icon(kind,30),width=44).pack(side='left',padx=(0,10))
    words=Frame(row);words.pack(side='left',fill='x',expand=True)
    Label(words,text=title,font=('Segoe UI',21,'bold'),height=24,anchor='w').pack(fill='x')
    Label(words,text=subtitle,text_color=MUTED,font=('Segoe UI',12),height=20,anchor='w').pack(fill='x')


def table_palette(tree):
    tree.tag_configure('even',background=color(CARD),foreground=color(TEXT))
    tree.tag_configure('odd',background=color(SOFT),foreground=color(TEXT))

class Label(ctk.CTkLabel):
    def __init__(self,parent,**kwargs):
        kwargs.setdefault('font',('Segoe UI',13))
        kwargs.setdefault('text_color',TEXT)
        super().__init__(parent,**kwargs)

class Paragraph(Label):
    """English paragraph with native Tk word wrapping."""
    def __init__(self,parent,line_width=480,**kwargs):
        kwargs.setdefault('justify','left')
        kwargs.setdefault('anchor','w')
        super().__init__(parent,wraplength=line_width,**kwargs)

class Entry(ctk.CTkEntry):
    def __init__(self,parent,**kwargs):
        super().__init__(parent,corner_radius=12,height=40,fg_color=CARD,border_color=BORDER,text_color=TEXT,**kwargs)

class Combobox(ctk.CTkComboBox):
    def __init__(self,parent,textvariable=None,**kwargs):
        super().__init__(parent,variable=textvariable,corner_radius=12,height=40,fg_color=CARD,border_color=BORDER,text_color=TEXT,dropdown_fg_color=CARD,dropdown_text_color=TEXT,button_color=SOFT,button_hover_color=BORDER,**kwargs)
    def __setitem__(self,key,value):self.configure(**{key:value})

class Spinbox(Entry):
    def __init__(self,parent,from_=0,to=20,width=100,**kwargs):
        super().__init__(parent,width=100,**kwargs)

class Scrollbar(ctk.CTkScrollbar):
    def __init__(self,parent,orient='vertical',**kwargs):
        super().__init__(parent,orientation=orient,corner_radius=8,button_color=BORDER,button_hover_color=ACCENT,**kwargs)

class Notebook(ctk.CTkTabview):
    def __init__(self,parent):
        self.names=[];self.callback=None
        super().__init__(parent,corner_radius=20,fg_color=CARD,border_width=1,border_color=BORDER,
                         segmented_button_fg_color=BG,segmented_button_selected_color=ACCENT,
                         segmented_button_unselected_color=SOFT,text_color=TEXT,command=self.changed,
                         segmented_button_selected_hover_color=('#06704f','#138a64'))
        self._segmented_button.configure(font=('Segoe UI',13,'bold'),height=38,corner_radius=12)
    def add(self,name):
        self.names.append(name)
        return super().add(name)
    def select(self,page=None):
        if page is None:return self.get()
        self.set(self.names[page] if isinstance(page,int) else page)
        self.after_idle(self.changed)
    def index(self,name):return self.names.index(name)
    def bind(self,event,callback,add=None):
        if event=='<<NotebookTabChanged>>':self.callback=callback
        else:super().bind(event,callback,add)
    def changed(self):
        if self.callback:self.callback(None)

class Progressbar(ctk.CTkProgressBar):
    def __init__(self,parent,mode='indeterminate'):
        super().__init__(parent,mode=mode,corner_radius=8,progress_color=ACCENT)
    def start(self,interval=None):super().start()

Treeview=native.Treeview

def video_image(canvas,rgb=None):
    background=Image.new('RGB',(400,300),color(CARD))
    frame=Image.fromarray(rgb) if rgb is not None else Image.new('RGB',(400,300),'#122b24')
    mask=Image.new('L',(400,300));ImageDraw.Draw(mask).rounded_rectangle((0,0,399,299),radius=20,fill=255)
    background.paste(frame,(0,0),mask)
    canvas.configure(bg=color(CARD))
    canvas.photo=ImageTk.PhotoImage(background,master=canvas)
    canvas.delete('all');canvas.create_image(0,0,anchor='nw',image=canvas.photo)
