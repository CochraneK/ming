# -*- coding: utf-8 -*-
"""零依赖测试运行器。

项目刻意不引入第三方包（见 requirements.txt），因此这里自建一个极小的
用例发现器：任何 ``test_*.py`` 中名为 ``test_*`` 的函数都会被调用。

    python tests/run_tests.py            # 跑全部
    python tests/run_tests.py core       # 只跑名字含 core 的模块

装了 pytest 时也可以直接 ``pytest tests``，用例是同一批函数。
"""

from __future__ import annotations

import importlib
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
for _p in (str(ROOT / "src"), str(TESTS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SKIP_MODULES = {"conftest", "_support", "run_tests"}


def discover(keyword: str = ""):
    modules = []
    for path in sorted(TESTS.glob("test_*.py")):
        name = path.stem
        if name in SKIP_MODULES:
            continue
        if keyword and keyword not in name:
            continue
        modules.append(name)
    return modules


def run(keyword: str = "") -> int:
    modules = discover(keyword)
    if not modules:
        print("没有匹配的测试模块（keyword=%r）" % keyword)
        return 1
    passed, failed = [], []
    started = time.time()
    for mod_name in modules:
        module = importlib.import_module(mod_name)
        cases = sorted(n for n in dir(module) if n.startswith("test_") and callable(getattr(module, n)))
        print("\n%s（%d 例）" % (mod_name, len(cases)))
        for case in cases:
            t0 = time.time()
            try:
                getattr(module, case)()
            except Exception:
                failed.append((mod_name, case, traceback.format_exc()))
                print("  FAIL  %-46s %.2fs" % (case, time.time() - t0))
            else:
                passed.append((mod_name, case))
                print("  ok    %-46s %.2fs" % (case, time.time() - t0))
    elapsed = time.time() - started
    print("\n" + "=" * 64)
    print("通过 %d / 失败 %d · 用时 %.1fs" % (len(passed), len(failed), elapsed))
    for mod_name, case, tb in failed:
        print("\n--- %s::%s ---\n%s" % (mod_name, case, tb.rstrip()))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1] if len(sys.argv) > 1 else ""))
