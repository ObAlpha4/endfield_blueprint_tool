"""终末地产线规划器 —— 领域模型与解析器（阶段 2）。

包结构：

- ``endfield.sources``：四份源文件（xlsx / docx）的解析与规范化中间数据导出。
- ``endfield.domain``：领域模型（几何、设备、配方、物流元件、蓝图）。
- ``endfield.items``：物品清单与品类（solid / liquid / gas）。
- ``endfield.cli``：命令行入口。

设计依据：``design/domain-model.md``（实体与字段）、``design/global-constraints.md``（G-001）。
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.2.0"
