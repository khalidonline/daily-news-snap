from pathlib import Path
import json
from PIL import Image, ImageDraw
from publishing_v2.fixed_information_template import render

p=Path('approved/us-midterms-20261101')
copy={
 'headline':'انتخابات أمريكا… والرئيس مو بالتصويت!',
 'bullets':[
 'الثلاثاء ٣ نوفمبر، أمريكا تنتخب الكونغرس، مو الرئيس. يسمونها «النصفية» لأنها بنص فترته.',
 'الكونغرس مجلسين: النواب والشيوخ. يقرون القوانين ويوافقون على الصرف؛ الرئيس مو لحاله.',
 'إذا حزب الرئيس أخذ أغلبية بالمجلسين، يسهل عليه تمرير خططه، بس الموافقة مو مضمونة.',
 'وإذا المعارضة أخذت مجلس واحد، تقدر توقف قوانينه؛ ويحتاج يتفاوض علشان يمشيها.'
 ],
 'closing':'الرئيس باقي… بس اللي يوافقون له ممكن يتغيرون!',
 'captions':['مبنى الكونغرس الأمريكي — Architect of the Capitol']}
im,blocks=render(copy['headline'],copy['bullets'],copy['closing'],[Image.open(p/'capitol.jpg')],copy['captions'])
im.save(p/'card.png')
(p/'copy.json').write_text(json.dumps(copy,ensure_ascii=False,indent=2)+'\n')
(p/'blocks.json').write_text(json.dumps(blocks,ensure_ascii=False,indent=2)+'\n')
mobile=im.resize((390,693))
for dest in ['story','saved-story']:
 overlay=mobile.copy();d=ImageDraw.Draw(overlay)
 d.rectangle((0,0,389,39),fill='#222222');d.rectangle((0,625,389,692),fill='#222222')
 overlay.save('/tmp/midterms-'+dest+'.png')
print([(b['role'],b['line_count']) for b in blocks])
