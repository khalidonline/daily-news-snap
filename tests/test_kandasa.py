import unittest,json,tempfile
from pathlib import Path
from publishing_v2.readability import validate_readability,ReadabilityError
class KandasaTest(unittest.TestCase):
 def test_accepts_reviewed_card_and_rejects_changed_bytes(self):
  p=Path('approved/kandasa-20261024/readability.json')
  raw=Path('approved/kandasa-20261024/card.png').read_bytes()
  self.assertEqual(validate_readability(p,[(Path('card.png'),raw)])['card_count'],1)
  with self.assertRaises(ReadabilityError): validate_readability(p,[(Path('card.png'),raw+b'x')])
 def test_rejects_changed_approval(self):
  original=Path('approved/kandasa-20261024/readability.json')
  data=json.loads(original.read_text());data['visual_review']['approved']=False
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'kandasa-20261024'/'readability.json';p.parent.mkdir();p.write_text(json.dumps(data))
   with self.assertRaises(ReadabilityError): validate_readability(p,[(Path('card.png'),Path('approved/kandasa-20261024/card.png').read_bytes())])
