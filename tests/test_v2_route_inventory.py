from pathlib import Path
import pytest


def test_new_transport_or_inline_workflow_requires_review(tmp_path):
    from publishing_v2.route_inventory import inventory, verify
    (tmp_path/'sender.py').write_text('import urllib.request\ndef send():\n return urllib.request.urlopen("https://example.test")\n')
    baseline=inventory(tmp_path)
    verify(tmp_path,baseline)
    (tmp_path/'sender.py').write_text('import urllib.request\ndef send():\n return urllib.request.urlopen("https://different.test", data=b"publish")\n')
    with pytest.raises(ValueError):verify(tmp_path,baseline)
    (tmp_path/'.github/workflows').mkdir(parents=True)
    (tmp_path/'.github/workflows/new.yml').write_text('steps:\n - run: curl -X POST example.test\n')
    with pytest.raises(ValueError):verify(tmp_path,baseline)


def test_repo_route_inventory_has_no_unreviewed_changes():
    import json
    from publishing_v2.route_inventory import verify
    verify(Path('.'),json.loads(Path('publishing_v2/route-inventory.json').read_text()))
