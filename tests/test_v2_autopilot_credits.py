import tempfile
import unittest
from pathlib import Path
from PIL import Image
from publishing_v2.autopilot.credits import attribution_eligible, render_credits, _layout


def asset(**changes):
    return {'license':'CC BY 4.0', 'license_url':'https://creativecommons.org/licenses/by/4.0/',
            'credit':'Aisha Photographer', 'title':'File:Saudi classroom.jpg', 'asset_id':'123',
            'source_url':'https://commons.wikimedia.org/wiki/File:Saudi_classroom.jpg',
            'restrictions':'', 'credit_line':'Courtesy of Aisha Photographer', **changes}


def package(rows):
    return {'cards':[{'image':row} for row in rows],
            'sources':[{'url':'https://www.bbc.com/news/arabic/long-story'},
                       {'url':'https://www.bbc.com/news/arabic/other-story'}]}


class CreditsTests(unittest.TestCase):
    def test_exact_license_and_bounded_complete_attribution(self):
        self.assertTrue(attribution_eligible(asset()))
        self.assertTrue(attribution_eligible(asset(license_url='http://creativecommons.org/licenses/by/4.0/')))
        for changes in [{'license':'CC BY-SA 4.0'}, {'license_url':'https://evil.test/licenses/by/4.0/'},
                        {'credit':''}, {'credit':'unknown'}, {'credit':'x'*121}, {'title':'x'*181},
                        {'credit_line':'x'*201}, {'restrictions':'trademark'}, {'asset_id':'abc'},
                        {'source_url':'https://user@commons.wikimedia.org/a'},
                        {'source_url':'http://commons.wikimedia.org/a'},
                        {'source_url':'https://commons.wikimedia.org.evil.test/a'}]:
            with self.subTest(changes=changes):self.assertFalse(attribution_eligible(asset(**changes)))

    def test_layout_preserves_full_credit_deduplicates_and_stays_in_bounds(self):
        rows=_layout(package([asset(),asset()]))
        text='\n'.join(row['text'] for row in rows)
        self.assertEqual(text.count('File:Saudi classroom.jpg'),1)
        self.assertIn('Courtesy of Aisha Photographer',text)
        self.assertIn('https://commons.wikimedia.org/?curid=123',text)
        self.assertIn('https://creativecommons.org/licenses/by/4.0/',text)
        self.assertIn('cropped/resized',text)
        self.assertEqual(text.count('bbc.com'),1)
        for row in rows:
            x,y,right,bottom=row['bounds']
            self.assertGreaterEqual(x,64); self.assertLessEqual(right,1016)
            self.assertGreaterEqual(y,390); self.assertLessEqual(bottom,1820)
            self.assertGreaterEqual(row['size'],26)

    def test_overflow_holds_without_creating_partial_image(self):
        rows=[asset(asset_id=str(i+1),title='W'*180,credit='W'*120,credit_line='W'*200) for i in range(6)]
        with self.assertRaisesRegex(ValueError,'credits_layout_overflow'):_layout(package(rows))
        with self.assertRaisesRegex(ValueError,'too_many_credited_assets'):
            _layout(package([asset(asset_id=str(i+1)) for i in range(7)]))

    def test_render_is_deterministic_jpeg_with_photo_strip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source.jpg';target=root/'credits.jpg';other=root/'other.jpg'
            Image.new('RGB',(1600,1000),'red').save(source)
            self.assertEqual(render_credits(package([asset()]),source,target),target)
            render_credits(package([asset()]),source,other)
            self.assertEqual(target.read_bytes(),other.read_bytes())
            with Image.open(target) as image:
                self.assertEqual(image.size,(1080,1920));self.assertEqual(image.format,'JPEG')
                r,g,b=image.getpixel((540,230));self.assertGreater(r,g+100)

if __name__=='__main__':unittest.main()
