"""Read-only Snapchat aggregate collection. Missing/stale metrics are not zero.
No publishing, refresh/force calls, model requests or scheduling.
"""
import argparse,json,math,urllib.parse
from datetime import datetime,timezone
from pathlib import Path
FIELDS=('views','viewsUnique','impressions','impressionsUnique','shares','saves','likes','comments','followers')
def timestamp(value):
 d=datetime.fromisoformat(value.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('timezone_required')
 return d

def assess(rows,now,*,placement,max_age_hours=24):
 if placement not in ('STORY','SAVED_STORY','SPOTLIGHT','PROFILE'):raise ValueError('placement_required')
 out={'placement':placement,'observed_at':now.isoformat(),'usable':False,'status':'unavailable','values':{k:None for k in FIELDS},'note':'Provider-reported snapshot, not independent verification. Never sum unique viewers across placements.'}
 if not rows:return out
 try:
  dated=[(timestamp(r['updatedAt']),r) for r in rows]
  updated,row=max(dated,key=lambda p:p[0]);created=timestamp(row['createdAt'])
  if not created<=updated<=now:raise ValueError('timestamp_order')
 except (KeyError,TypeError,ValueError,AttributeError):return dict(out,status='invalid_timestamp')
 values={k:row.get(k) for k in FIELDS}
 if any(v is not None and (type(v) not in (int,float) or not math.isfinite(v) or v<0) for v in values.values()):return dict(out,status='invalid_value')
 out.update(values=values,provider_updated_at=updated.isoformat(),age_hours=(now-updated).total_seconds()/3600)
 if out['age_hours']>max_age_hours:return dict(out,status='stale')
 present=[v for v in values.values() if v is not None]
 if not present:return out
 if not any(present) and updated==created:return dict(out,status='unverified_zero')
 return dict(out,status='reported',usable=True)

def collect(client,targets,now):
 if len(targets)>60 or len({t['post_id'] for t in targets})!=len(targets):raise ValueError('invalid_targets')
 reports=[]
 for t in targets:
  if t['placement'] not in ('STORY','SAVED_STORY','SPOTLIGHT'):raise ValueError('invalid_placement')
  query=urllib.parse.urlencode({'postId':t['post_id'],'platformType':'SNAPCHAT'})
  data=client.call('/analytics/post?'+query)
  p=data.get('post') or {};snap=(p.get('data') or {}).get('SNAPCHAT') or {}
  if p.get('id')!=t['post_id'] or p.get('teamId')!=client.team or p.get('status')!='POSTED' or p.get('deletedAt') or snap.get('type','STORY')!=t['placement']:raise ValueError('post_identity_or_placement_mismatch')
  report=assess(data.get('items',[]),now,placement=t['placement'])
  report.update(package=t['package'],post_id=t['post_id'],card_index=t.get('card_index'),posted_at=p.get('postedDate'))
  reports.append(report)
 return {'version':1,'observed_at':now.isoformat(),'reports':reports,'paid_model_requests':0,'comparison_ready':False,'note':'Snapshots only. A matched 24h/7d exposure window and supported metrics are required before comparison.'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--targets',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 from .bundle_api import BundleClient
 c=BundleClient();c.check();result=collect(c,json.loads(Path(a.targets).read_text()),datetime.now(timezone.utc))
 Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2))
 print(json.dumps({'reports':len(result['reports']),'statuses':[r['status'] for r in result['reports']],'paid_model_requests':0}))
if __name__=='__main__':main()
