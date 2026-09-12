"""源文件解析：把 ``docs/`` 的四份权威源文件解析成规范化中间数据。

解析内核不依赖 pandas / openpyxl，直接读取 OOXML（zip + XML），
以便对同一输入产生逐字节一致的结果。
"""

from __future__ import annotations

__all__ = ["ooxml", "parser", "emit"]
