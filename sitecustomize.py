# 本仓库的测试与脚本需要能导入 `src/endfield`。
#
# 首选做法是在命令行显式设置：
#     $env:PYTHONPATH = "$PWD\src"
#
# 本文件的唯一作用：在「`site` 自动导入 `sitecustomize`」的 Python 构建上，
# 让 `python -m ...` / `python -c ...` 从仓库根目录运行时无需再设 PYTHONPATH。
# 它不会被 `python script.py` 自动加载（那类入口见 `tools/*.py` 与 `tests/__init__.py`
# 里各自的 sys.path 处理），因此不作为唯一手段。
"""自动把 `src/` 加入 sys.path（站点自定义钩子）。"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
