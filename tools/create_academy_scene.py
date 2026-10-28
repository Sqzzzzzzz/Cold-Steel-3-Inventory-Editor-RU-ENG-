"""Procedural, original academy-city background. No proprietary game artwork is embedded.
Creates the intentionally defocused atmospheric background for the game-style HUD.
"""
from pathlib import Path
import random, math
from PIL import Image, ImageDraw, ImageFilter

W,H=1680,950
random.seed(41283)
im=Image.new('RGB',(W,H))
px=im.load()
for y in range(H):
    f=y/H
    for x in range(W):
        l=0.018*math.sin(x/150)+0.038*math.sin((x+y)/255)
        col=(int(80-40*f+36*l),int(131-70*f+48*l),int(162-86*f+40*l))
        px[x,y]=col
d=ImageDraw.Draw(im,'RGBA')
# Atmospheric mountains and far buildings.
d.polygon([(0,360),(160,315),(280,346),(430,275),(575,359),(770,291),(935,334),(1090,264),(1320,328),(1480,270),(1680,350),(1680,900),(0,900)],fill=(45,77,100,105))
for k in range(45):
    x=random.randrange(-20,W+20); ht=random.randrange(45,180); y=random.randrange(260,380)
    d.rectangle((x,y,x+random.randrange(16,44),y+ht), fill=(71,94,117,65))
# Academy main building, stone and turquoise shadow.
d.polygon([(295,355),(1350,355),(1350,746),(295,746)],fill=(167,163,149,205),outline=(218,212,189,155),width=7)
d.rectangle((310,418,1342,743),fill=(100,108,116,140))
d.rectangle((355,390,1285,734),fill=(159,160,153,130))
# Roof: sloping tile and ornaments
d.polygon([(266,371),(378,299),(1245,299),(1390,372)],fill=(65,85,111,205),outline=(212,215,212,190),width=7)
d.line((300,369,1360,369), fill=(237,229,207,180),width=8)
# Central hall bay + dome.
d.rectangle((670,275,1002,728), fill=(178,168,158,195),outline=(238,222,201,180),width=8)
d.polygon([(655,285),(836,178),(1025,285)],fill=(68,89,115,235),outline=(222,225,220,230),width=8)
d.ellipse((770,210,908,323),fill=(91,113,141,245),outline=(211,215,207,230),width=8)
d.line((840,166,840,210),fill=(216,210,191,230),width=7)
d.polygon([(829,177),(840,155),(852,177)],fill=(220,214,199,220))
# Side towers spires
for x in (265,1353):
    d.rectangle((x-49,228,x+50,684),fill=(153,160,164,205),outline=(209,214,212,200),width=6)
    d.polygon([(x-67,245),(x,103),(x+66,245)],fill=(68,91,115,240),outline=(214,217,210,215),width=7)
    d.line((x,100,x,75),fill=(229,212,169,220),width=6)
    d.ellipse((x-8,67,x+8,83),fill=(240,222,174,245))
    for yy in (298,393,487):
        d.rounded_rectangle((x-26,yy,x+24,yy+55),radius=20,fill=(39,70,84,206),outline=(230,215,185,180),width=4)
# Academy windows
for x0,x1,y0,nx,ny in [(360,630,432,5,4),(1055,1300,432,5,4),(720,960,360,4,5)]:
    for row in range(ny):
        for col in range(nx):
            x=x0+col*(x1-x0)//max(nx,1); y=y0+row*79
            d.rounded_rectangle((x,y,x+31,y+53),radius=12,fill=(27,53,67,230),outline=(222,210,190,175),width=3)
            d.line((x+16,y+5,x+16,y+50),fill=(152,169,167,120),width=2)
