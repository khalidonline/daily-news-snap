"""Retirement guards; original workflow-only assertions are archived."""
from pathlib import Path
import pytest


@pytest.mark.parametrize("workflow", ["daily","story","external-clock-receiver"])
def test_retired_paid_workflow_cannot_be_dispatched(workflow):
    assert not Path(f".github/workflows/{workflow}.yml").exists()
