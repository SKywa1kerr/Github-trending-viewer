import httpx
import json
import re
import time
import asyncio
from app.config import config
from app.database import get_connection

_daily_tokens_used = 0
_last_reset_date = ""


def build_translate_prompt(repo_name: str, description: str, readme: str) -> str:
    return f"""你是一个技术项目翻译助手。请将以下 GitHub 项目信息翻译为中文。

项目名：{repo_name}
项目描述：{description}
README 内容：{readme[:3000]}

请返回 JSON 格式：
{{
  "description_zh": "中文简介（1-2句）",
  "readme_summary_zh": "README 中文摘要（3-5句，涵盖核心功能、使用场景、亮点）"
}}"""


def parse_translate_response(text: str) -> dict:
    default = {"description_zh": "", "readme_summary_zh": ""}
    # 尝试从 markdown 代码块中提取 JSON
    md_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if md_match:
        text = md_match.group(1)
    try:
        data = json.loads(text)
        return {
            "description_zh": data.get("description_zh", ""),
            "readme_summary_zh": data.get("readme_summary_zh", "")
        }
    except (json.JSONDecodeError, TypeError):
        return default


async def translate_project(repo_name: str, description: str, readme: str) -> dict:
    global _daily_tokens_used, _last_reset_date
    today = time.strftime("%Y-%m-%d")
    if _last_reset_date != today:
        _daily_tokens_used = 0
        _last_reset_date = today
    if _daily_tokens_used >= config.MAX_DAILY_TOKENS:
        return {"description_zh": "", "readme_summary_zh": ""}

    prompt = build_translate_prompt(repo_name, description, readme)
    payload = {
        "model": config.API_MODEL,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
    }
    headers = {
        "Authorization": f"Bearer {config.API_KEY}",
        "Content-Type": "application/json"
    }
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(config.API_ENDPOINT, json=payload, headers=headers)
            if resp.status_code != 200:
                return {"description_zh": "", "readme_summary_zh": ""}
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            _daily_tokens_used += usage.get("total_tokens", 0)
            return parse_translate_response(content)
    except Exception:
        return {"description_zh": "", "readme_summary_zh": ""}


async def translate_untranslated_projects():
    from app.scraper import fetch_readme

    conn = get_connection()
    rows = conn.execute(
        "SELECT id, repo_full_name, description FROM projects "
        "WHERE description_zh = '' OR description_zh IS NULL "
        "LIMIT 50"
    ).fetchall()
    conn.close()

    for row in rows:
        readme = await fetch_readme(row["repo_full_name"])
        result = await translate_project(row["repo_full_name"], row["description"], readme)
        if result["description_zh"]:
            conn = get_connection()
            conn.execute(
                "UPDATE projects SET description_zh = ?, readme_summary_zh = ?, "
                "translated_at = datetime('now') WHERE id = ?",
                (result["description_zh"], result["readme_summary_zh"], row["id"])
            )
            conn.commit()
            conn.close()
        # 频率控制: 30 次/分钟 = 每 2 秒一次
        await asyncio.sleep(2)
