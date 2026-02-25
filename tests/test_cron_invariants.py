from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.cron_invariant_check import run


def test_cron_invariants():
    violations = run(ROOT)
    assert not violations, "\n".join(v.format() for v in violations)
