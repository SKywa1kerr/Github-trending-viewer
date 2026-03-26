import pytest
from app.scraper import parse_trending_html, build_search_url


def test_build_search_url_with_topic():
    url = build_search_url(topic="machine-learning", sort="stars")
    assert "q=topic:machine-learning" in url
    assert "sort=stars" in url


def test_build_search_url_with_keyword():
    url = build_search_url(keyword="ai agent", sort="stars")
    assert "q=ai+agent" in url


def test_parse_trending_html_empty():
    result = parse_trending_html("<html><body></body></html>")
    assert result == []
