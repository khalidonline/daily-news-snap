import json
import tempfile
import unittest
from pathlib import Path
from publishing_v2 import public_images
from publishing_v2 import preview


class PreviewTests(unittest.TestCase):
    def test_expiry_is_saudi_calendar_bound(self):
        preview.validate_date('2026-09-12', '2026-09-13T20:59:59+00:00')
        with self.assertRaises(ValueError):
            preview.validate_date('2026-09-12', '2026-09-13T21:00:00+00:00')
        with self.assertRaises(ValueError):
            preview.validate_date('2026-09-12', '2026-09-11T12:00:00+00:00')

    def test_vision_receives_actual_pixels_and_rejects_false_or_string_decision(self):
        from test_v2_public_images import jpeg
        calls = []
        def transport(method, url, headers, body):
            calls.append(body)
            return {'status_code': 200, 'body': {'id': 'r1', 'status': 'completed', 'usage': {'input_tokens': 100,'output_tokens': 30},
              'output': [{'type':'message','content':[{'type':'output_text','text':json.dumps({'relevant': True, 'crop_suitable': True,
              'historically_appropriate': True, 'readable': 'yes', 'reason': 'check'})}]}]}}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'card.jpg';p.write_bytes(jpeg())
            with self.assertRaises(ValueError):
                preview.review_card(p, {'title':'Moon'}, env={'OPENAI_API_KEY':'test'}, transport=transport)
        self.assertTrue(calls[0]['input'][0]['content'][1]['image_url'].startswith('data:image/jpeg;base64,'))

    def test_openai_rate_limit_uses_anthropic_pixels_once(self):
        from test_v2_public_images import jpeg
        calls=[]
        def transport(method,url,headers,body):
            calls.append((url,body))
            if len(calls)==1:
                return {'status_code':429,'body':{'error':{'code':'insufficient_quota'}}}
            return {'status_code':200,'body':{'id':'msg1','stop_reason':'end_turn',
                'usage':{'input_tokens':100,'output_tokens':50},'content':[{'type':'text','text':'```json\n'+json.dumps({
                'relevant':True,'crop_suitable':True,'historically_appropriate':True,'readable':True,'reason':'Fits'})+'\n```'}]}}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'card.jpg';path.write_bytes(jpeg())
            result=preview.review_card(path,{'title':'Moon'},env={'OPENAI_API_KEY':'x','ANTHROPIC_API_KEY':'y'},transport=transport)
        self.assertTrue(result['passed'])
        self.assertEqual(result['model'],'claude-sonnet-5')
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[1][1]['messages'][0]['content'][0]['source']['type'],'base64')

    def test_unknown_telegram_send_cannot_be_retried_locally(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'card.jpg';p.write_bytes(b'photo')
            calls=[]
            def send(*args): calls.append(1);raise TimeoutError('secret-token')
            with self.assertRaises(RuntimeError):
                preview.send_once(p, 'preview', Path(d)/'receipt.json', env={'TELEGRAM_TOKEN':'x','TELEGRAM_CHAT_ID':'1'}, transport=send)
            with self.assertRaises(RuntimeError):
                preview.send_once(p, 'preview', Path(d)/'receipt.json', env={'TELEGRAM_TOKEN':'x','TELEGRAM_CHAT_ID':'1'}, transport=send)
            self.assertEqual(len(calls),1)
            self.assertNotIn('secret-token',(Path(d)/'receipt.json').read_text())

    def test_telegram_success_requires_message_receipt(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'card.jpg';p.write_bytes(b'photo')
            result=preview.send_once(p,'preview',Path(d)/'receipt.json',env={'TELEGRAM_TOKEN':'x','TELEGRAM_CHAT_ID':'1'},
                transport=lambda *args:{'ok':True,'result':{'message_id':42,'chat':{'id':1}}})
            self.assertEqual(result['message_id'],42)
            self.assertEqual(result['status'],'sent')

    def test_only_exact_apod_host_allowed(self):
        public_images.validate_url('https://apod.nasa.gov/apod/image/2609/a.jpg')
        with self.assertRaises(public_images.ImageSourceError):
            public_images.validate_url('https://apod.nasa.gov.evil.test/a.jpg')
