import asyncio
import json
import os
import time

import pytest

from app import config as cfg
from app.database import get_connection, init_db
from app.translator import build_translate_prompt, parse_translate_response


@pytest.fixture(autouse=True)
def temp_db(monkeypatch):
    db_path = os.path.join(os.getcwd(), "data", "test_translator.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    monkeypatch.setattr(cfg.config, "DB_PATH", db_path)
    init_db()
    yield db_path
    if os.path.exists(db_path):
        os.remove(db_path)


def test_build_translate_prompt():
    prompt = build_translate_prompt("test/repo", "A test project", "# README\nThis is a test.")
    assert "test/repo" in prompt
    assert "A test project" in prompt
    assert "README" in prompt


def test_build_translate_prompt_respects_readme_char_limit(monkeypatch):
    monkeypatch.setattr(cfg.config, "TRANSLATION_README_CHARS", 10)

    prompt = build_translate_prompt("test/repo", "A test project", "x" * 20)

    assert "x" * 10 in prompt
    assert "x" * 11 not in prompt


def test_parse_translate_response_valid_json():
    response = json.dumps({
        "description_zh": "\u6d4b\u8bd5\u9879\u76ee",
        "readme_summary_zh": "\u8fd9\u662f\u6d4b\u8bd5\u9879\u76ee\u7684\u6458\u8981",
    })
    result = parse_translate_response(response)
    assert result["description_zh"] == "\u6d4b\u8bd5\u9879\u76ee"
    assert result["readme_summary_zh"] == "\u8fd9\u662f\u6d4b\u8bd5\u9879\u76ee\u7684\u6458\u8981"


def test_parse_translate_response_handles_list_values():
    response = json.dumps({
        "description_zh": ["\u6d4b\u8bd5", "\u9879\u76ee"],
        "readme_summary_zh": ["\u7b2c\u4e00\u70b9", "\u7b2c\u4e8c\u70b9"],
    })

    result = parse_translate_response(response)

    assert result["description_zh"] == "\u6d4b\u8bd5\n\u9879\u76ee"
    assert result["readme_summary_zh"] == "\u7b2c\u4e00\u70b9\n\u7b2c\u4e8c\u70b9"


def test_parse_translate_response_invalid_json():
    result = parse_translate_response("not json at all")
    assert result["description_zh"] == ""
    assert result["readme_summary_zh"] == ""


def test_parse_translate_response_json_in_markdown():
    response = '```json\n{"description_zh": "\\u6d4b\\u8bd5", "readme_summary_zh": "\\u6458\\u8981"}\n```'
    result = parse_translate_response(response)
    assert result["description_zh"] == "\u6d4b\u8bd5"


def test_make_source_signature_changes_when_inputs_change():
    from app.translator import make_source_signature

    first = make_source_signature("test/repo", "desc", "readme one")
    second = make_source_signature("test/repo", "desc", "readme two")

    assert first != second


def test_build_translation_provider_uses_openai_compatible_defaults():
    from app.translation_provider import build_translation_provider

    provider = build_translation_provider()

    assert provider.name == "openai-compatible"


def test_select_translation_candidates_returns_pending_and_due_retry_rows():
    from app.translator import select_translation_candidates

    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status) VALUES (?, ?, ?)",
        ("pending/repo", "https://github.com/pending/repo", "pending"),
    )
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status, translation_next_retry_at) "
        "VALUES (?, ?, ?, datetime('now', '-5 minutes'))",
        ("retry/repo", "https://github.com/retry/repo", "retry"),
    )
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status, translation_next_retry_at) "
        "VALUES (?, ?, ?, datetime('now', '+5 minutes'))",
        ("future/repo", "https://github.com/future/repo", "retry"),
    )
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status) VALUES (?, ?, ?)",
        ("done/repo", "https://github.com/done/repo", "done"),
    )
    conn.commit()
    conn.close()

    rows = select_translation_candidates(limit=10)
    repo_names = {row["repo_full_name"] for row in rows}

    assert repo_names == {"pending/repo", "retry/repo"}


def test_reset_processing_translations_returns_interrupted_rows_to_pending():
    from app.translator import reset_processing_translations

    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status) VALUES (?, ?, ?)",
        ("processing/repo", "https://github.com/processing/repo", "processing"),
    )
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, translation_status) VALUES (?, ?, ?)",
        ("done/repo", "https://github.com/done/repo", "done"),
    )
    conn.commit()
    conn.close()

    changed = reset_processing_translations()

    conn = get_connection()
    rows = conn.execute(
        "SELECT repo_full_name, translation_status FROM projects ORDER BY repo_full_name"
    ).fetchall()
    conn.close()

    assert changed == 1
    assert [(row["repo_full_name"], row["translation_status"]) for row in rows] == [
        ("done/repo", "done"),
        ("processing/repo", "pending"),
    ]


