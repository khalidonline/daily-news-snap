import hashlib
import tempfile
import unittest
from pathlib import Path
from PIL import Image, ImageDraw
from publishing_v2.autopilot.video import compile_story, _check_frame, _validate_stream


class StoryVideoTests(unittest.TestCase):
    def test_real_video_is_deterministic_and_review_frames_match_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);paths=[]
            for i,color in enumerate(['#d1e0d9','#e9d9c1','#f7f4ee']):
                path=root/f'input-{i}.jpg'
                frame=Image.new('RGB',(1080,1920),color)
                draw=ImageDraw.Draw(frame);draw.rectangle((90+i*40,200,940,850),fill=['red','blue','green'][i])
                draw.text((100,100),f'FRAME {i}: credits' if i==2 else f'FRAME {i}: editorial',fill='black',font_size=40)
                frame.save(path,quality=95);paths.append(path)
            first,reviews=compile_story(paths,root/'first')
            second,other_reviews=compile_story(paths,root/'second')
            self.assertEqual(first,second)
            self.assertEqual(first['duration_seconds'],35)
            self.assertEqual(first['kind'],'video')
            self.assertEqual(first['sha256'],hashlib.sha256((root/'first'/'story.mp4').read_bytes()).hexdigest())
            self.assertEqual(len(reviews),3)
            self.assertEqual(first['frame_sha256'],[hashlib.sha256(p.read_bytes()).hexdigest() for p in reviews])
            for source,review in zip(paths,reviews):
                with Image.open(review) as decoded:
                    self.assertEqual(decoded.size,(1080,1920))
                _check_frame(source,review)

    def test_mixed_editorial_and_credits_jpeg_subsampling_preserves_timeline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for index, color in enumerate(['#a93030', '#308030', '#3040a0', '#f7f4ee']):
                path = root / f'card-{index}.jpg'
                frame = Image.new('RGB', (1080, 1920), color)
                ImageDraw.Draw(frame).text((100, 200), f'Card {index}', fill='black', font_size=60)
                # Match actual runtime editorial JPEGs and final credits JPEG.
                frame.save(path, quality=95, **({'subsampling': 0} if index == 3 else {}))
                paths.append(path)
            specification, reviews = compile_story(paths, root / 'compiled')
            self.assertEqual(specification['duration_seconds'], 45)
            self.assertEqual(len(reviews), 4)
            for source, review in zip(paths, reviews):
                _check_frame(source, review)
            with Image.open(reviews[-1]) as credits:
                self.assertGreater(min(credits.getpixel((540, 960))), 225)

    def test_bounds_fail_before_encoding(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError,'attributed_video_requires_at_most_four_editorial_cards'):
                compile_story(['missing.jpg']*6,root)
            with self.assertRaisesRegex(ValueError,'attributed_video_requires_at_least_two_editorial_cards'):
                compile_story(['missing.jpg']*2,root)

    def test_frame_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            a=Path(root)/'a.png';b=Path(root)/'b.png'
            Image.new('RGB',(1080,1920),'black').save(a)
            Image.new('RGB',(1080,1920),'white').save(b)
            with self.assertRaisesRegex(ValueError,'video_frame_mismatch'):_check_frame(a,b)

    def test_wrong_duration_extra_frames_and_audio_rejected(self):
        stream={'codec_type':'video','codec_name':'h264','pix_fmt':'yuv420p','width':1080,'height':1920,
                'avg_frame_rate':'30/1','nb_read_frames':'1050','duration':'35.000000'}
        _validate_stream({'streams':[stream],'format':{'duration':'35.000000'}},35)
        for bad in [dict(stream,nb_read_frames='1051'),dict(stream,duration='34'),dict(stream,width=540),dict(stream,pix_fmt='yuv444p')]:
            with self.assertRaises(ValueError):_validate_stream({'streams':[bad],'format':{'duration':'35'}},35)
        with self.assertRaises(ValueError):_validate_stream({'streams':[stream,{'codec_type':'audio'}],'format':{'duration':'35'}},35)

if __name__=='__main__':unittest.main()
