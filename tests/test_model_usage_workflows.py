"""Retired workflow entrypoints; model-usage runtime tests remain separate."""
from pathlib import Path
import pytest


@pytest.mark.parametrize("workflow", ["daily","topic","breaking","story","batch-review"])
def test_retired_usage_workflow_remains_inactive(workflow):
    assert not Path(f".github/workflows/{workflow}.yml").exists()
