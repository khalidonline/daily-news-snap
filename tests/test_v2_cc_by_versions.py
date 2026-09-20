import unittest
from unittest.mock import patch
from publishing_v2.autopilot.credits import attribution_eligible, _blocks
from publishing_v2.public_images import search_commons
from test_v2_autopilot_credits import asset, package

class LicenseVersionsTests(unittest.TestCase):
    def test_mixed_versions_and_notices_are_preserved(self):
        two = asset(license='CC BY 2.0', license_url='https://creativecommons.org/licenses/by/2.0/',
                    copyright_notice='Copyright 2013 Photographer', attribution_notice='Credit supplied by author',
                    disclaimer='No warranty', usage_terms='Creative Commons Attribution 2.0')
        self.assertTrue(attribution_eligible(two))
        text = '\n'.join(t for t,b in _blocks(package([two, asset(asset_id='456')])) )
        for expected in ['CC BY 2.0', 'CC BY 4.0', two['license_url'], 'https://creativecommons.org/licenses/by/4.0/',
                         two['copyright_notice'], two['attribution_notice'], two['disclaimer'], two['usage_terms']]:
            self.assertIn(expected, text)
        self.assertFalse(attribution_eligible(dict(two, license_url=asset()['license_url'])))
        self.assertFalse(attribution_eligible(dict(two, disclaimer='x'*401)))
        self.assertFalse(attribution_eligible(dict(two, restrictions='personality')))
        with self.assertRaisesRegex(ValueError, 'conflicting_image_attribution'):
            _blocks(package([two, asset()]))

    def test_adapter_preserves_supplied_notices(self):
        fields = {'Copyright': 'Copyright Alice', 'Attribution': 'Alice / Museum', 'UsageTerms': 'CC BY 2.0',
                  'Disclaimer': 'No warranty'}
        info = {'mime':'image/jpeg', 'url':'https://upload.wikimedia.org/a.jpg',
                'descriptionurl':'https://commons.wikimedia.org/wiki/File:A.jpg',
                'extmetadata':{k:{'value':v} for k,v in fields.items()}}
        with patch('publishing_v2.public_images.get_json', return_value={'query':{'pages':[
                {'pageid':1,'title':'File:A.jpg','imageinfo':[info]}]}}):
            row = search_commons('A')[0]
        for key, field in [('copyright_notice','Copyright'),('attribution_notice','Attribution'),
                           ('usage_terms','UsageTerms'),('disclaimer','Disclaimer')]:
            self.assertEqual(row[key], fields[field])

    def test_by_two_cannot_publish_without_attached_credit_video(self):
        from publishing_v2.autopilot.runtime import publish_package
        row = asset(license='CC BY 2.0', license_url='https://creativecommons.org/licenses/by/2.0/')
        with self.assertRaisesRegex(ValueError, 'attribution_requires_single_video_delivery'):
            publish_package(package([row]), [], client=object())

    def test_credit_links_are_retained_without_truncation(self):
        from publishing_v2.public_images import rights_links
        self.assertEqual(rights_links({'Credit': {'value': '<a href="https://example.org/original">Original</a>'}}),
                         'https://example.org/original')
        self.assertFalse(attribution_eligible(asset(rights_links='https://example.org/'+'x'*400)))
