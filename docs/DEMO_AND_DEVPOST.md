# Submission copy and three-minute demo plan

Status: draft for human review. The video has not been recorded or uploaded, and Devpost has not been submitted. Add both human teammates' real full names and Devpost accounts before submission.

## Devpost project description

**ValleyLink** turns before/after satellite images into a rapid, source-attributed screening map for flood and debris response. A user selects an area and event date. The app finds a same-orbit Sentinel-1 radar pair, uses clear Sentinel-2 imagery when available, and overlays pre-event OpenStreetMap buildings and roads. It highlights candidate surface change, mapped assets that intersect it, and villages that could lose a mapped road connection to a town or hospital if suspected road segments are closed.

A constrained English/Nepali copilot answers questions and creates a one-page situation report using only map-derived numbers. The optional language model classifies question intent; it cannot invent impact counts. The dashboard exposes acquisition dates, coverage and uncertainty. A fixed, live-derived Syapru Besi case opens without credentials for demonstration, while live mode analyzes a new area/date from raw satellite and historical OSM data.

For the August 2026 Syapru Besi case, the prototype flags 1.8 km² of candidate change, 164 potentially affected mapped buildings, 5.82 km of mapped road and three possibly cut-off settlements. These are **unverified screening estimates**, not confirmed damage. Preliminary spatial overlap with EMSR927 mass-movement polygons is reported in the technical report; EMSR927 was used only for evaluation. ValleyLink is an educational prototype and is not an emergency response tool.

**Source and setup:** https://github.com/mdminhaj-2106/valleylink-hackathon-2026

## Video shot list and narration (~3 minutes)

| Time | Screen action | English narration |
|:---|:---|:---|
| 0:00–0:20 | Title and loaded Syapru Besi dashboard | “When ground access is uncertain after a flood, responders need a fast map of possible damage and isolation. ValleyLink screens satellite change and mapped road access, with its uncertainty visible.” |
| 0:20–0:45 | Show date, box and source label | “This case is a real-data snapshot for the 26 August 2026 Nepal event. The app also accepts a new area and date and runs from Sentinel imagery and historical OpenStreetMap data.” |
| 0:45–1:15 | Show radar and optical before/after images | “Same-orbit Sentinel-1 radar provides coverage through clouds. When clear Sentinel-2 imagery exists, we add optical vegetation and water-index change. The app displays acquisition dates and usable coverage.” |
| 1:15–1:45 | Pan candidate-change map and metrics | “For this case, the stronger candidate layer covers 1.8 square kilometres and intersects 164 mapped buildings, 5.82 kilometres of road and four bridge features. These are possible impacts, not verified damage.” |
| 1:45–2:15 | Show settlement access and crossing scenario | “We remove suspected road segments from the mapped network and check which villages lose a route to a mapped town or hospital. Three are possibly cut off. A crossing scenario shows which connection matters most; it is not advice to use an unsafe road.” |
| 2:15–2:40 | Ask one question; switch language; download report | “The copilot answers from computed map results and can produce a one-page English or Nepali report. A model may classify the question, but it never supplies the numbers.” |
| 2:40–3:00 | Show limitations and GitHub README | “We checked spatial overlap against EMSR927 only after inference. Clouds, revisit delay, incomplete maps and external API availability limit this prototype. The public repository explains how to reproduce it.” |

Record a separate live area/date run only if it succeeds during rehearsal. Do not edit a failed live request into a claim that arbitrary-area processing was demonstrated. Export at least 3:00 and at most 10:00, with English audio or subtitles, then upload to YouTube as public or unlisted (not private).

## Before submitting

- Verify a live area/date run and note the actual outcome in the technical report and project memory.
- Review the report and Nepali wording with the human team; replace any unsupported figure.
- Record and inspect the video, then add its YouTube URL to Devpost.
- Add every human teammate under their real full name and Devpost account.
- Confirm public GitHub access and submit before 15 October 2026.
