# Admin workspace and menu — UX redesign brief

**Route:** `/admin` and shared Admin menu · **Audience:** UX/frontend developer · **Date:** 20 November 2026

## Review basis

Review of the current Reflex implementation: `musicmind_ui/views/admin.py`, `musicmind_ui/views/components.py`, `musicmind_ui/job_definitions.py`, job state in `musicmind_ui/state.py`, and `assets/reflex.css`. Browser access was unavailable during this session; this is a source-based UX review, not a verified visual audit. Apply the same warm editorial design direction as `docs/stats-ux-redesign.md`.

### Review comments — live validation, 20 November 2026

The comments below supplement the original source review. The live page at `http://127.0.0.1:8787/admin` was inspected through Chrome's desktop accessibility interface. Library Operations was expanded, the Plex library Status dialog was opened, and the Admin menu was inspected. No maintenance jobs, imports, or rating writes were executed. Screenshots were unavailable; responsive layout, contrast, and visual spacing remain unverified.

- **High — preserve the requested Library Operations structure.** The live page now places Sync Plex library, Sync Plex listening history, and Sync Last.fm directly inside Library Operations, with no separate Library group under Individual Tasks. The proposed layout and Advanced task groups specification below would undo this change. Keep those jobs under Library Operations and remove the proposal to restore a Library advanced group.
- **High — resolve the rating-direction conflict before implementation.** The live card says: “Existing Plex ratings take priority and update MusicMind. MusicMind ratings fill only unrated tracks in Plex.” The current `sync_ratings_to_plex()` implementation confirms that behavior. The Data transfers specification below instead makes MusicMind authoritative and replaces different Plex ratings. These are materially different data-write policies; the redesign must explicitly resolve the discrepancy rather than treating it as a label change.
- **Medium — update the iTunes timeline limitation.** The live page still says imported history will not populate date-based timelines, and the import specification below repeats that assumption. Recent backend changes retain known last-played observations and include dated iTunes observations in listening data. Explain that the export lacks the complete sequence of historical plays, while known last-played dates can contribute to timelines. Do not distribute aggregate play counts across invented dates.
- **Medium — make Full sync discoverable outside the collapsed section.** Library Operations is collapsed initially and currently contains Full sync and Synapse as well as the individual syncs and transfers. This hides the primary maintenance action. Move Full sync outside that disclosure to satisfy the existing acceptance criterion, while keeping the individual library syncs inside Library Operations.
- **Medium — preserve Full sync's existing scan behavior.** The current backend triggers a Plex folder scan and waits for it to complete before ingestion. The instruction below not to chain scanning into Full sync is a workflow change, not a description of the current implementation. Preserve the pipeline for this UX work and describe the existing scan/wait behavior accurately unless a separate behavior change is agreed.
- **Medium — reuse available terminal-state data.** `jobs.status()` already returns `exit_code` and `stopped` in addition to `running`. Use those supported results for completion/failure/stopped presentation; do not require an entirely new result contract for all terminal states. Timestamps, stale state, and interrupted-process detection still need explicit treatment. The live Plex Status dialog opened successfully without the previously reported `_job_label` NameError, but its completed log was still presented as Idle.
- **Remaining redesign work confirmed live:** the page still starts with the eyebrow/slogan rather than a clear Admin heading; the menu retains Overview/DB Console/Tests/Synapse and its old grouping; release refresh still uses the Apply changes checkbox; group Run all controls remain inside disclosure summaries; and the Import button is enabled without a selected file. These portions of the original brief remain applicable.

## Design goal

### Latest user direction — horizontal separators

Use Full sync's horizontal-rule treatment across Admin: thin, theme-aware separators above major sections and between tools or data transfers. Prefer open sections over repeated bordered cards. Keep consistent spacing around each rule and avoid doubled adjacent borders.

Preserve Synapse's original dark teal gradient tile, compact controls, and network artwork as the deliberate feature-surface exception. Activity stays a compact ruled status strip, with its label and idle summary sharing a row where space permits; active job rows appear underneath. Library Operations stays collapsed initially with a right-aligned chevron that rotates when opened. Preserve keyboard focus, reduced-motion behavior, and mobile touch targets.

Help users answer three questions immediately: What is running? What should I run for my task? What happened after I ran it?

Present Admin as a calm operational workspace. Prioritize routine synchronization, show actionable status, and keep specialized jobs discoverable through progressive disclosure.

## Findings

