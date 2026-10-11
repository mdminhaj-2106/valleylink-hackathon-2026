# ValleyLink project memory

Last reviewed: 2026-10-11 (Asia/Kolkata). This is the current handoff; update it after each work session. Statements marked **unverified** need a fresh check before being presented as current.

## Project and goal

- Track B, Multimodal AI Hackathon 2026: map flood/debris change, potentially affected infrastructure, and possibly cut-off settlements from an area and event date.
- Repository: `https://github.com/mdminhaj-2106/valleylink-hackathon-2026`; local checkout: this directory.
- Deadline supplied by the user: 15 October 2026. Team: two humans plus Codex. Human names and Devpost accounts have not been provided here.
- Source briefs: `/Users/sufi_spryzen/Downloads/Track B.pdf` and `/Users/sufi_spryzen/Downloads/Multimodal AI Hackathon 2026 - Submission Guidelines.pdf`.

## Verified implementation

- The `main` checkout and remote HEAD were `39ace01` when checked on 11 October 2026. Check Git state again before editing or publishing.
- The Streamlit app starts with a bundled, live-derived Syapru Besi case (`syapru_besi_reference.npz`) without credentials or network access. It provides Sentinel-1 and Sentinel-2 before/after images, candidate change and OSM overlays, road access scenarios, English/Nepali situation reports and Q&A, and a one-page HTML report.
- Live analysis accepts an area/date (maximum 0.5° × 0.5°), discovers a same-satellite/same-orbit Sentinel-1 pair using CDSE STAC with Catalog fallback, processes radar and an optional clear Sentinel-2 pair, and queries pre-event OSM via ohsome. A failed rerun retains the last displayed successful result.
- Bundled case figures: 1.8 km² candidate change, 164 potentially affected buildings, 5.82 km potentially affected roads, 4 candidate bridges, 3 possibly cut-off settlements; 96% usable radar and 81% usable optical coverage. These are screening estimates, **not** confirmed damage or access loss.
- The README reports preliminary overlap against EMSR927 mass-movement polygons: 65.5% of mapped area covered in Syapru Besi AOI01 and 56.3% in Timure AOI02; 40.4% and 34.2% of candidate change inside those polygons. This is neither damage accuracy nor flood precision/recall. EMSR927 is evaluation only, never an inference input.
- The last completed automated result recorded in the handoff was **39 passing tests on 9 October**. A later test attempt on 11 October stalled under host load and must not be reported as passed.

## Current risks and unfinished work

1. **Judge-selected live run:** Track B requires an end-to-end run from raw satellite data for the judges' area/date. The live path has suffered Copernicus TLS and processing timeouts. A prior run succeeded for Syapru Besi, but arbitrary area/date reliability is **unverified**. Check service health, credentials, and a second area/date; preserve honest error messages if the external service fails.
2. **Submission:** `docs/TECHNICAL_REPORT.md` and a two-page `docs/TECHNICAL_REPORT.pdf` draft were created and visually checked on 11 October. `docs/DEMO_AND_DEVPOST.md` contains a Devpost description and timed demo script. Human review remains; the video has not been recorded or uploaded, and Devpost has not been submitted. Add both humans' real names and Devpost accounts before submission.
3. **Validation:** building/road counts and cut-off settlements lack independent per-feature confirmation. Human review of English/Nepali claims is outstanding. Current EMSR927 checks are only polygon-overlap diagnostics.
4. **Known limits:** optical gaps/clouds, satellite revisit delay, OSM incompleteness, detours outside the AOI, 0.5° area cap, and dependence on Copernicus/ohsome. Upstream DEM flood-path tracing is optional.

## Rules for the next session

- Start by checking `git status`, HEAD/remote, available disk space, and whether the app and tests actually run. Never infer freshness from this file alone.
- Keep `.env` and API keys out of commits, logs, reports, and chat. Do not use EMS/UNOSAT damage maps as model inputs or post-event OSM edits.
- Prioritize a dependable live judge path and the required deliverables over optional features. Label all candidate impact figures as preliminary.
- At session end, replace stale status above with dated evidence, changes made, remaining risks, and the immediate next step. Avoid a growing diary of contradictory claims.

Next action: verify a fresh live analysis for a second area/date, then revise the report with its observed outcome; rehearse and record the demo.
