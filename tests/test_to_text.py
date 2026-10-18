from __future__ import annotations

import json

from ochi.browser import to_text, wrap


def test_string_passes_through():
    assert to_text("hello", 100) == "hello"


def test_items_become_one_line_each_after_a_header():
    out = to_text({"total": 2, "items": [{"a": 1}, {"b": "ü"}]}, 1000).splitlines()
    assert json.loads(out[0]) == {"total": 2}
    assert out[1:] == ['{"a": 1}', '{"b": "ü"}']


def test_list_and_other_json():
    assert to_text([1, {"x": 2}], 100) == '1\n{"x": 2}'
    assert json.loads(to_text({"x": [1, 2]}, 100)) == {"x": [1, 2]}
    assert to_text(None, 100) == "null"


def test_truncation_reports_full_length():
    out = to_text("x" * 50, 10)
    assert out.startswith("x" * 10)
    assert "[truncated, 50 chars total]" in out


def test_wrap_returns_extract_result():
    js = wrap("async function extract() { return 42; }")
    assert js.startswith("async () => {")
    assert js.rstrip().endswith("return await extract();\n}")
