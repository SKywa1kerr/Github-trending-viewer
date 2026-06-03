import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from app.ai_client import build_ai_client, extract_json_array
from app.database import get_connection
from app.models import ProjectImportIn
from app.scraper import fetch_readme, fetch_search_results, save_projects
from app.state_store import get_runtime_state, set_runtime_state

router = APIRouter(prefix="/api")


def _one_day_ago():
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")


def _build_project_dict(r, fav_ids):
    topics = json.loads(r["topics"]) if r["topics"] else []
    first_seen = r["first_seen_at"] if "first_seen_at" in r.keys() else ""
    is_new = bool(first_seen and first_seen > _one_day_ago())
    return {
        "id": r["id"],
        "repo_full_name": r["repo_full_name"],
        "description": r["description"],
        "description_zh": r["description_zh"],
        "readme_summary_zh": r["readme_summary_zh"],
        "translation_status": r["translation_status"] if "translation_status" in r.keys() else "",
        "translation_attempts": r["translation_attempts"] if "translation_attempts" in r.keys() else 0,
        "stars": r["stars"],
        "stars_gained": r["stars_gained"],
        "language": r["language"],
        "topics": topics,
        "category": r["category"],
        "repo_url": r["repo_url"],
        "score": r["score"],
        "last_updated": r["last_updated"],
        "fetched_at": r["fetched_at"],
        "is_favorited": r["id"] in fav_ids,
        "is_new": is_new,
    }


