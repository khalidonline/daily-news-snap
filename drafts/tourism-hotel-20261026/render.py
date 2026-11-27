from pathlib import Path
import subprocess
P=Path(__file__).resolve().parent
ROOT=P.parents[1]
def run(args):
    subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',*args],check=True)
# Numeric color LUT for graphic layer only. Real photograph composited afterwards.
lut=P/'brand.cube'
with lut.open('w') as f:
    f.write('LUT_3D_SIZE 32\n')
    for b in range(32):
      for g in range(32):
       for r in range(32):
        R,G,B=[v*255/31 for v in (r,g,b)]
        out=(R,G,B)
        if R>235 and B>220 and G<R-8 and B>G-2: out=(253,229,235)
        elif R>225 and G>225 and B>205: out=(247,247,235)
        elif R>100 and R>G*1.8 and R>B*1.3: out=(182,14,50)
        elif R<100 and G>R*1.4 and G>B*1.1: out=(12,95,70)
        elif R<100 and B>R*1.4 and B>G*1.1: out=(11,54,86)
        elif max(R,G,B)-min(R,G,B)<22 and 75<R<170: out=(122,121,115)
        f.write(' '.join(str(v/255) for v in out)+'\n')
mask="if(lte(pow(max(35-X,0)+max(X-(W-36),0),2)+pow(max(35-Y,0)+max(Y-(H-36),0),2),1225),255,0)"
for name in ['question','answer']:
    filt=(f'[0:v]scale=1080:1920,lut3d={lut}[card];'
      '[1:v]scale=976:540:force_original_aspect_ratio=increase,crop=976:540,format=rgba,'
      f"geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{mask}'[photo];"
      '[card][photo]overlay=52:391:format=auto,format=rgb24[out]')
    run(['-i',str(P/f'{name}-generated.png'),'-i',str(P/'hotel-official.jpg'),
         '-filter_complex_threads','1','-filter_complex',filt,'-map','[out]','-frames:v','1',str(P/f'{name}.png')])
# Use the approved master countdown pixels and original audio, unshifted.
ref=ROOT/'approved/wheels-video-20261025/challenge.mp4'
filt=("[0:v]fps=30,setsar=1[base];[1:v]crop=1080:380:0:1230[answer];"
      "[2:v]crop=150:130:465:1460,lut3d="+str(lut)+"[timer];"
      "[base][timer]overlay=465:1480:enable='gte(t,3)*lt(t,8)'[counted];"
      "[counted][answer]overlay=0:1230:enable='gte(t,8)'[out]")
run(['-loop','1','-i',str(P/'question.png'),'-loop','1','-i',str(P/'answer.png'),'-i',str(ref),
     '-filter_complex_threads','1','-filter_complex',filt,'-map','[out]','-map','2:a:0',
     '-t','12','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','copy',
     '-movflags','+faststart',str(P/'Hotel-Challenge-v2.mp4')])
for t in [0.5,3.5,4.5,5.5,6.5,7.5,8.5,11.5]:
    run(['-ss',str(t),'-i',str(P/'Hotel-Challenge-v2.mp4'),'-frames:v','1',str(P/f'frame-{t}.png')])
