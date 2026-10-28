"""Lightweight, original GUI art for the Cold Steel-inspired Tk HUD.
All effects are pre-rendered with Pillow and cached; no animations or redraws
of the Treeview on mouse motion. No original game imagery is redistributed.
"""
from PIL import Image, ImageDraw, ImageFilter


def strip(base: Image.Image, width: int, height: int, y: int, *, darkness: int=115, bottom=True):
    """Real background scenery behind semi-transparent tinted UI glass."""
    if width < 1 or height < 1:
        return Image.new('RGBA',(1,1),(9,42,67))
    base=base.convert('RGB').resize((width,max(1,int(width*base.height/base.width))))
    if base.height < y+height:
        base=base.resize((width,y+height))
    img=base.crop((0,y,width,y+height)).convert('RGBA')
    tint=Image.new('RGBA',img.size,(4,25,47,darkness))
    img=Image.alpha_composite(img,tint)
    over=Image.new('RGBA',img.size,(0,0,0,0)); d=ImageDraw.Draw(over,'RGBA')
    d.line((0,0,width,0),fill=(69,150,178,90),width=1)
    if bottom:
        d.line((0,height-3,width,height-3),fill=(10,61,94,205),width=3)
        d.line((0,height-2,width,height-2),fill=(85,215,245,125),width=1)
    d.line((0,0,0,height),fill=(28,129,176,55),width=1)
    return Image.alpha_composite(img,over)


def bevel_corner(canvas,side,*,accent='#55DBF6',base='#092F4B'):
    """Small angular bevels with subtle cyan inner glows, four canvas corners."""
    canvas.configure(width=22,height=22,bg=base,highlightthickness=0,borderwidth=0)
    if side=='tl':
        a=((0,21),(0,6),(6,0),(21,0)); b=((2,20),(2,7),(7,2),(21,2))
    elif side=='tr':
        a=((0,0),(15,0),(21,6),(21,21)); b=((0,2),(14,2),(19,7),(19,21))
    elif side=='bl':
        a=((0,0),(0,15),(6,21),(21,21)); b=((2,0),(2,14),(7,19),(21,19))
    else:
        a=((0,21),(15,21),(21,15),(21,0)); b=((0,19),(14,19),(19,14),(19,0))
    canvas.create_line(*sum(([p[0],p[1]] for p in a),[]),fill=accent,width=2)
    canvas.create_line(*sum(([p[0],p[1]] for p in b),[]),fill='#2585B6',width=1)


def attach_corners(frame,bg='#092F4B'):
    import tkinter as tk
    placements={'tl':(0,0,'nw'),'tr':(1,0,'ne'),'bl':(0,1,'sw'),'br':(1,1,'se')}
    corners=[]
    for side,(x,y,anchor) in placements.items():
        cv=tk.Canvas(frame)
        bevel_corner(cv,side,base=bg)
        cv.place(relx=x,rely=y,anchor=anchor)
        corners.append(cv)
    return corners


class HUDTab:
    """Angular Tk canvas tab: real clickable control with hover/focus, no fake art."""
    def __init__(self,parent,text,command,width=204):
        import tkinter as tk
        self.canvas=tk.Canvas(parent,width=width,height=48,bd=0,highlightthickness=0,
                              bg='#07324C',cursor='hand2',takefocus=1)
        self.text=text;self.command=command;self.active=False;self.hover=False
        self.canvas.bind('<Button-1>',lambda e:self.command())
        self.canvas.bind('<Enter>',lambda e:(setattr(self,'hover',True),self._draw()))
        self.canvas.bind('<Leave>',lambda e:(setattr(self,'hover',False),self._draw()))
        self.canvas.bind('<space>',lambda e:self.command())
        self.canvas.bind('<Return>',lambda e:self.command())
        self._draw()
    def pack(self,**kwargs):return self.canvas.pack(**kwargs)
    def winfo_manager(self):return self.canvas.winfo_manager()
    def set_active(self,value):self.active=bool(value);self._draw()
    def set_text(self,value):self.text=value;self._draw()
    def _draw(self):
        c=self.canvas; c.delete('all')
        w=int(c.cget('width'));h=int(c.cget('height'))
        selected=self.active or self.hover
        pts=[2,4,w-31,4,w-3,h-4,21,h-4]
        c.create_polygon(pts,fill='#096397' if selected else '#0B354F',
                         outline='#5BDDFF' if selected else '#2E91B5',width=2)
        c.create_line(14,7,w-34,7,fill='#D0FDFF' if selected else '#8FBACD',width=1)
        c.create_line(w-34,7,w-7,h-8,fill='#7EE9FF' if selected else '#3E96AE',width=2)
        c.create_polygon((18,11,w-38,11,w-15,h-12,26,h-12),
                         fill='#128CD0' if self.active else '#0A4569',outline='')
        c.create_text(w//2,23,text=self.text,fill='#FFFFFF' if selected else '#C9E9F7',
                      font=('Segoe UI Semibold',11 if selected else 10))
