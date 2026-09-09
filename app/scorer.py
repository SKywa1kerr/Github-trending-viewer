import math
from datetime import datetime, timezone


def compute_score(stars: int, stars_gained: int,
                  last_updated: str, has_readme: bool, has_topics: bool) -> float:
    # Star 总数 (30%) — 对数归一化，10万星为满分
    star_score = min(math.log10(max(stars, 1)) / 5.0, 1.0)

    # Star 增长速度 (30%) — 对数归一化，1000 新增为满分
    growth_score = min(math.log10(max(stars_gained, 1)) / 3.0, 1.0)

    # 最近更新活跃度 (20%) — 7天内满分，逐渐衰减
    try:
        updated = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        days_ago = (datetime.now(timezone.utc) - updated).days
        recency_score = max(1.0 - days_ago / 180.0, 0.0)
    except (ValueError, TypeError):
        recency_score = 0.0

    # 项目质量 (20%)
    quality_score = 0.0
    if has_readme:
        quality_score += 0.5
    if has_topics:
        quality_score += 0.5

    total = (star_score * 0.3 + growth_score * 0.3 +
             recency_score * 0.2 + quality_score * 0.2)
    return round(min(total, 1.0), 4)


def update_all_scores():
    from app.database import get_connection
    import json
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, stars, stars_gained, last_updated, topics, readme_summary_zh, readme_fetched_at FROM projects"
    ).fetchall()
    for row in rows:
        topics = json.loads(row["topics"]) if row["topics"] else []
        # README 质量信号：已生成中文摘要，或抓取过 README 并成功翻译
        has_readme = bool((row["readme_summary_zh"] or "").strip())
        score = compute_score(
            stars=row["stars"],
            stars_gained=row["stars_gained"],
            last_updated=row["last_updated"],
            has_readme=has_readme,
            has_topics=len(topics) > 0
        )
        conn.execute("UPDATE projects SET score = ? WHERE id = ?", (score, row["id"]))
    conn.commit()
    conn.close()
