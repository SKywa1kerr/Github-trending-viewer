# UI Polish & Maintainability Design

## Goal

Improve the existing GitHub Trending Viewer without changing its core product model. The work should make the app feel more polished as a local desktop/mobile tool while reducing risk in the large vanilla JavaScript frontend and tightening a few backend/API consistency edges.

## Current Context

- The app is FastAPI + SQLite with a static HTML/CSS/JS frontend.
- Current functionality already includes category browsing, language and text filters, GitHub search import, favorites, AI recommendations, project chat, translation queue status, health diagnostics, refresh progress, and theme switching.
- The working tree contains many existing uncommitted changes. Implementation must stage only files changed for this optimization and must not revert unrelated changes.
- No build tooling should be introduced for this pass.

## Recommended Approach

Use an incremental "polish and structure" pass:

1. Keep the current warm modernist visual direction.
2. Improve hierarchy, spacing, responsive behavior, and state presentation.
3. Refactor only the frontend code directly touched by these UI changes.
4. Add focused regression tests for changed behavior and existing high-risk flows.

This avoids a full application layout rewrite while making the product noticeably cleaner and easier to maintain.

## UI Scope

### Header And Status Area

- Keep the existing header identity, but reduce visual competition between header, overview cards, translation status, and health warnings.
- Make status content easier to scan by using concise labels and stable dimensions.
- Ensure stale data, refresh failure, translation queue, and health warnings remain visible but do not dominate normal browsing.

### Filters And Navigation

- Make category tabs and filters more resilient on small screens.
- Avoid horizontal overflow in mobile layouts.
- Keep GitHub search distinct from local filtering so users understand which dataset they are viewing.
- Preserve the current category model: AI, tools, devtools, other, recommend, favorites.

### Project Cards

- Reduce crowding in the card header by grouping actions, metadata, and repository identity more clearly.
- Keep AI chat, favorite, stars, gained stars, language, translation status, tags, and update time.
- Improve README presentation so the list is easier to scan. The default may be collapsed or previewed, but the full summary must remain available.
- Keep external repository links safe and opening in a new tab.

### Modals And Mobile

- Improve keyword modal and chat modal sizing on narrow screens.
- Ensure buttons and text do not overflow their containers.
- Keep the chat experience simple: existing suggestions, streamed answers, and error state remain.

### Empty And Error States

- Provide clearer empty states for:
  - no local project results
  - no favorites
  - no recommendations
  - GitHub search failure
  - chat failure
- Avoid adding tutorial-style in-app copy. Use concise operational text only.

## Maintainability Scope

### Frontend JavaScript

- Continue using vanilla ES modules.
- Keep `sanitize.mjs` as the security boundary for user/API-rendered text.
- Split or reorganize `app.js` only where it reduces local complexity in changed areas.
- Prefer small pure helpers for:
  - state reset for mode switches
  - status summary formatting
  - project card metadata rendering
  - empty/error state rendering
- Do not introduce a framework or bundler.

### Backend/API

- Keep API routes and response shapes backward compatible for the current frontend.
- Fix only consistency issues found while implementing the UI polish, such as missing fields in favorites output or error responses that prevent clear UI states.
- Avoid changing scrape cadence, model prompts, recommendation algorithm, or database schema unless a small migration is required for a directly used field.

## Testing

Run focused verification before completion:

- Python API tests with `python -m pytest`.
- Frontend security/formatting tests with `node tests/test_frontend_security.mjs`.
- JavaScript syntax check with `node --check static/js/app.js`.
- Browser verification on the local app if a dev server or Docker service is available:
  - desktop viewport
  - mobile viewport
  - category switch
  - favorite toggle
  - README toggle
  - chat modal open/close
  - theme toggle

If a service cannot be started because of missing Docker/network/API configuration, record that limitation in the final implementation report.

## Scope Exclusions

- No full sidebar/dashboard redesign in this pass.
- No new frontend framework, package manager, or build step.
- No changes to model provider behavior or prompt strategy.
- No major database redesign.
- No unrelated cleanup of existing dirty files.

## Acceptance Criteria

- The app remains functionally equivalent for existing workflows.
- The first screen and project list feel cleaner and more stable across desktop and mobile.
- Existing security sanitization continues to pass.
- Tests cover any changed rendering, API, or state transition behavior.
- The final commit includes only the spec and files required for this optimization.
