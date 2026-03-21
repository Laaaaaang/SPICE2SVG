"""词法分析器测试。"""

import pytest
from spice2svg.parser.tokenizer import tokenize


class TestTokenize:
    def test_simple_lines(self):
        text = "R1 VIN VOUT 10k\nC1 VOUT 0 10nF\n.end"
        lines = tokenize(text)
        texts = [l.text for l in lines]
        assert "R1 VIN VOUT 10k" in texts
        assert "C1 VOUT 0 10nF" in texts

    def test_comment_lines_skipped(self):
        text = "* Title\n* This is a comment\nR1 VIN VOUT 10k\n.end"
        lines = tokenize(text)
        # 非 title 的注释行应被过滤
        texts = [l.text for l in lines]
        assert not any("This is a comment" in t for t in texts[1:])

    def test_title_preserved(self):
        text = "* My Circuit Title\nR1 A B 10k\n.end"
        lines = tokenize(text)
        assert lines[0].text.startswith("*")
        assert "My Circuit Title" in lines[0].text

    def test_inline_comments_semicolon(self):
        text = "R1 VIN VOUT 10k ; this is a comment\n.end"
        lines = tokenize(text)
        assert lines[0].text == "R1 VIN VOUT 10k"

    def test_inline_comments_dollar(self):
        text = "R1 A B 10k $ HSPICE comment\n.end"
        lines = tokenize(text)
        assert lines[0].text == "R1 A B 10k"

    def test_line_continuation(self):
        text = "R1 VIN VOUT\n+ 10k\n.end"
        lines = tokenize(text)
        assert lines[0].text == "R1 VIN VOUT 10k"

    def test_multiple_continuations(self):
        text = "M1 D G\n+ S B\n+ NMOD W=1u\n.end"
        lines = tokenize(text)
        assert lines[0].text == "M1 D G S B NMOD W=1u"

    def test_empty_lines_skipped(self):
        text = "R1 A B 10k\n\n\nC1 B 0 1nF\n.end"
        lines = tokenize(text)
        texts = [l.text for l in lines]
        assert "R1 A B 10k" in texts
        assert "C1 B 0 1nF" in texts

    def test_line_numbers_tracked(self):
        text = "* Title\nR1 A B 10k\n\nC1 B 0 1nF\n.end"
        lines = tokenize(text)
        # title at line 1, R1 at line 2, C1 at line 4
        assert lines[0].line_number == 1
        assert lines[1].line_number == 2
        assert lines[2].line_number == 4