def test_translate_project_row_marks_done_on_success(monkeypatch):
    from app.translator import select_translation_candidates, translate_project_row

    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, description, translation_status) "
        "VALUES (?, ?, ?, ?)",
        ("success/repo", "https://github.com/success/repo", "test project", "pending"),
    )
    conn.commit()
    conn.close()

    async def fake_fetch_readme(repo_full_name):
        return "# README\nhello"

    async def fake_translate_project(repo_name, description, readme):
        return {"description_zh": "\u4e2d\u6587\u7b80\u4ecb", "readme_summary_zh": "\u4e2d\u6587\u6458\u8981"}

    monkeypatch.setattr("app.translator.fetch_readme_for_translation", fake_fetch_readme)
    monkeypatch.setattr("app.translator.translate_project", fake_translate_project)

    row = select_translation_candidates(limit=1)[0]
    asyncio.run(translate_project_row(row))

    conn = get_connection()
    saved = conn.execute(
        "SELECT translation_status, description_zh, readme_summary_zh, translated_signature "
        "FROM projects WHERE repo_full_name = ?",
        ("success/repo",),
    ).fetchone()
    conn.close()

    assert saved["translation_status"] == "done"
    assert saved["description_zh"] == "\u4e2d\u6587\u7b80\u4ecb"
    assert saved["readme_summary_zh"] == "\u4e2d\u6587\u6458\u8981"
    assert saved["translated_signature"]


def test_translate_project_row_marks_retry_on_retryable_error(monkeypatch):
    from app.translator import (
        TranslationRetryableError,
        select_translation_candidates,
        translate_project_row,
    )

    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, description, translation_status) "
        "VALUES (?, ?, ?, ?)",
        ("retryable/repo", "https://github.com/retryable/repo", "test project", "pending"),
    )
    conn.commit()
    conn.close()

    async def fake_fetch_readme(repo_full_name):
        return "# README\nhello"

    async def fake_translate_project(repo_name, description, readme):
        raise TranslationRetryableError("provider timeout")

    monkeypatch.setattr("app.translator.fetch_readme_for_translation", fake_fetch_readme)
    monkeypatch.setattr("app.translator.translate_project", fake_translate_project)

    row = select_translation_candidates(limit=1)[0]
    asyncio.run(translate_project_row(row))

    conn = get_connection()
    saved = conn.execute(
        "SELECT translation_status, translation_attempts, translation_error, translation_next_retry_at "
        "FROM projects WHERE repo_full_name = ?",
        ("retryable/repo",),
    ).fetchone()
    conn.close()

    assert saved["translation_status"] == "retry"
    assert saved["translation_attempts"] == 1
    assert "timeout" in saved["translation_error"]
    assert saved["translation_next_retry_at"]


def test_translate_project_row_does_not_spend_attempt_on_rate_limit(monkeypatch):
    from app.translator import (
        TranslationRetryableError,
        select_translation_candidates,
        translate_project_row,
    )

    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, description, translation_status, translation_attempts) "
        "VALUES (?, ?, ?, ?, ?)",
        ("rate-limit/repo", "https://github.com/rate-limit/repo", "test project", "pending", 2),
    )
    conn.commit()
    conn.close()

    async def fake_fetch_readme(repo_full_name):
        return "# README\nhello"

    async def fake_translate_project(repo_name, description, readme):
        raise TranslationRetryableError("429 Too Many Requests")

    monkeypatch.setattr("app.translator.fetch_readme_for_translation", fake_fetch_readme)
    monkeypatch.setattr("app.translator.translate_project", fake_translate_project)

    row = select_translation_candidates(limit=1)[0]
    asyncio.run(translate_project_row(row))

    conn = get_connection()
    saved = conn.execute(
        "SELECT translation_status, translation_attempts, translation_error, translation_next_retry_at "
        "FROM projects WHERE repo_full_name = ?",
        ("rate-limit/repo",),
    ).fetchone()
    conn.close()

    assert saved["translation_status"] == "retry"
    assert saved["translation_attempts"] == 2
    assert "429" in saved["translation_error"]
    assert saved["translation_next_retry_at"]


def test_translate_project_row_marks_retry_on_unexpected_error(monkeypatch):
    from app.translator import select_translation_candidates, translate_project_row

    conn = get_connection()
    conn.execute(
        "INSERT INTO projects (repo_full_name, repo_url, description, translation_status) "
        "VALUES (?, ?, ?, ?)",
        ("unexpected/repo", "https://github.com/unexpected/repo", "test project", "pending"),
    )
    conn.commit()
    conn.close()

    async def fake_fetch_readme(repo_full_name):
        return "# README\nhello"

    async def fake_translate_project(repo_name, description, readme):
        raise ValueError("bad provider payload")

    monkeypatch.setattr("app.translator.fetch_readme_for_translation", fake_fetch_readme)
    monkeypatch.setattr("app.translator.translate_project", fake_translate_project)

    row = select_translation_candidates(limit=1)[0]
    asyncio.run(translate_project_row(row))

    conn = get_connection()
    saved = conn.execute(
        "SELECT translation_status, translation_attempts, translation_error "
        "FROM projects WHERE repo_full_name = ?",
        ("unexpected/repo",),
    ).fetchone()
    conn.close()

    assert saved["translation_status"] == "retry"
    assert saved["translation_attempts"] == 1
    assert "bad provider payload" in saved["translation_error"]


