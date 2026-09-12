"""命令行入口：生成 / 校验规范化中间数据。

用法（仓库根目录）：

    .venv\\Scripts\\python.exe -m endfield.cli build     # 解析源文件并写 data/derived/sources.json
    .venv\\Scripts\\python.exe -m endfield.cli check     # 只跑断言，不写文件
    .venv\\Scripts\\python.exe -m endfield.cli repeat    # 连跑两次，校验逐字节可重复

退出码：0 成功；1 校验失败；2 用法错误。
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

from endfield.sources import emit
from endfield.sources.parser import SourceParseError, parse_sources

#: 仓库根目录（本文件位于 ``<root>/src/endfield/cli.py``）。
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DOCS_DIR = REPO_ROOT / "docs"
DEFAULT_OUT = REPO_ROOT / "data" / "derived" / "sources.json"


def _configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def _parse(docs_dir: Path):
    try:
        return parse_sources(docs_dir)
    except SourceParseError as exc:
        print(f"[FAIL] {exc}")
        return None


def cmd_check(args: argparse.Namespace) -> int:
    bundle = _parse(args.docs_dir)
    if bundle is None:
        return 1
    print(f"[ OK ] 源文件校验通过（{len(bundle.device_types)} 设备 + {len(bundle.special_devices)} 特殊设备，"
          f"{len(bundle.recipes)} 配方，{len(bundle.power_entries)} 发电条目，{len(bundle.items)} 物料）")
    for line in bundle.report.checks:
        print(f"       · {line}")
    for line in bundle.report.warnings:
        print(f"       ! {line}")
    if bundle.report.normalizations:
        print(f"       · 规范化改写 {len(bundle.report.normalizations)} 处：")
        for item in bundle.report.normalizations:
            print(f"         - {item['file']} {item['sheet']} 行{item['row']} 列{item['column']}: {item['raw']!r} → {item['canonical']!r}")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    bundle = _parse(args.docs_dir)
    if bundle is None:
        return 1
    document = emit.build_document(bundle)
    digest, size = emit.write(document, args.out)
    print(f"[ OK ] 已写入 {args.out}")
    print(f"       sha256 {digest}")
    print(f"       字节数 {size}")
    for line in bundle.report.checks:
        print(f"       · {line}")
    return 0


def cmd_repeat(args: argparse.Namespace) -> int:
    digests: list[str] = []
    for _ in range(2):
        bundle = _parse(args.docs_dir)
        if bundle is None:
            return 1
        digests.append(hashlib.sha256(emit.dumps(emit.build_document(bundle)).encode("utf-8")).hexdigest())
    if digests[0] != digests[1]:
        print(f"[FAIL] 两次解析结果不一致：{digests[0]} vs {digests[1]}")
        return 1
    print(f"[ OK ] 逐字节可重复：sha256 {digests[0]}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="endfield.cli", description="终末地产线规划器 —— 源文件解析与规范化数据")
    parser.add_argument("--docs", dest="docs_dir", type=Path, default=DEFAULT_DOCS_DIR, help="docs/ 目录")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="只跑断言，不写文件")
    check.set_defaults(func=cmd_check)

    build = sub.add_parser("build", help="写出规范化 JSON（默认 data/derived/sources.json）")
    build.add_argument("--out", type=Path, default=DEFAULT_OUT, help="输出路径")
    build.set_defaults(func=cmd_build)

    repeat = sub.add_parser("repeat", help="连跑两次并校验逐字节可重复")
    repeat.set_defaults(func=cmd_repeat)
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdout()
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