| Implementation finding | Consequence | Design response |
| --- | --- | --- |
| Shared `shell()` accepts a title/subtitle but does not render them | “Back Office” does not establish the page heading; the visible utility header starts with an eyebrow and slogan | Add an explicit Admin heading and useful introduction |
| Plex scan and release refresh precede Full sync; imports and rating writes sit inside Library Operations | The recommended maintenance path is hard to scan | Put Full sync first; separate focused updates from data transfers |
| Job badges primarily distinguish Running and Idle | Idle can conceal success, failure, or a stopped job | Distinct lifecycle states, backed by job result data |
| Every start opens a log dialog | Users are taken away from the workspace before seeing a clear status summary | Start inline; offer job details without forcing a modal |
| Group Run all buttons are inside disclosure summaries | Running a group and expanding it occupy the same interaction area | Separate disclosure trigger from execution controls |
| A checkbox switches release refresh from preview to apply | Preview can be bypassed and the action changes meaning | Make preview the first step; expose apply with the result |
| Synapse indicator checks only `synapse_full`, while artwork also reacts to limited analysis | Status can disagree across elements | Derive one consistent analysis status |
| Menu labels mix Overview, DB Console, Tests, Synapse, Logs, Guide, Update | Destination purpose and hierarchy are unclear | Group destinations by task; use descriptive labels |
| Menu row CSS ends at approximately 34px high | Small touch targets | Minimum 44px interactive rows |

## Information architecture

Keep the global Playlists, Collection, and conditional Gaps links. Keep Appearance separate from Admin: changing a theme is a personal preference.

Use **Admin** consistently for both the trigger and page title. Replace the “Back Office”/“A little order in the noise” naming with a direct introduction: “Sync your library, manage metadata, and follow background jobs.”

### Admin menu

```text
Admin ▾

WORKSPACE
Admin overview          /admin
Audio analysis          /admin#synapse

DIAGNOSTICS
Playlist audit          /playlist-audit
Database console        /db
System tests            /tests
Logs                    /logs

HELP
Guide                   /guide
```

Preserve all current routes. “Audio analysis” can retain “Synapse” in the destination heading as the feature name. “Software update” is a navigation destination; selecting it must not execute an update.

- Highlight the current destination with text emphasis and a small indicator; do not rely on color alone. Overview should not appear selected when the audio-analysis hash is selected.
- Keep Admin visually active while on an admin-owned route. Establish an explicit route list rather than guessing from URL prefixes.
- Use existing menu primitives for keyboard navigation, Escape, and focus return. On open, focus the active item when supported; otherwise use the primitive's standard behavior.
- Maintain a readable 240–280px width, bounded by the viewport. Short viewports scroll within the menu. Align to the trigger without clipping at screen edges.
- Keep semantic group labels noninteractive. All rows have icons plus text and at least 44px height.
- Preserve portal theme inheritance across Light, Parchment, Midnight, Ocean, and Forest.
- This is navigation, so it should expose link destinations where the framework supports them. Avoid nested interactive elements when adapting menu items to links.

## Proposed page layout

```text
[Existing app navigation, Admin active]

Admin
Sync your library, manage metadata, and follow background jobs.
[Overview] [Library Operations] [Library tools] [Data transfers] [Advanced tasks]
    Local section links; not a second global navigation system

[Activity: {running count} jobs running / No jobs running]
[Active job · phase · progress when known · View details]

KEEP YOUR LIBRARY CURRENT
Full sync                                      [Start full sync]
Plex index, listening history, metadata, tags, and audio analysis
[Current phase / Last result when available]    [View details]
Includes a Plex folder scan and waits before importing the index.

LIBRARY OPERATIONS ▾
[Sync Plex library] [Sync Plex listening history] [Sync Last.fm, when configured]

LIBRARY TOOLS
[Refresh an album: Artist + Album → Preview changes]
[Audio analysis / Synapse: counts + status + Start analysis]

DATA TRANSFERS
[Import Apple Music / iTunes XML]
[Sync star ratings with Plex]

ADVANCED TASKS
[Metadata enrichment                      ▾]
[Audio and collection analysis            ▾]
[Maintenance                              ▾]
```

Make Full sync the most prominent action outside collapsed sections. Preserve its existing Plex folder scan and wait before ingestion. Keep standalone Scan Plex folders available as a focused tool; explain that it requests file discovery, whereas Sync Plex library imports the current Plex index.

