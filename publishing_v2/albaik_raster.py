"""Exact owner-approved raster review, not invented font metrics."""
import hashlib,io,json
from PIL import Image
EXPECTED_REPORT = "{\n  \"version\": 1,\n  \"typography_profile\": \"owner-reviewed-albaik-raster\",\n  \"visual_review\": {\n    \"approved\": true,\n    \"reference\": \"Khalid approved latest Albaik preview; exact exported pixels visually reviewed. Font family/size not asserted.\"\n  },\n  \"cards\": [\n    {\n      \"sha256\": \"5408d02d511458a830f559264ae6bc91973f28c82eeb4fe88f30787a8473c50f\",\n      \"width\": 1080,\n      \"height\": 1920,\n      \"bullet_line_counts\": [\n        2,\n        2,\n        2,\n        2\n      ],\n      \"text_boxes\": [\n        [\n          40,\n          235,\n          1040,\n          320\n        ],\n        [\n          40,\n          920,\n          1050,\n          1040\n        ],\n        [\n          40,\n          1080,\n          1050,\n          1205\n        ],\n        [\n          40,\n          1250,\n          1050,\n          1370\n        ],\n        [\n          40,\n          1420,\n          1050,\n          1545\n        ],\n        [\n          90,\n          1570,\n          1000,\n          1700\n        ],\n        [\n          130,\n          1730,\n          910,\n          1805\n        ]\n      ],\n      \"caption_boxes\": [\n        [\n          60,\n          825,\n          470,\n          875\n        ],\n        [\n          640,\n          825,\n          980,\n          875\n        ]\n      ]\n    }\n  ]\n}\n"
def validate(report,media,fail):
 if report != json.loads(EXPECTED_REPORT) or len(media)!=1: fail('Albaik review changed')
 content=media[0][1]
 if hashlib.sha256(content).hexdigest()!='5408d02d511458a830f559264ae6bc91973f28c82eeb4fe88f30787a8473c50f': fail('Albaik image changed')
 with Image.open(io.BytesIO(content)) as image:
  if image.size!=(1080,1920) or image.format!='PNG': fail('Albaik export dimensions')
  image.load()
 card=report['cards'][0]
 if any(n>2 for n in card['bullet_line_counts']): fail('More than two lines')
 boxes=card['text_boxes']+card['caption_boxes']
 for i,a in enumerate(boxes):
  if not (35<=a[0]<a[2]<=1050 and 230<=a[1]<a[3]<=1810): fail('Unsafe text box')
  for b in boxes[i+1:]:
   if max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3]): fail('Overlap')
 return {'status':'owner_reviewed_exact_raster_validated','card_count':1}
