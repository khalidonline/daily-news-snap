"""One-off native video composition; no paid generation or publishing."""
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[2]
dest = Path(__file__).resolve().parent
font = root/'fonts/Cairo-Bold.ttf'
source = root/'approved/wheels-balanced-20261025/card.png'
audio = dest/'approved-audio.mp4'
filters = []
for i, digit in enumerate('٥٤٣٢١'):
    filters.append(f"drawtext=fontfile='{font}':text='{digit}':fontsize=92:fontcolor=0xB60E32:x=(w-tw)/2:y=112:enable='gte(t,{3+i})*lt(t,{4+i})'")
filters += [
    "drawbox=x=65:y=1225:w=456:h=135:color=0x0C5F46:t=7:enable='gte(t,8)'",
    "drawbox=x=70:y=1380:w=940:h=80:color=0xF7F7EB:t=fill:enable='gte(t,8)'",
]
subprocess.run(['ffmpeg','-v','error','-y','-loop','1','-framerate','30','-i',str(source),
    '-i',str(audio),'-map','0:v:0','-map','1:a:0','-vf',','.join(filters),
    '-t','12','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p',
    '-c:a','copy','-movflags','+faststart',str(dest/'challenge.mp4')],check=True)
for at in [.5,3.5,4.5,5.5,6.5,7.5,8.5,11.5]:
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(at),'-i',str(dest/'challenge.mp4'),
        '-frames:v','1','-threads','1',str(dest/f'frame-{at}.png')],check=True)