Local section links scroll to real headings with a sticky-header offset; they must not launch work. On mobile, wrap into readable rows rather than concealing all destinations in a horizontal strip.

## Workflow specifications

### Full sync and active jobs

Show active work above the task sections, even if the associated advanced group is collapsed. Use one row per job, with its label, state, current phase when available, and View details. Keep backend concurrency rules authoritative.

Before starting, show the action's scope in the card. Start once, immediately display “Starting…”, and prevent duplicate submission. On acknowledgement transition to Running; on rejection show the reason next to the action. A disabled action must have an adjacent explanation identifying the blocking work.

For Full sync, use “Stage X of 12” only if the backend contract still guarantees twelve stages. A stage-based percentage is not an elapsed-time estimate. Never invent an ETA. Hide progress at rest unless showing an explicitly labeled last run.

Do not force a job dialog open after every start. Keep the workspace visible, surface inline feedback, and provide View details. Closing details never stops a job.

### Release refresh

Retitle “Refresh a specific release” to “Refresh an album” if artist and album are both required by the backend. Use persistent Artist and Album labels, field-specific validation, and whitespace trimming.

1. Enter artist and album; select **Preview changes**.
2. Show matched release, proposed changes, and any ambiguity or errors.
3. Offer **Apply changes** only for a valid preview; show an empty result as “No changes needed.”

Remove the Apply changes checkbox. Preserve input on errors. If either field changes, invalidate the preview. If the current dry-run produces only logs, label the output as a preview log rather than fabricating a structured diff. A structured, version-bound preview/apply flow requires backend support; implement that explicitly before claiming the preview guarantees the exact applied result.

### Audio analysis / Synapse

Keep `#synapse` as a stable anchor. Preserve the distinctive dark Synapse tile, its network illustration, and its prominent analysis counters. The illustration is decorative; keep it still at rest and disable animation under reduced motion. Retain the tile within Library tools and keep its controls and status accessible.

Show analyzed count and error count with clear units. Treat missing counts as unavailable rather than confirmed zero. Confirm whether counters cover the entire library or a particular run before writing captions.

Start analysis is primary; Count tracks is secondary and should say what it counts once backend semantics are verified. Derive running status from all relevant analysis jobs, distinguishing count-only work from analysis. Do not show Idle while a limited analysis is active.

### Data transfers

Separate transfers from routine maintenance; each gets a compact card with a clear source → destination description.

**Import Apple Music / iTunes history:** XML file picker and drop target; show filename, 50 MiB limit, validation feedback, import progress/state, and result. Disable Import until a valid file is selected and while importing. Keep visible: existing ratings are preserved and the higher play count is retained. Put export instructions in an expandable “About this import” section. Explain that known last-played observations can contribute to timelines, but XML does not contain the complete sequence of historical plays. Never distribute aggregate play counts across invented dates. Report matched/unmatched counts only if returned by the backend.

**Sync star ratings with Plex:** Keep the consequence visible: “Existing Plex ratings take priority and update MusicMind. MusicMind ratings fill only unrated tracks in Plex.” Use **Sync star ratings** as the button label. Preserve this data-write policy. Keep result feedback in this card; show refreshed, synced, unchanged, and failed counts when returned. Do not imply an undo capability.

### Advanced task groups

Use the existing JOB_GROUPS definitions as the task inventory. Keep the individual Library jobs in Library Operations, including Plex library sync, Plex listening-history sync, and conditional Last.fm sync. Do not duplicate them under Advanced tasks. Full sync remains outside the collapsed Library Operations section.

Each group has a disclosure button with its task count and short description. Inside, task rows show name, purpose, state, **Run task**, and **View details**. Put **Run all tasks in this group** inside the expanded group, separate from its disclosure trigger, with a summary of included work. Preserve backend ordering and concurrency behavior; do not imply parallel execution.

Avoid unexplained technical terms where a task description can explain the outcome. Keep specialist names such as MusicBrainz visible where they identify the source. Last.fm availability must follow existing configuration rules; explain unavailable integration functionality without exposing credentials.

## Job details and status model

Use a desktop dialog or side panel; use a full-height dialog on small screens. Include job name, state, phase, progress when known, last refresh time when available, and recent output. Retain manual Refresh, Close, and Stop for applicable running jobs.

