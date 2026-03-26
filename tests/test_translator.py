import json
import pytest
from app.translator import build_translate_prompt, parse_translate_response


def test_build_translate_prompt():
    prompt = build_translate_prompt("test/repo", "A test project", "# README\nThis is a test.")
    assert "test/repo" in prompt
    assert "A test project" in prompt
    assert "README" in prompt


def test_parse_translate_response_valid_json():
    response = json.dumps({
        "description_zh": "测试项目",
        "readme_summary_zh": "这是一个测试项目的摘要。"
    })
    result = parse_translate_response(response)
    assert result["description_zh"] == "测试项目"
    assert result["readme_summary_zh"] == "这是一个测试项目的摘要。"


def test_parse_translate_response_invalid_json():
    result = parse_translate_response("not json at all")
    assert result["description_zh"] == ""
    assert result["readme_summary_zh"] == ""


def test_parse_translate_response_json_in_markdown():
    response = '```json\n{"description_zh": "测试", "readme_summary_zh": "摘要"}\n```'
    result = parse_translate_response(response)
    assert result["description_zh"] == "测试"
