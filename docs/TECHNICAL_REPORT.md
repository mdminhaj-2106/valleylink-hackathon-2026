---
title: "ValleyLink: satellite change and road-access screening"
subtitle: "Multimodal AI Hackathon 2026 · Track B technical report"
date: "11 October 2026"
geometry: margin=0.65in
fontsize: 10pt
colorlinks: true
---

## 1. Purpose and output

ValleyLink is an educational prototype for rapidly screening a flood or debris event in a user-selected area and date. It answers three operational questions: where imagery changed, which mapped buildings/roads/bridges intersect that change, and which mapped settlements could lose a road connection to a town or hospital. It displays evidence, coverage, provenance and limitations alongside the estimates. It does **not** confirm damage, prove a road is closed, or replace field assessment.

The Streamlit dashboard shows Sentinel-1 radar and, when usable, Sentinel-2 optical before/after imagery; a candidate-change map; infrastructure and road-access overlays; crossing scenarios; map-derived Q&A; and downloadable one-page English or Nepali situation reports. A bundled Syapru Besi case allows a dependable, credential-free demonstration. The live path retrieves imagery and historical OSM for a new area/date; the bundled case is a fixed snapshot, not a substitute for live analysis.

## 2. Inputs and reproducible pipeline

1. **Area and date.** The user supplies a WGS84 bounding box (currently at most 0.5° by 0.5°) and flood date. Invalid bounds and oversized areas are rejected.
2. **Radar.** Copernicus Data Space STAC discovery (authenticated Catalog fallback) finds Sentinel-1 IW, dual VV/VH scenes. The pre/post pair must share satellite, relative orbit and direction. Copernicus Process API returns aligned 512-pixel-width rasters with terrain correction, gamma-nought backscatter, data and shadow masks. Invalid/shadowed pixels are excluded. A darker VV return can indicate new smooth water; brighter VV *and* VH can indicate rough debris or surface change. A 3 dB threshold defines the stronger radar candidate; 2 dB defines a broader possible-change layer. These fixed rules are not calibrated probabilities.
3. **Optical.** When available, a clear Sentinel-2 pair provides green, red, near-infrared, shortwave-infrared, scene-classification and data-mask bands. Valid-pixel screening excludes cloud/invalid classes. The stronger optical candidate is new water (post NDWI > 0.1 and pre NDWI < 0) or vegetation loss (pre NDVI > 0.25 and decrease > 0.2). Radar remains a broader context layer. If no usable optical pair is found, the app labels the result radar-only and lower confidence.
4. **Infrastructure.** The ohsome API supplies buildings, roads, bridges, settlements and hospitals from OSM state at UTC midnight one day before the event. This prevents later OSM edits from entering inference. Features intersecting the stronger change mask are counted as *potentially affected*. Such intersection is a screening signal, not proof of physical damage.
5. **Access.** Road line segments form a graph. Segments intersecting the stronger candidate mask are removed in a hypothetical closure scenario. A village/hamlet is *possibly cut off* if it had a graph route to a mapped town/city or hospital beforehand and none afterward. A crossing scenario shows how many settlements would reconnect if one suspected segment were passable. The graph uses local mapped roads; off-map detours and real road passability are unknown.
6. **AI and reports.** The situation-report copilot maps questions to a constrained set of intents. An optional language model may classify the intent, but it does not write factual answers or numbers. English/Nepali answers and one-page reports render only computed result fields; unsupported questions receive an explicit insufficient-information answer.

Copernicus EMS and UNOSAT damage products are not used as inputs. The app retains the previous successful result, clearly labeled, if a new live request fails.

## 3. August 2026 Nepal case study

For the 26 August event, the bundled live-derived Syapru Besi reference snapshot uses a small WGS84 area around 85.318–85.353°E, 28.145–28.192°N. The optical pair was acquired on 12 and 27 August; the radar post-event scene was acquired on 28 August. Because these images capture different times, their change layers can reflect different event stages.

| Screening output | Bundled case |
|:---|---:|
| Candidate change area | 1.8 km² |
| Potentially affected OSM buildings | 164 |
| Potentially affected mapped road length | 5.82 km |
| Candidate bridge features | 4 |
| Possibly cut-off mapped settlements | 3 |
| Usable radar / optical coverage | 96% / 81% |

These figures are exploratory. They are not a count of confirmed destroyed buildings, blocked roads or isolated people. The dashboard provides scene identifiers and acquisition times for auditability.

## 4. Independent check and evidence limits

We compared the fixed optical-change rule after inference with Copernicus Emergency Management Service activation EMSR927 *mass-movement polygons*. In Syapru Besi AOI01, candidate change covers 65.5% of the mapped polygon area, while 40.4% of candidate area falls inside those polygons. For Timure AOI02, the corresponding figures are 56.3% and 34.2%. This is a preliminary spatial-overlap diagnostic, not flood precision/recall: the reference polygons depict one hazard class and are not an exhaustive pixel-level truth set. EMSR927 did not train, tune or feed the algorithm.

No independent per-building or per-road damage labels have yet been checked, and road-access conclusions have not been field validated. The optical and radar rules need evaluation on more dates, terrain types and cloud conditions. The current automated checks cover code behavior; they do not establish real-world mapping accuracy.

## 5. What the system cannot do

- Sentinel revisit and processing delay prevent minute-scale warning of a sudden glacier collapse or flood peak. Cloud and terrain shadow leave unmapped areas; optical and radar evidence may disagree by date.
- Surface change can arise from seasonal vegetation, sediment, construction or imaging effects. Intersections with mapped assets do not establish damage severity or safety.
- OSM can omit or misplace roads, bridges, buildings, settlements and hospitals. A locally disconnected graph may still have a route outside the AOI. The method has no population or travel-time model.
- Live judge-selected runs require functioning Copernicus and ohsome services, valid credentials and a usable same-orbit radar pair. Requests can time out; a bundled reference case cannot satisfy a fresh-area test. Larger areas need tiling beyond the present 0.5° cap.
- English/Nepali wording and candidate counts need human review before any operational use. ValleyLink is an educational prototype, not an emergency response tool.

## 6. Reproduction, references and attribution

The public [repository](https://github.com/mdminhaj-2106/valleylink-hackathon-2026) contains setup instructions, dependencies, the dashboard, tests and the source-attributed reference case. Create a Python 3.11+ environment, install `requirements.txt`, then run `streamlit run app.py`. The bundled case needs no keys; new live analyses require Copernicus OAuth and an ohsome API key in a local `.env` file. No training dataset was used; the rules are fixed, so no training-dataset citation is claimed.

Data and methods: [Copernicus Data Space Sentinel APIs](https://documentation.dataspace.copernicus.eu/APIs.html); [ohsome API](https://docs.ohsome.org/ohsome-api/v2/); [OpenStreetMap](https://www.openstreetmap.org/copyright); [EMSR927](https://mapping.emergency.copernicus.eu/activations/EMSR927/) (evaluation only).

Contains modified Copernicus Sentinel data 2026.

Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.

© OpenStreetMap contributors. EMSR927 comparison: European Union, Copernicus Emergency Management Service data.
