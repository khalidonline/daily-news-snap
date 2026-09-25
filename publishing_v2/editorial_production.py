"""Text approval before design; bounded patches and pixel-verified card reuse."""
import copy
import hashlib
import json
from pathlib import Path
from .autopilot.policy import digest

TEXT_CHECKS = ('factual','timely','current_attention','saudi_language','broad_appeal',
               'story_coherent','documented_story','distinct_value','owner_quality','safe_routine')
TEXT_FIELDS = ('kind','title','body','punch','claim_ids','image_query','image_caption')

def text_input(package):
    data = {**{k:copy.deepcopy(package[k]) for k in
               ('title','candidate','research','sources','lane','as_of','expires_at','verified_timing') if k in package},
            'cards':[{k:copy.deepcopy(c[k]) for k in TEXT_FIELDS if k in c}
                     for c in package['cards'] if c.get('kind')!='credits']}
    if isinstance(data.get('candidate'),dict): data['candidate'].pop('visual_discovery',None)
    return data

class TextRejected(ValueError):
    def __init__(self, review):
        super().__init__('text_not_approved: '+str(review.get('reason',''))[:2000])
        self.review=review

def approve_text(package, agent, original_sources=None):
    data=text_input(package)
    review=agent.run('text_review',dict(data, original_sources=original_sources) if original_sources else data)
    if any(review.get('checks',{}).get(k) is not True for k in TEXT_CHECKS):
        raise TextRejected(review)
    if review.get('repair_indices') != [] or not isinstance(review.get('reason'),str) or not review['reason'].strip():
        raise TextRejected(review)
    package['text_approval']={'input_sha256':digest(data),'review':review}
    return package['text_approval']

def require_text_approval(package):
    approval=package.get('text_approval',{})
    if approval.get('input_sha256')!=digest(text_input(package)):
        raise ValueError('text_approval_missing_or_stale')
    if any(approval.get('review',{}).get('checks',{}).get(k) is not True for k in TEXT_CHECKS):
        raise ValueError('text_approval_failed')

def repair_indices(review, count):
    indices=review.get('repair_indices',[])
    if not isinstance(indices,list) or not indices or any(type(i) is not int or i<0 or i>=count for i in indices):
        raise ValueError('repair_scope_missing_or_invalid')
    if len(set(indices))!=len(indices):raise ValueError('duplicate_repair_indices')
    return indices

def apply_card_patches(draft, result, allowed):
    patches=result.get('patches')
    if not isinstance(patches,list) or not patches:raise ValueError('missing_card_patches')
    updated=copy.deepcopy(draft); seen=set()
    for patch in patches:
        i=patch.get('index');card=patch.get('card')
        if type(i) is not int or i not in allowed or i in seen or not isinstance(card,dict):
            raise ValueError('patch_outside_approved_scope')
        seen.add(i);updated['cards'][i]=copy.deepcopy(card)
    if seen!=set(allowed):raise ValueError('incomplete_card_patches')
    return updated

class CardArtifacts:
    def __init__(self, folder, renderer_version):
        self.folder=Path(folder);self.version=renderer_version
    def key(self, binding):return digest({'renderer':self.version,'binding':binding})
    def reuse(self,index,binding,path):
        try:
            row=json.loads((self.folder/f'.card-{index}.json').read_text())
            return row['key']==self.key(binding) and row['sha256']==hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except (OSError,ValueError,KeyError,TypeError):return False
    def record(self,index,binding,path,metadata=None):
        self.folder.mkdir(parents=True,exist_ok=True)
        row={'key':self.key(binding),'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'metadata':metadata or {}}
        target=self.folder/f'.card-{index}.json'; temp=target.with_suffix('.tmp')
        temp.write_text(json.dumps(row));temp.replace(target)

    def metadata(self,index):
        return json.loads((self.folder/f'.card-{index}.json').read_text()).get('metadata',{})