| State | Presentation |
| --- | --- |
| Loading status | Neutral placeholder; do not claim Idle |
| Ready / never run | “Ready” or “No recorded run,” based on available data |
| Starting | Pending control, no duplicate start |
| Running | Text + icon; progress only when measurable |
| Completed | Success label with result/timestamp if supported |
| Failed | Short error, details, supported retry action |
| Stopping | Pending stop state until backend acknowledgement |
| Stopped | Explicit stopped result, distinct from success |
| Status unavailable | Connection/error message; preserve last known state as stale |

Reuse the existing `jobs.status()` fields `running`, `exit_code`, and `stopped`: an acknowledged stop takes precedence; otherwise, after execution has ended, exit code 0 indicates completion and nonzero indicates failure. Missing terminal metadata must remain unknown/interrupted rather than success. Expose these fields through UI state. Timestamps, stale status, and interrupted-process handling require explicit treatment; do not derive success merely because a process is no longer running.

Logs should use readable monospace text, wrap long lines, and remain selectable. Auto-follow only when the user is at the bottom; offer “Jump to latest” after they scroll away. Avoid announcing each incoming log line to screen readers. Announce lifecycle transitions politely. Keep focus trapped in the dialog, support Escape, and restore focus to its opener.

Explain Stop behavior using verified backend semantics. Do not claim rollback or instant termination. Keep Stop visually distinct and away from Close and Refresh to reduce accidental activation.

## Visual and responsive design

- Reuse the Collection brief's typography and spacing: serif page title, application sans serif for task UI, tabular counts, 16px body, minimum 13px captions.
- Use a centered content area around 1200px with 32px desktop and 16px mobile gutters.
- Full sync and Activity span the content width. Library tools may use two columns above 1024px; long forms, advanced tasks, and transfers prioritize readable widths.
- Use horizontal rules above major sections and between tools/transfers, following Full sync, rather than repeated card outlines. Preserve Synapse's rounded dark teal feature tile. Keep brown for primary actions, sage for normal operational status, amber for attention, and red for failed/stopping operations. Pair every color with text.
- Avoid the current accumulation of late CSS overrides: consolidate Admin styles into a clear scoped section after removing superseded rules.
- At narrow widths, task descriptions sit above actions; buttons wrap without overlapping. Dialog headers stack. All controls retain 44px targets.
- Verify 320, 390, 768, 1024, and 1440px plus 200% zoom. No page-level horizontal scrolling. Keep menu content and dialog actions reachable in short landscape viewports.
- Check text contrast at 4.5:1, essential controls/focus at 3:1, and all five themes. Honor reduced motion for status glow, artwork, and dialog transitions.

## Developer handoff and delivery order

1. Update menu labels/grouping in `views/components.py`, add route-aware active state, and preserve routes and Appearance.
2. Refactor `views/admin.py` into Activity, Full sync, Library tools, Data transfers, and Advanced tasks. Add explicit headings and stable anchors.
3. Separate disclosure triggers from run controls; standardize job rows, action labels, and inline feedback.
4. Extend `state.py` and job services only where required for lifecycle results, pending states, preview/apply, and trustworthy status. Verify conflict rules on the backend as well as in button state.
5. Consolidate scoped CSS in `assets/reflex.css`; preserve shared navigation behavior on non-Admin pages.

Prioritize navigation, task hierarchy, and truthful status first. Structured preview diffs, persisted run history, and additional counters are follow-up data-contract work unless already supported. No invented health scores, elapsed estimates, or synthetic history.

## Acceptance criteria

- Admin has one clear page heading, and Full sync is discoverable without opening an advanced group.
- All existing menu destinations remain reachable; selecting menu entries navigates without running operations.
- Menu groups, active destination, keyboard navigation, focus return, touch targets, and viewport bounds work in all themes.
- Running jobs remain visible with advanced sections closed and details dismissed.
- Repeated clicks cannot duplicate pending starts; conflict reasons and request failures are visible beside the relevant action.
- Expanding a group cannot execute a job; running a group cannot toggle its disclosure accidentally.
- Release preview and apply have distinct steps, truthful output, and retained input after errors.
- Imports and rating writes clearly state source, destination, and existing-data behavior.
- Job completion, failure, stopped, unknown, and stale states are distinguished only when backed by reliable data.
- Validate keyboard-only use, reduced motion, long job labels/log lines, missing Last.fm configuration, no active jobs, multiple active jobs, rejected starts, status connection failure, and narrow/zoomed layouts.

Deliver desktop/mobile screenshots for the page and open menu, a short keyboard/accessibility check, and a list of any backend requirements that remain unresolved. Test job state transitions with controlled fixtures or mocks; avoid running full maintenance or rating writes merely to validate layout.

