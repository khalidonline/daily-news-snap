# A Latin abbreviation's closing dot must stay on the Latin run inside Arabic
# text: the 26 Sep test card drew the owner's exact title «P.T.» as «.P.T».
import os
import unittest

os.environ.setdefault('FONT_FAMILY', 'Almarai')
os.environ.setdefault('THEME', 'light')

from PIL import Image, ImageChops, ImageDraw

import news_bot

LRM = '‎'


class LatinAbbrevBidiTests(unittest.TestCase):
    def test_abbreviations_are_bound_sentence_periods_are_not(self):
        bound = news_bot._bind_latin_abbrev(
            'لعبة P.T. عام 1999 في U.S. مع Apple Inc. وانتهت مع Mac Studio.')
        self.assertIn('P.T.' + LRM, bound)
        self.assertIn('U.S.' + LRM, bound)
        self.assertIn('Inc.' + LRM, bound)
        self.assertTrue(bound.endswith('Studio.'))    # RTL sentence end stays RTL
        self.assertEqual(news_bot._bind_latin_abbrev('بين 2007 و2012.'), 'بين 2007 و2012.')

    def test_idempotent_after_sanitize(self):
        once, _ = news_bot.ar('P.T. عام')
        twice, _ = news_bot.ar(once)
        self.assertEqual(once, twice)

    @unittest.skipUnless(news_bot.HAS_RAQM, 'the runner renders through libraqm')
    def test_rendered_dot_follows_the_latin_run(self):
        font = news_bot.load_font(64, bold=True)

        def draw(text):
            img = Image.new('L', (700, 100), 255)
            ImageDraw.Draw(img).text((650, 10), text, font=font, fill=0, anchor='ra',
                                     direction='rtl', language='ar')
            return img

        shaped, _ = news_bot.ar('لعبة P.T. عام')
        fixed = draw(shaped)
        self.assertIsNone(ImageChops.difference(fixed, draw('لعبة P.T.' + LRM + ' عام')).getbbox())
        self.assertIsNotNone(ImageChops.difference(fixed, draw('لعبة P.T. عام')).getbbox())


if __name__ == '__main__':
    unittest.main()
