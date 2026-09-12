"""端口串分词：``n`` 占 1 字符，其余标记占 2 字符。

历史缺陷：按固定 2 字符切分会把 ``nfin`` 切成 ``nf`` / ``in``，
把 ``nnfinn`` 压成 ``nfnn``，导致「格数 = 宽/高」断言失守（baseline §4.2）。
"""

from __future__ import annotations

import unittest

from endfield.sources.ooxml import tokenize


class TokenizeTests(unittest.TestCase):
    def test_n_takes_one_character(self) -> None:
        self.assertEqual(tokenize("nfin"), ["n", "fi", "n"])
        self.assertEqual(tokenize("nfinfin"), ["n", "fi", "n", "fi", "n"])
        # 协议核心北面权威值：n + 7×si + n = 9 个标记，正好 9 格。
        self.assertEqual(
            tokenize("nsisisisisisisin"),
            ["n", "si", "si", "si", "si", "si", "si", "si", "n"],
        )

    def test_repeated_double_markers(self) -> None:
        self.assertEqual(tokenize("sisisi"), ["si", "si", "si"])
        self.assertEqual(tokenize("sososo"), ["so", "so", "so"])
        self.assertEqual(len(tokenize("sisisisisisi")), 6)
        self.assertEqual(len(tokenize("sosososososo")), 6)

    def test_all_n(self) -> None:
        self.assertEqual(tokenize("nnnnnnnnn"), ["n"] * 9)
        self.assertEqual(tokenize(""), [])

    def test_the_historical_typo_differs(self) -> None:
        # `nnfinn`（权威，5 格）与 `nfnn`（曾经的错误写法，3 格）分词结果不同，断言必须能区分。
        self.assertEqual(len(tokenize("nnfinn")), 5)
        self.assertEqual(tokenize("nnfinn"), ["n", "n", "fi", "n", "n"])
        self.assertEqual(len(tokenize("nfnn")), 3)
        # 掉字符后 `f` 被当成未知标记的 2 字符块 `fn`，两种错误都必须能被断言发现。
        self.assertEqual(tokenize("nfnn"), ["n", "fn", "n"])

    def test_nsonnsonnson(self) -> None:
        # 协议核心西/东面权威值：9 格，其中 3 个 so。
        tokens = tokenize("nsonnsonnson")
        self.assertEqual(len(tokens), 9)
        self.assertEqual(tokens.count("so"), 3)


if __name__ == "__main__":
    unittest.main()
