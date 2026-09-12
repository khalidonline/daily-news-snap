import tempfile
import unittest
from pathlib import Path
from publishing_v2 import preview_package as package

class PackageTests(unittest.TestCase):
    def test_partial_album_receipt_is_unknown_and_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            paths=[]
            for n in range(8):
                p=Path(d)/f'{n}.jpg';p.write_bytes(b'photo');paths.append(p)
            journal=Path(d)/'receipt.json'
            env={'TELEGRAM_TOKEN':'x','TELEGRAM_CHAT_ID':'1'}
            calls=[]
            def transport(*args):
                calls.append(1)
                return {'ok':True,'result':[{'message_id':1,'chat':{'id':1}}]}
            with self.assertRaises(RuntimeError):package.send_album_once(paths,['caption']*8,journal,env=env,transport=transport)
            with self.assertRaises(RuntimeError):package.send_album_once(paths,['caption']*8,journal,env=env,transport=transport)
            self.assertEqual(len(calls),1)

    def test_album_preserves_order_and_confirms_all_messages(self):
        with tempfile.TemporaryDirectory() as d:
            paths=[]
            for n in range(8):
                p=Path(d)/f'{n}.jpg';p.write_bytes(f'photo{n}'.encode());paths.append(p)
            def transport(url,body,headers):
                self.assertTrue(url.endswith('/sendMediaGroup'))
                self.assertLess(body.index(b'photo0'),body.index(b'photo7'))
                return {'ok':True,'result':[{'message_id':n+10,'chat':{'id':1}} for n in range(8)]}
            result=package.send_album_once(paths,['caption']*8,Path(d)/'receipt.json',env={'TELEGRAM_TOKEN':'x','TELEGRAM_CHAT_ID':'1'},transport=transport)
            self.assertEqual(result['message_ids'],list(range(10,18)))

    def test_unreviewed_card_blocks_entire_package(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'a.jpg';path.write_bytes(b'a')
            with self.assertRaises(ValueError):package.verify_reviews([path],[{'passed':False}])
            with self.assertRaises(ValueError):package.verify_reviews([path],[])
            with self.assertRaises(ValueError):package.verify_reviews([path],[{'passed':True,'card_sha256':'old'}])
