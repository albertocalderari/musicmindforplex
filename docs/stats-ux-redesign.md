# The Collection — UX redesign brief

**Route:** `/stats` · **Audience:** UX/frontend developer · **Date:** 20 November 2026

## Review basis

The local URL responds with a Reflex application. This review uses `musicmind_ui/views/stats.py`, the associated state, and `assets/reflex.css`. A browser was unavailable, so these are implementation findings and a proposed design, not a verified visual audit of the rendered page. Do not implement against the legacy `web/templates/stats.html`.

## Design goal

Make this page feel like a personal record collection: warm, editorial, and easy to read. Within a few seconds, users should understand the size of their collection, their listening pattern, and where the data comes from.

Keep the existing warm palette and shared application navigation. Give the content a clearer hierarchy instead of adding more dashboard decoration.

## Problems to solve

| Current implementation | UX consequence | Proposed change |
| --- | --- | --- |
| “The Collection” followed by “In the stacks” and another introduction | Repeated introduction delays useful information | One title and one explanatory sentence |
| Library totals and Last.fm plays share one metric group | Users may assume all figures describe the same source | Explicit source labels and separate listening section |
| Four equally prominent metrics, including instrumentals | Secondary metadata competes with core totals | Prioritize tracks and artists; move instrumental count to library details |
| 10–100 results rendered in a 320px horizontal chart | Large selections cannot retain readable rows | Ranked lists with visible values and pagination |
| Top artists use Plex plays; timeline uses Last.fm | Rankings may appear inconsistent | Name the source next to each heading; never imply a shared filter |
| Gender pie uses labels and a legend | Duplicated information and poor small-category comparison | Optional metadata detail table |
| Charts animate for 900–1000ms | Repeated updates delay inspection | Short optional entry animation; respect reduced motion |

## Proposed page structure

```text
[Existing app navigation]

THE COLLECTION                             [Export library CSV]
Your music, in perspective.
Plex library and Last.fm listening history.

LIBRARY OVERVIEW · Plex
[ Tracks                  ] [ Artists                 ]
Instrumental tracks: {count} · Based on available metadata

LISTENING · Last.fm
Your listening over time
Recorded plays: {total}                 [Year / Month]*
[full-width timeline                                  ]
[View data]

IN YOUR LIBRARY
Most played artists                    Genres
Plex play counts                       Plex / enriched tags
[ranked rows, count, proportional bar]  [ranked rows, count]
[Show: 10 / 25 / 50 / 100]              [Show: ...]

Artist origins                         Across the decades
[ranked rows]                          [vertical bars]

[Disclosure: Artist metadata]
[Gender categories and counts; unknowns retained]
```

*Expose Year/Month only when both datasets are available and meaningful. The current state selects a granularity supplied by the API; it does not establish a working user-controlled toggle.*

## Visual direction

Use a quiet “record sleeve notes” aesthetic: parchment background, ink text, fine rules, generous spacing, and a single strong brown accent. Reserve sage for library composition and terracotta for listening. Avoid assigning a different decorative color to every metric.

- Use the existing serif heading family (`New York`, Georgia fallback) and existing application sans serif for controls/body text. No new font dependency is required.
- Title: 36–44px desktop, 30–34px mobile; body: 16px; chart labels and captions: at least 13px. Use tabular numerals for counts.
- Content width: approximately 1200px, centered; desktop gutters 32px, mobile gutters 16px.
- Spacing scale: 4, 8, 12, 16, 24, 32, 48px. Use 40–48px between sections and 24px within sections.
- Panels: 12px corner radius, thin existing hairline token, minimal shadow. Let section headings establish hierarchy; do not frame every sentence.
- Reuse existing theme tokens (`--ink`, `--muted`, `--surface`, `--hairline`). Add semantic chart tokens for both light and midnight themes; replace hard-coded light grid/tick colors.
- Validate text contrast at 4.5:1 and essential chart marks/control boundaries at 3:1. Keep visible keyboard focus.

## Component and interaction specification

### Overview

Two primary totals: Tracks and Artists. Show real zero only after a successful response; use skeletons during initial loading. Keep instrumental count as supporting text, with “Based on available metadata.” Do not infer complete vocal classification from missing tags.

### Listening timeline

Show Last.fm as the source and label the vertical axis “Recorded plays.” Use chronological ordering, integer ticks, and a baseline at zero. Prefer straight line segments to a smoothed curve that implies intermediate observations. Tooltip: explicit month/year and formatted count. Distinguish missing observations from confirmed zero plays.

Provide “View data” as an accessible disclosure containing a period/count table. Do not require hovering to retrieve exact values. Do not add date filters or comparisons until the backend supports their scope consistently.

### Ranked lists

Use semantic ordered lists or tables for artists, genres, and countries. Each row contains rank, full name, formatted count, and a subtle decorative proportional bar. Long names wrap; never rely solely on truncated axis labels or tooltips.

Keep the existing result limits. Display at most ten rows per page, with Previous/Next and “1–10 of N loaded.” Changing a limit resets that list to page one. Do not claim N is the complete library total when the endpoint only returns a top-N subset. Label each select “Artist results,” “Genre results,” or “Country results.” Preserve selection using the existing state behavior.

A list update should preserve the rest of the page, keyboard focus, and scroll position. Keep old results visible while refreshing and ignore stale responses from earlier requests. No clickable row styling unless a destination actually exists.

### Composition and metadata

Keep decades as bars, with count units confirmed from the backend. Source captions must explicitly say whether countries/eras count artists, tracks, or metadata assignments; current `cnt` field names alone do not establish this.

