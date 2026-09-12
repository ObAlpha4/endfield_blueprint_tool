"""源数据校验入口（兼容壳）。

真正的实现已经并入解析器 ``endfield.sources.parser``（阶段 2 步骤 1「统一数据入口」）：
设备表「四面接口串分词格数 = 宽/高」、配方表结构、发电表数值等断言全部在那里执行，
并且额外产出规范化中间数据 ``data/derived/sources.json``。

本脚本只保留一个稳定入口，避免出现两份互相漂移的校验逻辑。

用法（从仓库根目录运行）：

    .venv\\Scripts\\python.exe tools\\validate_sources.py            # 只校验
    .venv\\Scripts\\python.exe -m endfield.cli check                 # 等价写法
    .venv\\Scripts\\python.exe -m endfield.cli build                 # 校验并写出规范 JSON
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from endfield.cli import main as cli_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    return cli_main(["check", *arguments])


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 控制台默认 GBK
    sys.exit(main())
