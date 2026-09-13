# -*- coding: utf-8 -*-
"""pytest 集成：把 src/ 与 tests/ 加进 import 路径。

不装 pytest 也能跑：`python tests/run_tests.py`。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT / "src"), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
