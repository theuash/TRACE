import pytest

from llm.client import extract_json_object


def test_plain_json():
    assert extract_json_object('{"total_assets": "120,500"}') == {"total_assets": "120,500"}


def test_code_fence_and_prose_are_tolerated():
    text = 'Sure!\n```json\n{"revenue": "1,234"}\n```\nDone.'
    assert extract_json_object(text) == {"revenue": "1,234"}


def test_no_object_raises():
    with pytest.raises(ValueError):
        extract_json_object("I could not find anything.")
