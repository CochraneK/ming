# -*- coding: utf-8 -*-
"""对 web/css/app.css 做极小、可审计、幂等的历史样式去重。

只处理已经确认的两类冗余：
1. ``.quality-grid .quality`` 完全相同规则曾被重复追加；
2. ``.full-graph-tip-box`` 先写 ``white-space:nowrap``，后面又单独覆盖为
   ``white-space:normal``。把最终值并回主规则并删掉后置覆盖。

脚本使用 bytes 读写，避免把历史文件里混合的 CRLF/LF 全量改写成另一种换行，
从而把一个小修复放大成不可审查的大 diff。
"""
from __future__ import annotations

import argparse
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CSS = BASE / "web" / "css" / "app.css"

QUALITY = (
    ".quality-grid .quality{border-left:3px solid var(--gold);"
    "background:#fbf8f1;padding:12px 14px}"
).encode("utf-8")

TIP_NOWRAP = (
    ".full-graph-tip-box{position:fixed;pointer-events:none;"
    "background:rgba(40,33,28,.92);color:#fffdf9;font-size:12px;"
    "padding:5px 8px;border-radius:6px;max-width:240px;white-space:nowrap;"
    "transform:translate(-50%,calc(-100% - 12px));display:none;z-index:50}"
).encode("utf-8")
TIP_NORMAL = TIP_NOWRAP.replace(b"white-space:nowrap", b"white-space:normal")
TIP_OVERRIDE = b".full-graph-tip-box{white-space:normal}"
TIP_COMMENT = "/* 力导图悬浮提示：允许换行，避免超长文本溢出 */".encode("utf-8")


def normalize(raw: bytes) -> bytes:
    data = raw

    quality_count = data.count(QUALITY)
    if quality_count == 0:
        raise SystemExit("CSS 锚点缺失：quality-grid quality")
    if quality_count > 1:
        first = data.find(QUALITY)
        head = data[: first + len(QUALITY)]
        tail = data[first + len(QUALITY) :].replace(QUALITY, b"")
        data = head + tail

    nowrap_count = data.count(TIP_NOWRAP)
    normal_count = data.count(TIP_NORMAL)
    if nowrap_count + normal_count != 1:
        raise SystemExit(
            "CSS 锚点异常：full-graph-tip-box 主规则 nowrap=%d normal=%d"
            % (nowrap_count, normal_count)
        )
    if nowrap_count == 1:
        data = data.replace(TIP_NOWRAP, TIP_NORMAL, 1)

    # 后置覆盖和专门解释这层覆盖的注释都不再需要。
    data = data.replace(TIP_OVERRIDE, b"")
    data = data.replace(TIP_COMMENT, b"")
    return data


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="规范化 app.css 历史重复规则")
    parser.add_argument("--check", action="store_true", help="只检查，不写文件")
    args = parser.parse_args(argv)

    raw = CSS.read_bytes()
    updated = normalize(raw)
    if updated == raw:
        print("app.css 已规范化")
        return 0
    if args.check:
        print("app.css 存在可规范化的历史重复规则")
        return 1
    CSS.write_bytes(updated)
    print("app.css 已规范化：%d → %d bytes" % (len(raw), len(updated)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
