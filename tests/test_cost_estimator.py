import pytest
from backend.services.cost_estimator import estimate_completion_cost_usd

def test_super_cost_example():
    assert estimate_completion_cost_usd("nvidia/nemotron-3-super-120b-a12b", 4000, 700) == pytest.approx(0.00183)

def test_nano_cost_example():
    assert estimate_completion_cost_usd("nvidia/Nemotron-3-Nano-30B", 4000, 700) == pytest.approx(0.000408)

def test_cost_estimator_rejects_negative_or_unknown():
    with pytest.raises(ValueError):
        estimate_completion_cost_usd("unknown", 1, 1)
    with pytest.raises(ValueError):
        estimate_completion_cost_usd("nvidia/Nemotron-3-Nano-30B", -1, 1)
