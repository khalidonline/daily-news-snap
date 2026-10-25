// Deterministic output geometry/palette. Photos and smile are protected.
const sharp = require('sharp');
const fs = require('fs');
const crypto = require('crypto');
const src = process.argv[2], dest = process.argv[3];
if (!src || !dest) throw Error('input and output required');
(async()=>{
  const {data,info}=await sharp(src).resize(1080,1920,{fit:'fill'}).removeAlpha().raw().toBuffer({resolveWithObject:true});
  const colors={body:[11,54,86],red:[182,14,50],green:[12,95,70],background:[247,247,235],cta_background:[253,229,235],caption:[122,121,115]};
  const inside=(x,y,b)=>x>=b[0]&&x<b[2]&&y>=b[1]&&y<b[3];
  const protectedBoxes=[[68,373,558,869],[578,373,1013,869],[264,998,325,1055]];
  const totals={};
  for(let y=0;y<1920;y++)for(let x=0;x<1080;x++){
    const i=(y*1080+x)*3; const [r,g,b]=data.subarray(i,i+3);
    if(protectedBoxes.slice(0,2).some(b=>inside(x,y,b)))continue;
    if(inside(x,y,protectedBoxes[2]) && r>190 && g>100 && b<145)continue;
    let key;
    if(y>=879&&y<=925&&Math.max(r,g,b)-Math.min(r,g,b)<35&&r<215)key='caption';
    else if(r>g*1.35&&r>b*1.15&&r-g>35)key='red';
    else if(g>r*1.2&&g>b*1.08&&g-r>25)key='green';
    else if(b>r*1.2&&g>r*1.15&&b-r>25)key='body';
    else if(y>1690&&y<1825&&r>220&&r-g>8&&b>205)key='cta_background';
    else if(Math.min(r,g,b)>205)key='background';
    if(key){
      let alpha=1;
      if(key==='body'||key==='green')alpha=r<80?1:Math.min(1,(247-r)/(247-11));
      if(key==='red')alpha=g<70?1:Math.min(1,(247-g)/(247-14));
      if(key==='caption')alpha=r<170?1:Math.min(1,(247-r)/(247-122));
      const bg=y>1690&&y<1825?colors.cta_background:colors.background;
      data.set(colors[key].map((v,c)=>Math.round(v*alpha+bg[c]*(1-alpha))),i);
      totals[key]=(totals[key]||0)+1;
    }
  }
  await sharp(data,{raw:{width:1080,height:1920,channels:3}}).png().toFile(dest);
  const raw=fs.readFileSync(dest);
  console.log(JSON.stringify({dimensions:[1080,1920],sha256:crypto.createHash('sha256').update(raw).digest('hex'),palette:colors,remapped_pixels:totals,protected_boxes:protectedBoxes}));
})();
