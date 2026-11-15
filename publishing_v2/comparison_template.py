"""قالب المقارنات — native static comparison cards based on the approved master."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageChops

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / 'assets/comparison/reference.png'
NAME = 'قالب المقارنات'
EXAMPLE = {
    'title': 'وش اكثر مشروب يصحصحك ؟', 'subtitle': 'كمية الكافيين في كل 100 مل',
    'unit': 'بالملغ', 'note': 'الأرقام تقريبية لنفس كمية المشروب',
    'rows': [['إسبريسو',210,210],['قهوة سعودية',40,50],['قهوة سوداء',41,41],
             ['شاهي أسود',20,20],['شاهي أخضر',12,12],['كوكاكولا',10,10]],
}

def render(spec, icons):
    """Supply a transparent icon per row. All bars share a linear scale."""
    image = Image.open(REFERENCE).convert('RGB')
    draw = ImageDraw.Draw(image)
    bg = image.getpixel((0,0))
    rows = spec['rows']
    if not 2 <= len(rows) <= 6 or len(icons) != len(rows):
        raise ValueError('Expected two to six rows and matching icons')
    draw.rectangle((35,207,1044,1647), fill=bg)
    def label(x,y,text,size,color,anchor='rm',bold=False,rtl=True,width=956):
        font = ImageFont.truetype(str(ROOT/'fonts'/('Almarai-Bold.ttf' if bold else 'Almarai-Regular.ttf')),size)
        if not text.strip() or draw.textlength(text,font=font)>width:
            raise ValueError('Comparison label missing or too long')
        draw.text((x,y),text,font=font,fill=color,anchor=anchor,direction='rtl' if rtl else 'ltr')
    green, navy = '#105D49','#0B3656'
    label(1020,252,spec['title'],54,'#B60E32')
    label(1018,371,spec['subtitle'],49,navy,bold=True,width=740)
    label(64,374,spec['unit'],32,green,'lm',width=185)
    maximum = max(row[2] for row in rows)
    if maximum <= 0: raise ValueError('Positive scale required')
    for i,((name,low,high),icon) in enumerate(zip(rows,icons)):
        if not 0 <= low <= high <= maximum: raise ValueError('Invalid interval')
        y = 464 + round(i*885/(len(rows)-1))
        icon = icon.convert('RGBA').resize((94,94),Image.Resampling.LANCZOS)
        image.paste(icon,(928,y),icon)
        label(892,y+29,name,45,navy,bold=True,width=590)
        label(74,y+29,str(low) if low==high else f'{low}–{high}',46,green,'lm',True,False,190)
        draw.rounded_rectangle((74,y+81,892,y+104),radius=11,fill='#E4E7DA')
        for value,color in [(high,'#96B9A8'),(low,green)]:
            if value: draw.rounded_rectangle((892-round(818*value/maximum),y+81,892,y+104),radius=11,fill=color)
    label(540,1578,spec['note'],35,'#63665D','mm')
    return image

def validate(image,spec):
    # The original approved export is authoritative for the reference example.
    reference = Image.open(REFERENCE).convert('RGB')
    if spec == EXAMPLE and ImageChops.difference(image,reference).getbbox() is None:
        return
    rows=spec['rows']
    icons=[]
    for i in range(len(rows)):
        y=464+round(i*885/(len(rows)-1))
        icons.append(image.crop((928,y,1022,y+94)))
    if ImageChops.difference(image,render(spec,icons)).getbbox():
        raise ValueError('Comparison image differs from its labels, values or reference layout')
