# SAGE Dashboard UI Improvements — Claude Code Prompt

> Read `.build/AGENT.md` and `.build/SAGE_SPEC.md` first for project context.

## Objective

Implement 12 UI improvements to the SAGE Cloud dashboard. All changes are in `sage-solver-cloud/sage_cloud/builtin_pages.py`, which contains three inline JSX page components (`_DASHBOARD_JSX`, `_ARTIFACTS_JSX`, `_SAGE_JOBS_JSX`), plus `sage-solver-cloud/sage_cloud/jobs_api.py` for one API-level change.

The dashboard uses React (available as `React` global), inline styles (no CSS framework), and a dark theme with these colors:
```
bg: '#0d1117', surface: '#161b22', border: '#1e2a3a',
accent: '#3b82f6', text: '#e2e8f0', muted: '#8b949e',
green: '#34d399', red/fail: use '#ef4444', amber/stall: use '#f59e0b'
```

Pages are registered at the bottom of `builtin_pages.py` via `register_builtin_pages()`. The page server renders them inside the Sage shell layout. No build step — just edit the JSX strings and restart.

## Changes to Implement (in order)

### 1. Filtered Count Display (Quick — `_SAGE_JOBS_JSX`)
**Problem:** Header always shows "X total" even when filtered.
**Fix:** When `statusFilter !== 'all'` or `typeFilter !== 'all'`, show `"X matching of Y total"` instead of just `"Y total"`. The filtered count is `filteredJobs.length`, total is `jobs.length`.

### 2. Variable Value Rounding (Quick — `_SAGE_JOBS_JSX`)
**Problem:** Variable values show 6+ decimal places (e.g., `6.000000`).
**Fix:** In the variable values table (rendered in expanded job details), round displayed numbers: if the value is an integer (Math.abs(v - Math.round(v)) < 1e-9), show as integer; otherwise show `toFixed(4)`. Also round the objective value the same way. Add a small "Show full precision" toggle (a clickable text link, not a big button) that switches between rounded and raw display.

### 3. Status Badge Styling (Quick — `_SAGE_JOBS_JSX`)
**Problem:** Status badges are basic colored text, not visually distinct enough.
**Fix:** Replace plain text status with filled pill badges. Use this style pattern:
```js
const statusBadge = (status) => {
  const map = {
    completed: { bg: '#0d2a1f', color: '#34d399', icon: '✓' },
    failed:    { bg: '#2a0d0d', color: '#ef4444', icon: '✗' },
    running:   { bg: '#0d1f2a', color: '#3b82f6', icon: '⟳' },
    stalled:   { bg: '#2a1f0d', color: '#f59e0b', icon: '⏸' },
    paused:    { bg: '#2a1f0d', color: '#f59e0b', icon: '⏸' },
    queued:    { bg: '#1a1a2e', color: '#8b949e', icon: '○' },
    infeasible:{ bg: '#2a1a0d', color: '#f97316', icon: '⊘' },
  };
  const s = map[status] || map.queued;
  return { display:'inline-flex', alignItems:'center', gap:'.35rem', padding:'.15rem .6rem', borderRadius:'999px', fontSize:'.78rem', fontWeight:600, background:s.bg, color:s.color };
};
```

### 4. Error Display Overhaul (High priority — `_SAGE_JOBS_JSX`)
**Problem:** Failed jobs show a wall of raw Pydantic ValidationError text that's unreadable.
**Fix:** In the expanded job detail view, when status is `failed` and there's an error field:
- Parse the error string: try `JSON.parse(error)` first — if it's a Pydantic validation error array, render a structured list of `loc`, `msg`, `type` per error item.
- If it's a plain string, extract the first line as the "Error Type" heading, and show the rest in a scrollable `<pre>` block with `max-height: 200px; overflow-y: auto;` instead of dumping everything.
- Add a "Copy Error" button that copies the full raw error to clipboard.
- Wrap the whole thing in a card with the red-tinted background (`#1a0a0a` bg, `#2a1010` border).

### 5. Auto-Generated Job Names (`jobs_api.py` + `_SAGE_JOBS_JSX`)
**Problem:** Many jobs show as "unnamed" with only a UUID visible.
**Fix in `jobs_api.py`:** In the `POST /api/jobs` handler, when `problem_name` is `"unnamed"` or empty, auto-generate a name from `solver_input`:
```python
if not req.problem_name or req.problem_name == "unnamed":
    n_vars = solver_input.get("num_variables", "?")
    n_cons = solver_input.get("num_constraints", "?")
    ptype = req.problem_type or "opt"
    req.problem_name = f"{ptype}-{n_vars}v-{n_cons}c"
```
**Fix in `_SAGE_JOBS_JSX`:** In the job list row, show the `problem_name` prominently as the primary label. Show the task_id in smaller muted text below or beside it. Currently many rows just show the task_id — make the name the primary visual identifier.

