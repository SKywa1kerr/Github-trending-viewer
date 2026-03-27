# Star Trends & Smart Recommendations Design

## Feature 1: Star Trend Sparklines

### Data Layer
- New table `star_history(id, project_id, stars, recorded_date)` with unique constraint on `(project_id, recorded_date)`
- On each scrape refresh, insert/update today's star count for every project
- No historical backfill; data accumulates from first run onward

### API
- `GET /api/projects/{id}/star-history` returns `[{date, stars}, ...]` for last 30 days
- Batch endpoint `GET /api/star-history?ids=1,2,3` to avoid N+1 when rendering project list

### Frontend
- Pure SVG sparkline (~80x24px) rendered inline next to star count
- Green line if trending up, red if down, gray if flat/insufficient data
- Minimum 2 data points required to draw; show nothing if only 1 day of data
- SVG generated client-side from history data

## Feature 2: Smart Recommendations

### Matching Strategy (two-phase)
1. **Tag+Language scoring**: For each non-favorited project, count overlapping topics and language matches with user's favorited projects. Score = (shared_topics * 2) + (same_language * 1). Take top 20 candidates.
2. **AI re-ranking**: Send top 20 candidates + user's favorites summary to DeepSeek. Ask for top 10 ranked results with one-line recommendation reason in Chinese.

### Data Layer
- New table `recommendations(id, project_id, reason, score, generated_at)`
- Cache results; regenerate only if favorites change or 24 hours pass
- Track `last_recommendation_hash` (hash of favorite project IDs) to detect changes

### API
- `GET /api/recommendations` returns recommended projects with AI-generated reasons
- Triggers regeneration if stale or favorites changed

### Frontend
- New tab "为你推荐" between "其他热门" and "收藏"
- Same card layout as other tabs, with added recommendation reason badge
- If no favorites yet, show prompt: "收藏一些项目后，AI 会为你推荐相似项目"
- Loading state while AI generates recommendations

## Scope Exclusions
- No historical star data backfill
- No third-party charting library
- No real-time recommendation computation on every page load