## Review validation outcome — 20 November 2026

All six substantive review corrections are accepted. Source checks confirm the current Library job placement, Plex-first rating policy (`musicmind/itunes.py`), dated iTunes observations (`musicmind/listening.py`), collapsed Full sync placement, scan/wait sequence (`web/app.py`), and existing terminal-state fields (`musicmind_ui/jobs.py`). The Library grouping is retained as a documented design constraint; its origin as an earlier user request is reported by the reviewer rather than independently established here.

The implementation also confirms the remaining heading, menu, preview checkbox, nested group controls, and file-selection issues. The brief above now incorporates the corrections. Live accessibility observations and the reported absence of the earlier NameError were not independently repeated; responsive layout, visual spacing, contrast, and actual runtime behavior still require verification. No maintenance or data-write actions were executed during validation.

The Collection brief also predates the multi-source listening changes: its Last.fm-only timeline/source wording must be reconciled with current Plex and iTunes observations before implementation.

## Implementation comments — validated handoff

These comments resolve the review for development. Preserve backend behavior while changing presentation; do not implement the original rating-overwrite policy or remove the scan/wait phase.

### Priority 1 — structure and navigation

- Add an explicit Admin h1 in the page. Avoid changing shared `shell()` heading behavior across other pages as an incidental fix.
- Move Full sync outside Library Operations. Keep individual library syncs together inside that disclosure, including Plex listening history. Keep the Synapse anchor reachable without requiring users to manually expand a hidden parent.
- Implement the revised Admin menu, active route/hash states, and 44px rows. Preserve existing destinations and theme propagation.
- Separate every disclosure trigger from execution buttons. Use one clear disclosure target and place Run all in the expanded content.

### Priority 2 — trustworthy operation feedback

- Carry `exit_code` and `stopped` from job services into presentation state rather than adding a second source of truth. Missing metadata means unknown, not completed.
- Keep pending start/stop state per operation. Clear pending state on both success and exception; preserve useful error messages beside the originating control.
- Derive Activity from the existing running-job inventory. Identify parent/group jobs and their child processes before displaying a count so one pipeline is not misleadingly counted as several independent user operations.
- Keep dialog inspection available throughout polling. Starting work should not require opening details; changing this behavior must retain feedback for errors currently surfaced through the dialog/global message.
- Backend conflict rules remain authoritative. Do not expand the permitted concurrency merely because controls have moved.

### Priority 3 — focused tools and transfers

- Preserve Plex-first star-rating reconciliation. The operation can update MusicMind and fill unrated Plex tracks; describe both directions explicitly.
- Disable Import for an empty file selection. Validate file size/type on the server as well as in UI state; retain the existing 50 MiB limit.
- Explain iTunes history as known dated observations plus aggregate counts. An imported lifetime count is not a sequence of dated plays.
- Deliver release preview as two explicit steps. If a trustworthy structured diff is unavailable, use the real preview log and avoid promising that it is an atomic snapshot. Keep this dependency separate from navigation/layout work.

### Developer verification

Use focused tests for changed state transitions, duplicate submission, job-result mapping, and preview invalidation. Use controlled fixtures for running, completed, failed, stopped, unknown, and stale states; do not start production maintenance or rating writes for UI verification. Check menu/anchor navigation, keyboard focus, expanded groups, and narrow layouts manually. Record any unverified browser behavior in the implementation handoff.

**Definition of ready:** layout/menu work can begin now. Persisted run history, timestamps, structured preview diffs, and additional progress counters are optional follow-up work unless the implementation explicitly adds their backend support. The accepted review corrections are requirements for this redesign.

## Shared theme follow-up

Implement the shared [Theme UX review](theme-ux-review.md) alongside this brief. Midnight is approved; improve Light, Parchment, Ocean, and Forest. Prioritize consistent canvas, controls, statuses, menu/dialog portals, and Synapse feature styling. Preserve the approved Midnight appearance during shared CSS changes.

## User design correction — Synapse tile

Restore the existing distinctive Synapse tile and network artwork. Its dark surface and visual identity are intentional and should be preserved in future Admin changes. Keep the illustration decorative, still at rest, and compatible with reduced motion. The stable `#synapse` anchor and the revised analysis controls remain in place.

## Update page removal

The user requested removal of `/update`. Remove its page registration and Admin menu entry; do not restore it during redesign. Existing update APIs are outside this page-removal scope.
