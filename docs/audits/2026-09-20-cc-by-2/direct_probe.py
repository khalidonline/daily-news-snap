from publishing_v2.public_images import search_commons
from publishing_v2.autopilot.credits import attribution_eligible
import json
open('/tmp/direct-images.jsonl', 'w').close()
for name in ['Jose Mourinho','Diego Simeone']:
 for offset in (0,5,10):
  try:
   rows=search_commons(name,offset=offset)
   print(name,offset,[(r['asset_id'],r['license'],attribution_eligible(r)) for r in rows],flush=True)
   with open('/tmp/direct-images.jsonl','a') as f:
    for r in rows:f.write(json.dumps(r)+'\n')
  except Exception as e:print(type(e).__name__,str(e),flush=True)