### 6. Health Page (`builtin_pages.py` — new `_HEALTH_JSX`)
**Problem:** `/health` returns raw JSON with no styling.
**Fix:** Create a new `_HEALTH_JSX` page component. Register it as `"sage-health"` in `register_builtin_pages()`. The page should:
- Fetch `/health` and `/api/system/state` (with auth header from sessionStorage).
- Show a large status badge (green dot + "Operational" or red + "Degraded").
- Show version number, uptime (formatted), blob count, page count.
- Show a "Solver Check" section: attempt a tiny solve via the MCP or just show solver availability from system state.
- Use the same dark theme as other pages.
- Link to it from the dashboard home System Health card (update `_DASHBOARD_JSX` navigate target).

### 7. Dashboard Home Enrichment (`_DASHBOARD_JSX`)
**Problem:** Dashboard home is sparse — 3 small cards with lots of empty space.
**Fix:** Add below the existing 3 cards:
- **Recent Jobs feed**: Fetch `/api/jobs` and show the 5 most recent jobs as a compact list (name, status badge, elapsed time, timestamp). Each row clickable to navigate to `/page/sage-jobs`.
- **Quick Stats row**: Above the cards, show a horizontal stat bar: "Jobs Today: X | Avg Solve Time: Xs | Success Rate: X%". Compute from the jobs list (filter by today's date, count completed vs total, average elapsed for completed).

### 8. Convergence Chart Time Normalization (`_SAGE_JOBS_JSX`)
**Problem:** Header shows elapsed as "45m 34s" but chart X-axis shows raw seconds (2372).
**Fix:** Format the chart X-axis ticks to mm:ss or hh:mm:ss using the same `fmtElapsed` helper. If using Chart.js, set a `ticks.callback` on the x-axis that calls `fmtElapsed`. Add axis labels: X = "Elapsed Time", Y = "Objective Value".

### 9. Job Action Icons on Collapsed View (`_SAGE_JOBS_JSX`)
**Problem:** Actions (Explain, Download, Relaxations) only visible after expanding.
**Fix:** On each collapsed job row (for completed/failed/infeasible jobs), add a small action icon bar on the right side with 2-3 icon buttons: a clipboard icon for "Copy Result", a download icon for "Download JSON", and an info icon to expand. Use simple unicode or SVG icons, styled as small subtle buttons. Keep the full action set in the expanded view.

### 10. Artifacts Browser Improvements (`_ARTIFACTS_JSX`)
**Problem:** Minimal metadata, no search, no job linkage.
**Fix:**
- Add a search/filter input at the top that filters artifacts by name.
- Show creation date and file size (if available from the API) on each artifact row.
- Add artifact type indicators (icon or colored dot — page vs blob).

### 11. Empty States (`_SAGE_JOBS_JSX` + `_ARTIFACTS_JSX`)
**Problem:** No helpful messages when filters return no results.
**Fix:** When the filtered list is empty, show a centered message instead of a blank area:
- Jobs with filter active: "No {status} jobs found" with a "Clear filters" link.
- Jobs with no jobs at all: "No jobs yet — submit your first optimization problem via the MCP tools."
- Artifacts with no items: "No artifacts stored yet."
Use muted text color, centered, with some vertical padding.

### 12. Responsive Layout (`_DASHBOARD_JSX` + `_SAGE_JOBS_JSX`)
**Problem:** Fixed-width layout clips on narrow screens.
**Fix:** Use `max-width` with `width: 100%` instead of fixed widths. Set card containers to `flex-wrap: wrap`. On the jobs list, make the table/list horizontally scrollable (`overflow-x: auto`) on narrow viewports. Add a `@media` check via JS: `window.innerWidth < 768` to stack cards vertically.

## Testing

After implementing all changes:

1. Restart the server: `cd sage-solver-cloud && pip install -e . --break-system-packages && sage-cloud`
2. Verify each page loads without JS console errors.
3. Check the jobs list with various filters — the count should update.
4. Expand a failed job — error should render as a structured card, not a wall of text.
5. Check dashboard home — should show recent jobs and quick stats.
6. Navigate to the health page — should show styled status, not raw JSON.
7. Submit a new job without a `problem_name` — it should auto-generate a name.
8. Narrow the browser window — layout should adapt without clipping.

## Do NOT

- Do not move JSX out of `builtin_pages.py` into separate files — the page server expects inline strings.
- Do not add npm dependencies or a build step — these are runtime JSX strings rendered by the Sage shell.
- Do not change the API contract of existing endpoints (only additive changes to response fields are OK).
- Do not touch `sage-solver-core` — all changes are in `sage-solver-cloud`.
