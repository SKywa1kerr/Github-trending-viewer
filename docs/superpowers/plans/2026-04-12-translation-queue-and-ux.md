# Translation Queue And UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decouple scrape refresh from translation, add reliable background translation with retries and provider abstraction, then expose better translation status and actions in the UI.

**Architecture:** Keep FastAPI and SQLite, but move translation into a background worker flow driven by project-level translation state. Refresh only scrapes and marks projects for translation; a translation service and worker consume pending/retry items with retry scheduling, while the frontend polls lightweight status and project state to update cards without full-page waiting.

**Tech Stack:** Python 3.11, FastAPI, SQLite, APScheduler, httpx, pytest, vanilla JS

---

### Task 1: Add translation state to the data model

**Files:**
- Modify: `app/database.py`
- Modify: `app/models.py`
- Test: `tests/test_database.py`

- [ ] **Step 1: Write the failing test**

```python
def test_init_db_adds_translation_state_columns(tmp_path, monkeypatch):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\test_database.py -q`
Expected: FAIL because the new columns do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
for sql in migration_sql:
    try:
        conn.execute(sql)
    except Exception:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests\test_database.py -q`
Expected: PASS

### Task 2: Introduce translation provider and service helpers

**Files:**
- Create: `app/translation_provider.py`
- Modify: `app/config.py`
- Test: `tests/test_translator.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_build_provider_from_config_uses_openai_compatible_defaults():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests\test_translator.py -q`
Expected: FAIL because provider construction and source signatures are missing.

- [ ] **Step 3: Write minimal implementation**

```python
def build_translation_provider():
    return OpenAICompatibleTranslationProvider(...)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests\test_translator.py -q`
Expected: PASS

### Task 3: Add translation queue selection, retries, and status updates

**Files:**
- Modify: `app/translator.py`
- Modify: `app/routers/system.py`
- Test: `tests/test_translator.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_pick_projects_for_translation_skips_done_without_source_change():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests\test_translator.py -q`
Expected: FAIL because queue logic and retry state handling do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
async def process_translation_queue(limit: int = 10):
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests\test_translator.py -q`
Expected: PASS

### Task 4: Decouple refresh from translation completion

**Files:**
- Modify: `app/routers/system.py`
- Modify: `app/main.py`
- Modify: `app/scheduler.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_refresh_starts_scrape_without_waiting_for_translation(client, monkeypatch):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests\test_api.py -q`
Expected: FAIL because refresh still waits for translation and status lacks queue counts.

- [ ] **Step 3: Write minimal implementation**

```python
async def _do_refresh():
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests\test_api.py -q`
Expected: PASS

### Task 5: Expose translation state in project APIs

**Files:**
- Modify: `app/models.py`
- Modify: `app/routers/projects.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing test**

```python
def test_projects_api_returns_translation_state_fields(client):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\test_api.py -q`
Expected: FAIL because project payloads do not include translation state.

- [ ] **Step 3: Write minimal implementation**

```python
return {
    ...
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests\test_api.py -q`
Expected: PASS

### Task 6: Add targeted retry endpoints and translation summary status

**Files:**
- Modify: `app/routers/system.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_retry_failed_translations_marks_retry_projects_pending(client):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests\test_api.py -q`
Expected: FAIL because the endpoint and summary fields do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
@router.post("/translations/retry-failed")
def retry_failed_translations():
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests\test_api.py -q`
Expected: PASS

### Task 7: Improve frontend translation status and refresh behavior

**Files:**
- Modify: `static/index.html`
- Modify: `static/js/app.js`
- Modify: `static/css/style.css`

- [ ] **Step 1: Add translation summary UI and retry control**
- [ ] **Step 2: Update project cards to show translation state**
- [ ] **Step 3: Poll lightweight status and refresh visible cards**
- [ ] **Step 4: Verify manually in browser**

### Task 8: Final verification

**Files:**
- Modify: `tests/test_api.py`
- Modify: `tests/test_database.py`
- Modify: `tests/test_translator.py`

- [ ] **Step 1: Run focused backend tests**
- [ ] **Step 2: Run the app and verify refresh behavior manually**
- [ ] **Step 3: Inspect for encoding regressions in touched files**