def test_translate_project_uses_persisted_daily_budget(monkeypatch):
    from app.state_store import set_runtime_state
    from app.translator import TranslationRetryableError, translate_project

    set_runtime_state(
        translation_daily_tokens_used=str(cfg.config.MAX_DAILY_TOKENS),
        translation_budget_date=time.strftime("%Y-%m-%d"),
    )

    with pytest.raises(TranslationRetryableError, match="daily token budget reached"):
        asyncio.run(translate_project("budget/repo", "desc", "readme"))


def test_translate_project_persists_token_usage(monkeypatch):
    from app.state_store import get_runtime_value
    from app.translator import translate_project

    class FakeProvider:
        async def translate(self, prompt: str):
            return {
                "choices": [{"message": {"content": json.dumps({
                    "description_zh": "\u4e2d\u6587\u7b80\u4ecb",
                    "readme_summary_zh": "\u4e2d\u6587\u6458\u8981",
                })}}],
                "usage": {"total_tokens": 123},
            }

    monkeypatch.setattr("app.translator.build_translation_provider", lambda: FakeProvider())

    result = asyncio.run(translate_project("persist/repo", "desc", "readme"))

    assert result["description_zh"] == "\u4e2d\u6587\u7b80\u4ecb"
    assert get_runtime_value("translation_daily_tokens_used") == "123"
    assert get_runtime_value("translation_budget_date") == time.strftime("%Y-%m-%d")


def test_start_translation_worker_updates_runtime_state(monkeypatch):
    import app.translator as translator_module
    from app.state_store import get_runtime_bool

    async def fake_worker():
        await asyncio.sleep(0)

    monkeypatch.setattr(translator_module, "run_translation_worker", fake_worker)

    async def scenario():
        started = translator_module.start_translation_worker()
        assert started is True
        assert get_runtime_bool("translation_worker_running") is True
        await translator_module._worker_task
        assert get_runtime_bool("translation_worker_running") is False

    asyncio.run(scenario())


def test_parse_translate_response_tolerates_think_tags_and_prose():
    response = (
        "<think>Let me translate.</think>\n"
        "Here you go:\n"
        '{"description_zh": "一个命令行工具", "readme_summary_zh": ["功能一", "功能二"]}\n'
        "Hope this helps."
    )

    result = parse_translate_response(response)

    assert result["description_zh"] == "一个命令行工具"
    assert result["readme_summary_zh"] == "功能一\n功能二"


def test_translate_project_requests_json_mode_and_strips_thinking(monkeypatch):
    from app.translator import translate_project

    captured = {}

    class FakeClient:
        async def chat_completion(self, messages, *, temperature=0.3, max_tokens=None, json_mode=False):
            captured["json_mode"] = json_mode
            captured["max_tokens"] = max_tokens
            return {
                "choices": [{"message": {
                    "reasoning_content": "hidden reasoning",
                    "content": '<think>x</think>{"description_zh": "简介", "readme_summary_zh": "摘要"}',
                }}],
                "usage": {"total_tokens": 10},
            }

    class FakeProvider:
        def __init__(self):
            self.client = FakeClient()

        async def translate(self, prompt, temperature=0.3):
            return await self.client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=cfg.config.TRANSLATION_MAX_OUTPUT_TOKENS,
                json_mode=True,
            )

    monkeypatch.setattr("app.translator.build_translation_provider", lambda: FakeProvider())

    result = asyncio.run(translate_project("x/y", "desc", "readme"))

    assert captured["json_mode"] is True
    assert captured["max_tokens"] == cfg.config.TRANSLATION_MAX_OUTPUT_TOKENS
    assert result == {"description_zh": "简介", "readme_summary_zh": "摘要"}


def test_openai_provider_requests_json_mode(monkeypatch):
    from app.translation_provider import OpenAICompatibleTranslationProvider

    captured = {}

    class FakeClient:
        async def chat_completion(self, messages, *, temperature=0.3, max_tokens=None, json_mode=False):
            captured["json_mode"] = json_mode
            return {"choices": [{"message": {"content": "{}"}}]}

    provider = OpenAICompatibleTranslationProvider(endpoint="e", api_key="k", model="qwen")
    provider.client = FakeClient()

    asyncio.run(provider.translate("prompt"))

    assert captured["json_mode"] is True
