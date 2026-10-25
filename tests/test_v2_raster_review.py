import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image, ImageDraw
from publishing_v2.readability import validate_readability, ReadabilityError


class RasterReviewTests(unittest.TestCase):
    def fixture(self, third_line=False, spacing=55):
        root=Path(self.tmp.name)
        image=Image.new('RGB',(1080,1920),'#F7F7EB');draw=ImageDraw.Draw(image)
        boxes={'headline':[60,260,1020,330],'bullet':[60,950,1020,1120],
               'caption':[60,850,1020,920],'closing':[60,1500,1020,1570],
               'cta':[60,1700,1020,1770]}
        blocks=[]
        for role,box in boxes.items():
            color='#0B3656' if role=='bullet' else '#7A7973' if role=='caption' else '#B60E32'
            count=(3 if third_line else 2) if role=='bullet' else 1
            for i in range(count):
                y=box[1]+5+i*spacing
                draw.rectangle((80,y,900,y+30),fill=color)
            blocks.append({'role':role,'box':box,'line_count':2 if role=='bullet' else 1,'color':color})
        image.save(root/'card.png');raw=(root/'card.png').read_bytes();sha=hashlib.sha256(raw).hexdigest()
        manifest={'format':'owner-reviewed-composite-v1','approved':True,
                  'owner_review':{'approved_media_sha256':[sha]}}
        (root/'manifest.json').write_text(json.dumps(manifest))
        report={'version':1,'typography_profile':'owner-reviewed-composite-raster-v1',
            'visual_review':{'approved':True,'reference':'Owner-approved final raster, measured not inferred font',
                'mobile_width':390,'captions_match_images':True},
            'cards':[{'sha256':sha,'blocks':blocks}]}
        (root/'readability.json').write_text(json.dumps(report))
        return root,raw

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)

    def test_measured_pixels_allow_two_lines_without_inventing_font(self):
        root,raw=self.fixture()
        self.assertEqual(validate_readability(root/'readability.json',[(root/'card.png',raw)])['card_count'],1)

    def test_three_pixel_lines_fail_even_when_report_says_two(self):
        root,raw=self.fixture(True)
        with self.assertRaises(ReadabilityError): validate_readability(root/'readability.json',[(root/'card.png',raw)])

    def test_ten_blank_rows_separate_two_lines(self):
        root,raw=self.fixture(spacing=41)
        result=validate_readability(root/'readability.json',[(root/'card.png',raw)])
        self.assertEqual(result['bullet_line_counts'],[[2]])

    def test_revoked_manifest_cannot_authorize_raster_review(self):
        root,raw=self.fixture()
        manifest=json.loads((root/'manifest.json').read_text());manifest['approved']=False
        (root/'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(ReadabilityError): validate_readability(root/'readability.json',[(root/'card.png',raw)])