# Balustrade and courtyard
for y in (705,753): d.line((100,y,1600,y),fill=(215,201,181,170),width=8)
d.rectangle((0,770,W,H),fill=(55,86,97,200))
d.polygon([(660,776),(1020,776),(1535,H),(120,H)],fill=(137,130,119,205))
for i in range(11):
    x=160+i*132
    d.ellipse((x-9,737,x+9,761),fill=(207,202,178,205))
    d.rectangle((x-9,755,x+9,817),fill=(208,203,186,178))
# Banners hanging in the center
for x in (570,1090):
    d.rectangle((x-35,346,x+35,533),fill=(131,42,62,223),outline=(229,199,143,218),width=4)
    d.polygon([(x-35,530),(x,559),(x+35,530)],fill=(131,42,62,223),outline=(223,184,123,200))
    d.ellipse((x-13,402,x+13,437),outline=(230,204,139,224),width=4)
# Side trees soft leaf clusters
for cx,base,scale in [(146,755,1.05),(1510,759,1.2),(1190,760,0.68),(510,740,0.65)]:
    d.polygon([(cx-17,base),(cx+20,base),(cx+16,base-200*scale),(cx-10,base-180*scale)],fill=(58,62,63,200))
    for j in range(28):
        rx=cx+random.randrange(-78,79)*scale; ry=base-random.randrange(150,365)*scale
        r=random.randrange(26,78)*scale
        d.ellipse((rx-r,ry-r*.68,rx+r,ry+r*.7),fill=random.choice([(41,82,71,175),(61,100,79,177),(79,113,88,177),(38,75,77,170)]))
# Gentle bright bokeh
for i in range(26):
    x=random.randrange(W); y=random.randrange(180,750); r=random.randrange(4,13)
    d.ellipse((x-r,y-r,x+r,y+r),fill=(244,218,169,random.randrange(30,75)))
im=im.filter(ImageFilter.GaussianBlur(9))
# Cinematic midnight blue film over the painted city, brighter at upper center.
blue=Image.new('RGBA',(W,H),(5,32,54,92))
im=Image.alpha_composite(im.convert('RGBA'),blue)
# Soft vignette
vign=Image.new('RGBA',(W,H),(0,0,0,0)); vd=ImageDraw.Draw(vign,'RGBA')
for j in range(14):
    a=int(4+1.5*j)
    vd.rounded_rectangle((j*16,j*11,W-j*16,H-j*11),radius=90,outline=(0,20,39,a),width=24)
im=Image.alpha_composite(im,vign).convert('RGB')
# A broad vertical ornamental stripe on the left, behind the nav.
orn=Image.new('RGBA',(W,H),(0,0,0,0)); od=ImageDraw.Draw(orn,'RGBA')
for x in (58,69,84):
    od.arc((x-25,-150,x+270,1160),90,270,fill=(188,224,236,136 if x!=73 else 205),width=8 if x==73 else 4)
od.polygon([(0,0),(90,0),(44,H),(0,H)],fill=(3,35,61,120))
for y in range(12,H-12,36):
    for x in ([24,65,105,160,1630,1668] if y%72 else [2,45,85,145,1590,1640]):
        pts=[]
        for i in range(6):
            a=(math.pi/3)*i
            pts.append((x+16*math.cos(a),y+16*math.sin(a)))
        od.line(pts+[pts[0]],fill=(79,197,242,49),width=1)
# Silver-blue curved rails, inspired by the vertical chrome trim in JRPG menus.
for offset,color,width in [(0,(233,248,253,180),4),(-7,(17,36,50,190),8),(7,(92,191,216,120),3)]:
    coords=[]
    for y in range(-30,H+35,5):
        x=86+math.sin((y+120)/290)*43+offset
        coords.append((int(x),y))
    od.line(coords,fill=color,width=width,joint='curve')
im=Image.alpha_composite(im.convert('RGBA'),orn)
path=Path(__file__).resolve().parents[1]/'assets'/'academy_hud_background.jpg'
path.parent.mkdir(exist_ok=True)
im.convert('RGB').save(path,quality=87,optimize=True)
print(path)
