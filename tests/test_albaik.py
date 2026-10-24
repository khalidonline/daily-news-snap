import unittest,json
from pathlib import Path
from publishing_v2.readability import validate_readability,ReadabilityError
class Albaik(unittest.TestCase):
 def test_approved_export_passes(self):
  p=Path('approved/albaik-20261024/card.png')
  self.assertEqual(validate_readability(p.parent/'readability.json',[(str(p),p.read_bytes())])['card_count'],1)
 def test_changed_image_rejected(self):
  p=Path('approved/albaik-20261024/card.png')
  with self.assertRaises(ReadabilityError): validate_readability(p.parent/'readability.json',[(str(p),p.read_bytes()+b'changed')])