@router.get("/projects")
def list_projects(
    category: str = Query(None),
    language: str = Query(None),
    sort: str = Query("score"),
    q: str = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    conn = get_connection()

    # Load favorite IDs
    fav_ids = {r["project_id"] for r in conn.execute("SELECT project_id FROM favorites").fetchall()}

    conditions = []
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)
    if language:
        conditions.append("language = ?")
        params.append(language)
    if q:
        conditions.append("(repo_full_name LIKE ? OR description LIKE ? OR description_zh LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    sort_map = {
        "score": "score DESC",
        "stars": "stars DESC",
        "stars_gained": "stars_gained DESC",
        "updated": "last_updated DESC",
    }
    order = sort_map.get(sort, "score DESC")

    offset = (page - 1) * page_size

    total = conn.execute(f"SELECT COUNT(*) FROM projects {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT * FROM projects {where} ORDER BY {order} LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()

    items = [_build_project_dict(r, fav_ids) for r in rows]
    conn.close()
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/projects/{project_id}")
def get_project(project_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")
    fav_ids = {r["project_id"] for r in conn.execute("SELECT project_id FROM favorites").fetchall()}
    result = _build_project_dict(row, fav_ids)
    conn.close()
    return result


@router.post("/projects/import")
def import_project(project: ProjectImportIn):
    repo_full_name = (project.repo_full_name or "").strip()
    if not repo_full_name or "/" not in repo_full_name:
        raise HTTPException(status_code=400, detail="Invalid repo_full_name")

    save_projects([{
        "repo_full_name": repo_full_name,
        "description": project.description,
        "stars": project.stars,
        "stars_gained": project.stars_gained,
        "language": project.language,
        "topics": project.topics,
        "repo_url": project.repo_url or f"https://github.com/{repo_full_name}",
        "last_updated": project.last_updated,
    }], project.category or "other")

    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM projects WHERE repo_full_name = ?",
        (repo_full_name,),
    ).fetchone()
    fav_ids = {r["project_id"] for r in conn.execute("SELECT project_id FROM favorites").fetchall()}
    conn.close()

    if not row:
        raise HTTPException(status_code=500, detail="Failed to import project")
    return _build_project_dict(row, fav_ids)


@router.get("/star-history")
def get_star_history_batch(ids: str = Query(...)):
    """Get star history for multiple projects. ids=1,2,3"""
    project_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    if not project_ids:
        return {}
    conn = get_connection()
    result = {}
    placeholders = ",".join("?" * len(project_ids))
    rows = conn.execute(
        f"SELECT project_id, stars, recorded_date FROM star_history "
        f"WHERE project_id IN ({placeholders}) ORDER BY recorded_date",
        project_ids
    ).fetchall()
    conn.close()
    for r in rows:
        pid = str(r["project_id"])
        if pid not in result:
            result[pid] = []
        result[pid].append({"date": r["recorded_date"], "stars": r["stars"]})
    return result


@router.get("/search/github")
async def search_github(q: str = Query(..., min_length=1)):
    """Search GitHub directly and return results."""
    results = await fetch_search_results(keyword=q)
    items = []
    for p in results:
        items.append({
            "id": 0,
            "repo_full_name": p["repo_full_name"],
            "description": p.get("description", ""),
            "description_zh": "",
            "readme_summary_zh": "",
            "translation_status": "",
            "translation_attempts": 0,
            "stars": p.get("stars", 0),
            "stars_gained": p.get("stars_gained", 0),
            "language": p.get("language", ""),
            "topics": p.get("topics", []),
            "category": "",
            "repo_url": p.get("repo_url", ""),
            "score": 0,
            "last_updated": p.get("last_updated", ""),
            "fetched_at": "",
            "is_favorited": False,
            "is_new": False,
        })
    return {"total": len(items), "page": 1, "page_size": len(items), "items": items}


import hashlib


@router.get("/recommendations")
async def get_recommendations(force: bool = Query(False)):
    """Get AI-powered project recommendations based on favorites."""
    conn = get_connection()

    # Get favorite project IDs and info
    fav_rows = conn.execute(
        "SELECT p.id, p.repo_full_name, p.topics, p.language, p.description_zh, p.description "
        "FROM favorites f JOIN projects p ON f.project_id = p.id"
    ).fetchall()

    if not fav_rows:
        conn.close()
        return {"items": [], "message": "no_favorites"}

    fav_ids = {r["id"] for r in fav_rows}

    # Check if we need to regenerate
    runtime_state = get_runtime_state(
        "recommendation_fav_hash",
        "recommendation_generated_at",
    )
    cached_hash = runtime_state["recommendation_fav_hash"]
    cached_generated_at = runtime_state["recommendation_generated_at"]
    fav_hash = hashlib.md5(",".join(sorted(str(i) for i in fav_ids)).encode()).hexdigest()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    hours_since = 999
    if cached_generated_at:
        try:
            dt = datetime.strptime(cached_generated_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            hours_since = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        except ValueError:
            pass

    if not force and fav_hash == cached_hash and hours_since < 24:
        # Return cached recommendations
        rows = conn.execute(
            "SELECT r.project_id, r.reason, r.score, p.* FROM recommendations r "
            "JOIN projects p ON r.project_id = p.id ORDER BY r.score DESC LIMIT 10"
        ).fetchall()
        conn.close()
        items = []
        for r in rows:
            d = _build_project_dict(r, fav_ids)
            d["recommendation_reason"] = r["reason"]
            items.append(d)
        return {"items": items, "message": "ok"}

    # Phase 1: Tag + Language scoring
    fav_topics = set()
    fav_languages = set()
    for r in fav_rows:
        topics = json.loads(r["topics"]) if r["topics"] else []
        fav_topics.update(topics)
        if r["language"]:
            fav_languages.add(r["language"])

    all_projects = conn.execute(
        "SELECT id, repo_full_name, topics, language, description, description_zh FROM projects"
    ).fetchall()

    scored = []
    for p in all_projects:
        if p["id"] in fav_ids:
            continue
        topics = json.loads(p["topics"]) if p["topics"] else []
        shared = len(set(topics) & fav_topics)
        lang_match = 1 if p["language"] in fav_languages else 0
        score = shared * 2 + lang_match
        if score > 0:
            scored.append((p, score))

    scored.sort(key=lambda x: -x[1])
    candidates = scored[:20]

    if not candidates:
        conn.close()
        return {"items": [], "message": "no_matches"}

    # Phase 2: AI re-ranking
    fav_summary = "; ".join(
        f"{r['repo_full_name']}({r['description_zh'] or r['description'][:60]})"
        for r in fav_rows[:10]
    )
    candidate_text = "\n".join(
        f"- {c[0]['repo_full_name']}: {c[0]['description_zh'] or c[0]['description'][:80]} (匹配分:{c[1]})"
        for c in candidates
    )

    prompt = f"""用户收藏了这些项目: {fav_summary}

以下是候选推荐项目:
{candidate_text}

请从中选出最值得推荐的10个项目，按推荐度排序。对每个项目用一句简短的中文说明为什么推荐（结合用户兴趣）。
返回JSON数组格式: [{{"repo":"owner/name","reason":"推荐理由","score":95}}]
只返回JSON，不要其他内容。"""

    recommendations = []
    try:
        client = build_ai_client(timeout=60)
        data = await client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = data["choices"][0]["message"]["content"]
        recommendations = extract_json_array(content)
    except Exception:
        pass

    # Save to DB
    conn.execute("DELETE FROM recommendations")
    repo_to_id = {c[0]["repo_full_name"]: c[0]["id"] for c in candidates}

    if recommendations:
        for rec in recommendations[:10]:
            repo = rec.get("repo", "")
            pid = repo_to_id.get(repo)
            if pid:
                conn.execute(
                    "INSERT INTO recommendations (project_id, reason, score, generated_at) VALUES (?, ?, ?, ?)",
                    (pid, rec.get("reason", ""), rec.get("score", 0), now)
                )
    else:
        # Fallback: use tag-scored candidates without AI reason
        for c, s in candidates[:10]:
            conn.execute(
                "INSERT INTO recommendations (project_id, reason, score, generated_at) VALUES (?, ?, ?, ?)",
                (c["id"], "基于相似标签和语言推荐", s * 10, now)
            )

    conn.commit()
    set_runtime_state(
        recommendation_fav_hash=fav_hash,
        recommendation_generated_at=now,
    )

    # Return results
    rows = conn.execute(
        "SELECT r.project_id, r.reason, r.score, p.* FROM recommendations r "
        "JOIN projects p ON r.project_id = p.id ORDER BY r.score DESC LIMIT 10"
    ).fetchall()
    conn.close()
    items = []
    for r in rows:
        d = _build_project_dict(r, fav_ids)
        d["recommendation_reason"] = r["reason"]
        items.append(d)
    return {"items": items, "message": "ok"}


class ChatRequest(BaseModel):
    repo_full_name: str
    message: str
    history: list = Field(default_factory=list)


@router.post("/chat")
async def chat_about_project(req: ChatRequest):
    """Chat with AI about a specific project."""
    # Get project info from DB
    conn = get_connection()
    row = conn.execute(
        "SELECT description, description_zh, readme_summary_zh FROM projects WHERE repo_full_name = ?",
        (req.repo_full_name,)
    ).fetchone()
    conn.close()

    # Fetch README for richer context
    readme = await fetch_readme(req.repo_full_name)

    project_context = f"项目名: {req.repo_full_name}\n"
    if row:
        project_context += f"描述: {row['description']}\n"
        if row['description_zh']:
            project_context += f"中文描述: {row['description_zh']}\n"
        if row['readme_summary_zh']:
            project_context += f"README摘要: {row['readme_summary_zh']}\n"
    if readme:
        project_context += f"\nREADME 内容:\n{readme}\n"

    system_prompt = f"""你是一个 GitHub 项目助手，帮助用户深入了解开源项目。基于以下项目信息回答用户的问题。
用中文回答，简洁实用，重点突出。如果项目信息中没有相关内容，请如实说明。

{project_context}"""

    messages = [{"role": "system", "content": system_prompt}]
    for h in req.history[-6:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": req.message})

    async def generate():
        client = build_ai_client(timeout=60)
        async for content in client.stream_chat_completion(messages, temperature=0.5):
            yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
