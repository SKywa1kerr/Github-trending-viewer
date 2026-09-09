from app.scorer import compute_score


def test_high_stars_high_growth():
    score = compute_score(stars=50000, stars_gained=1000,
                          last_updated="2026-03-26T00:00:00Z",
                          has_readme=True, has_topics=True)
    assert score > 0.7


def test_low_stars_no_growth():
    score = compute_score(stars=10, stars_gained=0,
                          last_updated="2024-01-01T00:00:00Z",
                          has_readme=False, has_topics=False)
    assert score < 0.3


def test_score_between_0_and_1():
    score = compute_score(stars=1000, stars_gained=50,
                          last_updated="2026-03-20T00:00:00Z",
                          has_readme=True, has_topics=True)
    assert 0 <= score <= 1


def test_update_all_scores_uses_readme_summary_presence(monkeypatch):
    import os
    from app import config as cfg
    from app.database import get_connection, init_db
    from app.scorer import update_all_scores

    db_path = os.path.join(os.getcwd(), "data", "test_scorer.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    monkeypatch.setattr(cfg.config, "DB_PATH", db_path)
    init_db()
    try:
        conn = get_connection()
        for name, summary in (("with/readme", "有摘要"), ("without/readme", "")):
            conn.execute(
                "INSERT INTO projects (repo_full_name, stars, stars_gained, last_updated, topics, readme_summary_zh) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (name, 1000, 50, "2026-09-01T00:00:00Z", '["ai"]', summary),
            )
        conn.commit()
        conn.close()

        update_all_scores()

        conn = get_connection()
        scores = {r["repo_full_name"]: r["score"] for r in conn.execute("SELECT repo_full_name, score FROM projects")}
        conn.close()

        # README contributes half of the 20% quality weight
        assert round(scores["with/readme"] - scores["without/readme"], 4) == 0.1
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
