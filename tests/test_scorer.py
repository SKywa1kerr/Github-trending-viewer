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
