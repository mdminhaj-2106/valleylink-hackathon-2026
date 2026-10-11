# ValleyLink project memory

Last reviewed: 2026-10-11 (Asia/Kolkata). This is the current handoff; update it after each work session. Statements marked **unverified** need a fresh check before being presented as current.

## Project and goal

- Track B, Multimodal AI Hackathon 2026: map flood/debris change, potentially affected infrastructure, and possibly cut-off settlements from an area and event date.
- Repository: `https://github.com/mdminhaj-2106/valleylink-hackathon-2026`; local checkout: this directory.
- Deadline supplied by the user: 15 October 2026. Team: two humans plus Codex. Human names and Devpost accounts have not been provided here.
- Source briefs: `/Users/sufi_spryzen/Downloads/Track B.pdf` and `/Users/sufi_spryzen/Downloads/Multimodal AI Hackathon 2026 - Submission Guidelines.pdf`.

## Verified implementation

- Submission drafts and this memory were pushed to `main` as `8dd2b84` on 11 October 2026. Check Git state again before editing or publishing.
- The Streamlit app starts with a bundled, live-derived Syapru Besi case (`syapru_besi_reference.npz`) without credentials or network access. It provides Sentinel-1 and Sentinel-2 before/after images, candidate change and OSM overlays, road access scenarios, English/Nepali situation reports and Q&A, and a one-page HTML report.
- Live analysis accepts an area/date (maximum 0.5° × 0.5°), discovers a same-satellite/same-orbit Sentinel-1 pair using CDSE STAC with Catalog fallback, processes radar and an optional clear Sentinel-2 pair, and queries pre-event OSM via ohsome. A failed rerun retains the last displayed successful result.
- Bundled case figures: 1.8 km² candidate change, 164 potentially affected buildings, 5.82 km potentially affected roads, 4 candidate bridges, 3 possibly cut-off settlements; 96% usable radar and 81% usable optical coverage. These are screening estimates, **not** confirmed damage or access loss.
- The README reports preliminary overlap against EMSR927 mass-movement polygons: 65.5% of mapped area covered in Syapru Besi AOI01 and 56.3% in Timure AOI02; 40.4% and 34.2% of candidate change inside those polygons. This is neither damage accuracy nor flood precision/recall. EMSR927 is evaluation only, never an inference input.
- On 11 October, an AOI01 per-feature check of the local EMSR927 v1 grading archive found 78/164 candidate OSM building footprints contain an EMS affected-building point; 80/433 EMS affected-building points fall inside candidate footprints. All 14 EMS "Destroyed" road lines touch the candidate mask, but so do 3/9 marked "No visible damage"; 3/5 destroyed-bridge points touch it. Different inventories, geometry and dates prevent accuracy claims; a road line counts if any portion touches. These results are documented in the technical report.
- On 11 October, a new environment outside the synced Documents folder ran the full suite after the UI edit: **40 tests passed in 12.22 s**. The dashboard started and returned HTTP 200. The old `.venv` had macOS `dataless` package files, causing earlier import/test/server stalls; the active `.venv` now links to `~/Library/Caches/ValleyLink/venv`. The offloaded old environment remains in ignored `.venv.offloaded` as a local backup.
- The synced folder also offloaded `.git/index` once; it was rebuilt from HEAD with `git reset --mixed HEAD` without discarding source edits. If Git becomes slow again, check macOS `dataless` flags before treating it as a repository defect. Moving the checkout out of the synced folder remains a future environment cleanup, not a product-code requirement.
- A second nearby box `(85.35, 28.15, 85.39, 28.21)` for 26 August completed the live pipeline on 11 October: token 2.1 s, discovery 4.6 s, both radar scenes 12.3 s, optical 30.0 s, historical OSM 38.0 s, complete 44.7 s. A separate call to the app's actual `run()` also succeeded with optical output: 2.41 km² candidate change, 20 mapped building intersections, one possibly cut-off settlement. This is a smoke test, not independent impact validation.
- The browser dashboard also completed a live run for that exact box and displayed those results with 2.6 km of candidate road exposure and one bridge feature. A live form was added after the last coordinate initially failed to submit; the corrected form was checked in the browser and a focused test now covers the last-edited coordinate.

## Current risks and unfinished work

1. **Judge-selected live run:** Track B requires an end-to-end run from raw satellite data for the judges' area/date. Syapru Besi and one nearby second box succeeded, but arbitrary area/date reliability remains **unverified**; external services can still time out. Rehearse a judge-style run in the app UI before recording.
2. **Submission:** `docs/TECHNICAL_REPORT.md` and a two-page `docs/TECHNICAL_REPORT.pdf` draft were created and visually checked on 11 October. `docs/DEMO_AND_DEVPOST.md` contains a Devpost description and timed demo script. Human review remains; the video has not been recorded or uploaded, and Devpost has not been submitted. Add both humans' real names and Devpost accounts before submission.
3. **Validation:** preliminary EMSR927 feature checks now exist for one AOI, but the 164 OSM building count and road-access conclusions are not confirmed damage or isolation. Human review of English/Nepali claims is outstanding. Evaluate more areas and investigate map-inventory differences before claiming performance.
4. **Known limits:** optical gaps/clouds, satellite revisit delay, OSM incompleteness, detours outside the AOI, 0.5° area cap, and dependence on Copernicus/ohsome. Upstream DEM flood-path tracing is optional.

## Rules for the next session

- Start by checking `git status`, HEAD/remote, available disk space, and whether the app and tests actually run. Never infer freshness from this file alone.
- Keep `.env` and API keys out of commits, logs, reports, and chat. Do not use EMS/UNOSAT damage maps as model inputs or post-event OSM edits.
- Prioritize a dependable live judge path and the required deliverables over optional features. Label all candidate impact figures as preliminary.
- At session end, replace stale status above with dated evidence, changes made, remaining risks, and the immediate next step. Avoid a growing diary of contradictory claims.

Next action: validate candidate infrastructure/access against independent evidence, have a human review the English/Nepali claims, then rehearse and record the demo. The map now appears ahead of the optional imagery gallery in the dashboard. The whole project is **not complete or submission-ready** while those checks, the video, Devpost and teammate details remain outstanding.
