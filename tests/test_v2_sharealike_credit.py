from publishing_v2.autopilot.credits import attribution_eligible, public_attribution_layout

def asset(**kw):
 return dict(provider='commons',asset_id='38130580',license='CC BY-SA 4.0',license_url='https://creativecommons.org/licenses/by-sa/4.0/',credit='Mathías Tabó',title='Diamond Viper V330 / RIVA 128',source_url='https://commons.wikimedia.org/?curid=38130580',restrictions='',sharealike_presentation='unmodified_photo_collection',modifications='Resized only',**kw)

def test_sharealike_requires_explicit_unmodified_collection_and_full_notice():
 a=asset();assert attribution_eligible(a)
 rows,height=public_attribution_layout(a)
 notice='\n'.join(rows)
 for value in ['Mathías Tabó','38130580','creativecommons.org/licenses/by-sa/4.0','Resized only','Photo: CC BY-SA 4.0']:
  assert value in notice
 assert len(rows)==4 and height>=112
 for key in ['sharealike_presentation','modifications']:
  b=dict(a);b.pop(key);assert not attribution_eligible(b)
 b=dict(a,sharealike_presentation='cropped_without_license');assert not attribution_eligible(b)