Genres may overlap. Do not display a percentage of the library without a confirmed denominator and deduplication rule. Preserve the current Plex/enrichment source distinction.

Place gender inside a collapsed “Artist metadata” disclosure. Show source categories without guessing identity, and keep unknown/unclassified values visible. Avoid presenting metadata coverage as a personal insight.

### Export

Use a secondary button/link labeled “Export library CSV,” with a download icon rather than an external-link arrow. Export scope is the enriched library, independent of visible ranking limits. Keep it available without competing with the title.

## Responsive behavior

- At 1024px and above: two columns for composition panels; full-width listening timeline.
- At 768–1023px: retain two columns only where row labels remain readable; otherwise stack.
- Below 768px: one column; title/export wrap; overview totals may remain two columns until 380px, then stack.
- Controls have at least 44px touch targets. Panel headings wrap above controls when necessary.
- Timeline reduces tick density rather than font size. Ranked lists use flexible labels and a fixed numeric column.
- At 320px width and 200% zoom, no page-level horizontal scrolling or clipped controls.

## Loading, empty, and failure states

| State | Required presentation |
| --- | --- |
| Initial fetch | Stable skeleton footprints; section marked busy; no fabricated zero totals |
| Successful empty library | “No tracks found.” Link to relevant library setup/sync area |
| No Last.fm history | “No listening history yet.” Link to Admin with clear sync wording |
| Missing enrichment | Explain the missing metadata and link to the existing Admin workflow |
| Refresh failure | Keep last successful data, label it as stale, and offer Retry |
| Initial failure | Clear error and Retry; do not render an empty dataset as success |
| Chart dependency/render failure | Keep the accessible data table/list available |

Do not trigger synchronization automatically from this page. Announce loading/errors politely without announcing every chart mark.

## Developer handoff

1. Refactor `musicmind_ui/views/stats.py` into overview, timeline, ranked-list, and metadata components. Retain the shared shell.
2. Update collection styles in `assets/reflex.css` using existing theme tokens; scope changes to this page.
3. Extend `musicmind_ui/state.py` as needed for explicit loading/error state, pagination, and stale-request handling. Preserve existing endpoint contracts.
4. Verify backend count semantics before finalizing source captions. If adding timestamps, coverage percentages, date filters, or delta metrics, treat these as separate data-contract work; do not invent values in the UI.
5. Keep existing CSV export and Admin routes working. Avoid changing the legacy template as part of this task.

## Acceptance criteria

- One clear introduction; Plex collection and Last.fm listening are visibly distinguished.
- All current datasets remain discoverable, with secondary metadata progressively disclosed.
- Selecting 100 results remains readable without squeezing 100 labels into a fixed chart.
- Exact chart values are available through keyboard-accessible tables/lists.
- Unknown metadata, overlapping genres, and missing periods are represented honestly.
- Loading, empty, initial error, and stale refresh states are distinguishable.
- All controls work with keyboard alone; focus remains stable after updates.
- Reduced motion disables chart animation; both application themes retain readable chart labels and focus indicators.
- Check at 320, 390, 768, 1024, and 1440px, plus 200% zoom. Review with empty data, long names, large counts, and all result limits.

Deliver the implementation with desktop/mobile screenshots, a short accessibility check, and a note identifying any unresolved data definitions.

## Implementation comments — current listening model

**These comments supersede the earlier Last.fm-only listening labels and empty-state instructions.** The current backend combines known dated observations from Last.fm, Plex, and iTunes. Preserve that model during redesign.

- Label the section **Listening history** and the quantity **Recorded plays**. Use a caption such as “Known dated plays from Last.fm, Plex, and iTunes; overlapping observations are deduplicated.” Identify available sources from actual data rather than implying all integrations are connected.
- Use the combined-history total for that section. Keep any lifetime Plex play counts or Last.fm-only scrobble totals explicitly labeled and separate; they are not interchangeable with the combined dated total.
- The backend currently considers cross-source observations of the same identified track within 60 seconds overlapping, with Last.fm, then Plex, then iTunes taking precedence. Source contributions describe retained observations after this deduplication, not each service's raw total. Do not change that policy as part of styling.
- iTunes contributes known last-played observations, not an invented dated distribution of aggregate play counts. Explain incomplete history without claiming an empty timeline whenever Last.fm is absent.
- Reuse `combined_timeline_rows()` and its explicit unknown-period handling in `musicmind_ui/collection.py`. Preserve gaps rather than plotting missing periods as zero. Keep displayed totals and source columns aligned with the same dataset.
- An empty listening section should say “No dated listening history yet” and point to relevant library-history sync/import tools in Admin. Do not require Last.fm specifically.
- Verify the timezone used for date grouping before adding timezone copy; the current aggregation uses the server's local datetime conversion. Do not imply the browser timezone controls grouping.
- Reuse existing ranked-row/timeline presentation helpers where suitable. Inspect the current page before replacing components: implementation has progressed since the original brief, so retain already-working accessibility and data handling.
- Validate with one source, multiple overlapping sources, iTunes-only observations, missing periods, and no dated observations. Confirm that timeline tables and chart tooltips agree. Review all five application themes, not only light and midnight.

**Development order:** reconcile listening labels and units first; then implement page hierarchy and ranked-list behavior; then finish loading/error states, responsive layout, and accessibility verification. No backend listening-policy change is required by this brief.

## Shared theme follow-up

Apply the shared [Theme UX review](theme-ux-review.md). Midnight is approved; the other four themes need complete component palettes. In particular, make chart axes, tooltips, ranked bars, metric values, selected controls, and full-page backgrounds theme-aware without changing data meaning.
