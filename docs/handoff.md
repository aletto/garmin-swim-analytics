# Project handoff

Build a local-first Python application for historical Garmin Swim 2 pool workouts. The initial validation profile is a 25 m pool with freestyle and breaststroke. Ingestion, quality and analytics should remain reusable for other devices and pool lengths. Use English in code, documentation, issues and commit messages.

## Scaffold delivered

- Installable Python package in `src/` with an offline `import-fit` command and direct Garmin Personal API import by activity ID or paginated pool-swim history and pluggable provider discovery through `sync-garmin`.
- FIT validation and message inventory, byte-preserving local archival, and idempotent raw storage with provider provenance.
- Standalone quality function using stroke, pool length and workout context, with synthetic test cases and configurable thresholds.
- GitHub Actions definitions for lint, typing, tests, secret scanning and dependency auditing. Privacy exclusions apply before a repository is created.
- MIT license.

## Milestones and acceptance criteria

1. **Finish ingestion discovery.** Inspect several privately exported 25 m Swim 2 FIT activities, including a mixed-stroke session and a session with rest or drills. Record the field mapping and support missing fields explicitly. Direct import has been verified on a real Swim 2 activity. Validate automatic history discovery on the same account. The connector rechecks all pages and skips archived provider IDs, so rerunning after interruption resumes without redownloading committed files. Review an unofficial connector only if the official API leaves a material gap.
2. **Normalize and persist.** Write typed Activity, Interval and Length tables to local Parquet with DuckDB views. Preserve observed values and their raw references, track Quality Assessment and versioned Correction separately, and reconcile totals without changing original observations. Test mixed strokes, duplicate imports, missing lengths and missing metrics.
3. **Integrate quality and review.** Apply the existing MAD rule to explicit historical and workout-local references. Add contextual device-error hypotheses and an auditable review path. Accept, exclude, change stroke or distance with evidence, and restore earlier corrections. See [quality and progress](quality.md).
4. **Extend `swim-analytics analyze`.** The raw overview shows monthly volume and pace by stroke and pool size. The separate `progress` command shows monthly time and SWOLF medians with a raw toggle and within-interval MAD quarantine. Add historical baselines, review and correction workflows, curated summaries, window comparisons and trends for speed, efficiency, endurance, cardiovascular measures and training consistency. Include sample sizes, quality coverage and missing-metric counts.
5. **Implement `swim-analytics dashboard`.** Use Streamlit and Plotly for Overview, Stroke Analysis, Workout Explorer, Data Quality and Progress. Support per-workout lengths and intervals, raw/clean switching, quarantine review and correction history. Bind locally by default. Use synthetic data in public demos and screenshots.
6. **Validate privately.** Compare results with Garmin totals and known workout sets, including genuine slow recovery and fast sprints. Review the effects of quarantining on both strokes and document uncertainty before interpreting trends.

These milestones use local Python, Parquet and DuckDB. Keep user thresholds and device-specific test exports in private configuration and storage.
