import json,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from publishing_v2.autopilot.sources import Sources
from publishing_v2.autopilot.credits import _layout
Path('docs/audits/2026-09-20-multisource').mkdir(parents=True, exist_ok=True)
queries=['Diego Simeone','Jeddah','iPhone','Saudi coffee','Date palm']
def probe(query):
 source=Sources(recovery=True);start=time.monotonic()
 rows=source.subject_images(query,query)
 for row in rows:
  try:_layout({'cards':[{'image':row}]});row['credits_layout_pass']=True
  except Exception as e:row['credits_layout_error']=str(e)
 result={'query':query,'seconds':round(time.monotonic()-start,2),'paid_ai_calls':0,
         'download_verified':len(rows),'rows':rows,'diagnostics':source.image_diagnostics}
 Path('docs/audits/2026-09-20-multisource/'+query.lower().replace(' ','-')+'.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
 return query,len(rows),[r['provider'] for r in rows]
with ThreadPoolExecutor(max_workers=3) as ex:
 for f in as_completed([ex.submit(probe,q) for q in queries]):print('RESULT',f.result(),flush=True)
