import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image, ImageDraw
import story_bot as story

class BodyReadabilityTests(unittest.TestCase):
    def test_crowded_story_reclaims_photo_space_before_shrinking_body(self):
        # Regression: the published Oswald card silently shrank body to 32px.
        body=('بعد ٧٨ سنة، رجعت ديزني حقوق أوزوالد عام ٢٠٠٦ باتفاق مع NBCUniversal. '
              'المفاجأة إن الاتفاق شمل السماح للمعلّق الرياضي آل مايكلز بالانتقال من شبكة ABC التابعة لديزني إلى NBC. '
              'ورجع أوزوالد يظهر بألعاب ومنتجات وأفلام ديزني.')
        captured=[]
        original=ImageDraw.ImageDraw.text
        def record(draw, xy, text, *args, **kwargs):
            if kwargs.get('fill') == story.BODY:
                captured.append((draw,kwargs['font'].size,text))
            return original(draw,xy,text,*args,**kwargs)
        with tempfile.TemporaryDirectory() as folder:
            photo=Path(folder)/'photo.jpg';target=Path(folder)/'card.png'
            Image.new('RGB',(1024,540),'green').save(photo)
            with patch.object(ImageDraw.ImageDraw,'text',record):
                story.render_frame(target,'ملخص تنفيذي - قصة','٣ من ٣',
                    'رجع الأرنب… بصفقة فيها معلّق رياضي',64,sub=body,photo=photo,
                    punch='الأرنب اللي خلّت خسارته والت يبتكر ميكي… صاروا الاثنين تحت سقف شركة وحدة.',
                    photo_caption='أوزوالد في فيلم ديزني القصير عام ٢٠٢٢')
            self.assertTrue(target.is_file())
            last=captured[-1][0]
            sizes=[size for canvas,size,_ in captured if canvas is last]
            self.assertTrue(sizes)
            self.assertGreaterEqual(min(sizes),44)
