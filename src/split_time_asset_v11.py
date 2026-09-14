# -*- coding: utf-8 -*-
"""V11 在线时间域物理分层：把 lifespans 从 data-time.js 拆成独立资源。

最终 DATA、standalone 与 build.py 的逻辑分区保持不变；这里只对 web 构建后的物理文件
做无损后处理，使年谱只需 characters + lifespans，而时间轴/帝王继续使用 time + events。
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

TIME_NAME = "time"
LIFESPANS_NAME = "lifespans"
_ASSIGN_RE = re.compile(r"^Object\.assign\(DATA,(.*)\);$", re.MULTILINE)


def _compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def read_chunk_payload(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = _ASSIGN_RE.search(text)
    if not match:
        raise RuntimeError("找不到 Object.assign(DATA,...)：%s" % path)
    value = json.loads(match.group(1))
    if not isinstance(value, dict):
        raise RuntimeError("DATA chunk 不是对象：%s" % path)
    return value


def _replace_payload(text: str, payload: dict) -> str:
    updated, count = _ASSIGN_RE.subn("Object.assign(DATA,%s);" % _compact(payload), text, count=1)
    if count != 1:
        raise RuntimeError("替换 DATA chunk 失败")
    return updated


def _lifespans_script(lifespans) -> str:
    payload = {"lifespans": lifespans}
    return (
        "Object.assign(DATA,%s);\n" % _compact(payload)
        + "window.__MING_DATA_CHUNKS__=window.__MING_DATA_CHUNKS__||{};\n"
        + 'window.__MING_DATA_CHUNKS__["lifespans"]=true;\n'
        + "document.dispatchEvent(new CustomEvent('ming:data-chunk',{detail:{name:\"lifespans\"}}));\n"
    )


def check_site(root: Path) -> dict:
    assets = root / "assets"
    time_path = assets / "data-time.js"
    life_path = assets / "data-lifespans.js"
    if not time_path.exists():
        raise RuntimeError("缺少 %s" % time_path)
    if not life_path.exists():
        raise RuntimeError("缺少 %s" % life_path)
    time_payload = read_chunk_payload(time_path)
    life_payload = read_chunk_payload(life_path)
    if "lifespans" in time_payload:
        raise RuntimeError("data-time.js 仍包含 lifespans")
    if set(life_payload) != {"lifespans"}:
        raise RuntimeError("data-lifespans.js 字段异常：%s" % sorted(life_payload))
    if 'window.__MING_DATA_CHUNKS__["lifespans"]=true' not in life_path.read_text(encoding="utf-8"):
        raise RuntimeError("data-lifespans.js 未标记 chunk ready")
    return {
        "time_bytes": time_path.stat().st_size,
        "lifespans_bytes": life_path.stat().st_size,
        "lifespans_count": len(life_payload.get("lifespans") or []),
    }


def split_site(root: Path) -> dict:
    assets = root / "assets"
    time_path = assets / "data-time.js"
    life_path = assets / "data-lifespans.js"
    if not time_path.exists():
        raise RuntimeError("缺少 %s" % time_path)

    original_text = time_path.read_text(encoding="utf-8")
    payload = read_chunk_payload(time_path)
    if "lifespans" not in payload:
        return check_site(root)

    original = json.loads(json.dumps(payload, ensure_ascii=False))
    lifespans = payload.pop("lifespans")
    time_path.write_text(_replace_payload(original_text, payload), encoding="utf-8")
    life_path.write_text(_lifespans_script(lifespans), encoding="utf-8")

    time_after = read_chunk_payload(time_path)
    life_after = read_chunk_payload(life_path)
    reconstructed = dict(time_after)
    reconstructed.update(life_after)
    if reconstructed != original:
        raise RuntimeError("V11 time/lifespans 物理拆分不可逆")
    return check_site(root)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="V11：把 web data-time.js 的 lifespans 拆成独立资源")
    parser.add_argument("root", type=Path, nargs="?", default=Path("dist/full"))
    parser.add_argument("--check", action="store_true", help="只检查已拆分产物")
    args = parser.parse_args(argv)
    try:
        stats = check_site(args.root) if args.check else split_site(args.root)
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print("[FAIL] %s" % exc)
        return 1
    print(
        "V11 时间域分层通过：time %.1f KiB · lifespans %.1f KiB · %d 人"
        % (stats["time_bytes"] / 1024, stats["lifespans_bytes"] / 1024, stats["lifespans_count"])
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
