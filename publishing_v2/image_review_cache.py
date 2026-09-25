"""Reuse independent image verdicts only for identical pixels and editorial context."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

class ImageReviewCache:
    def __init__(self, store_factory, policy, now=None):
        self.store_factory, self.policy = store_factory, policy
        self.now = now or (lambda: datetime.now(timezone.utc))

    def run(self, data, images, review):
        options = data.get('options', [])
        if not images or len(images) != len(options) or len(images) > 8:
            raise ValueError('invalid_image_review_inputs')
        ids = [o['asset_id'] for o in options]
        if len(set(ids)) != len(ids): raise ValueError('duplicate_review_ids')
        context = {k:v for k,v in data.items() if k != 'options'}
        hits, missing = {}, []
        for option,path in zip(options,images):
            binding = {'version':1,'policy':self.policy,'context':context,'option':option,
                       'pixels':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
            key = hashlib.sha256(json.dumps(binding,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()
            store = self.store_factory('image-review-' + key)
            row = store.read()  # An uncertain store never authorizes another paid request.
            if row:
                try:
                    stamp = datetime.fromisoformat(row['at'])
                    valid = (row['key'] == key and type(row['accepted']) is bool
                        and isinstance(row['description'],str) and stamp.tzinfo is not None
                        and timedelta(0) <= self.now()-stamp < timedelta(days=7))
                except (KeyError, TypeError, ValueError): valid=False
                if valid:
                    hits[option['asset_id']] = row
                    continue
            missing.append((option,path,key,store))
        if missing:
            decision = review(dict(context,options=[x[0] for x in missing]),[x[1] for x in missing])
            accepted = decision.get('accepted_ids'); descriptions=decision.get('descriptions',{})
            allowed={x[0]['asset_id'] for x in missing}
            if (not isinstance(accepted,list) or any(not isinstance(i,str) or i not in allowed for i in accepted)
                    or len(set(accepted)) != len(accepted) or not isinstance(descriptions,dict)):
                raise ValueError('invalid_cached_image_verdict')
            for option,path,key,store in missing:
                ident=option['asset_id']; description=descriptions.get(ident,'')
                if not isinstance(description,str): raise ValueError('invalid_image_description')
                row={'key':key,'at':self.now().isoformat(),'accepted':ident in accepted,'description':description[:600]}
                store.save(row)
                hits[ident]=row
        return {'accepted_ids':[i for i in ids if hits[i]['accepted']],
                'descriptions':{i:hits[i]['description'] for i in ids if hits[i]['accepted']},
                'reason':'Verified image verdicts bound to pixels, context, prompt and model.',
                'cache_hits':len(ids)-len(missing)}
