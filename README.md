# ValleyLink

Satellite change → suspected road damage → settlement access. Built for Track B of the Multimodal AI Hackathon 2026.

This is a **research prototype**, not an emergency response tool. It combines Sentinel-1 radar, Sentinel-2 optical imagery when available, historical OpenStreetMap, road-access scenarios, and a grounded English/Nepali report and Q&A. The optional language model classifies questions only; all reported facts are rendered from computed map results.

## Run

Python 3.11+ is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your own keys; never commit or paste them into chat.
streamlit run app.py
```

Create a free Copernicus Data Space account and an OAuth client in [Sentinel Hub user settings](https://shapps.dataspace.copernicus.eu/dashboard/#/account/settings). Also get a free [ohsome v2 API key](https://account.heigit.org/). Its legacy v1 geometry endpoint currently returns HTTP 403. The app reads keys from `.env`, which Git ignores. The default WGS84 box covers Syapru Besi (EMSR927 AOI01) for the 26 August 2026 event. The app finds same-orbit Sentinel-1 before/after scenes, then uses cloud-screened Sentinel-2 vegetation-loss/new-water candidates where the default 12/27 August images are available. Radar change remains a lower-confidence context layer; if Sentinel-2 is unavailable, the app marks its impact estimates as radar-only.

Run the synthetic checks with `pip install pytest` and `python -m pytest tests -q`.

## What the result means

- Orange map areas indicate optical change consistent with possible water or debris where clear observations exist; yellow includes more uncertain radar change. Neither proves the cause.
- Buildings, roads, and bridges are **potentially affected** when they intersect the stronger change layer.
- A settlement is **possibly cut off** if it had a route to a mapped town or hospital before suspected road closures and no route afterward in the local road network. An outside-network detour may exist.
- The crossing scenario asks what would change if one suspected blocked segment were passable. It does not recommend using that segment.
- The optical/radar candidate layers are not calibrated probabilities.

The inputs are Sentinel-1, Sentinel-2, Copernicus DEM for radar terrain correction, and OpenStreetMap state one day before the event via [ohsome v2](https://docs.ohsome.org/ohsome-api/v2/). Copernicus EMS and other published damage maps are **not used as inputs**. The [Copernicus processing documentation](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S1GRD.html) describes the radar calibration, terrain correction, and shadow mask used here. Scene IDs and optical timestamps appear in the app for provenance.

## Preliminary independent check

The [official EMSR927 maps](https://mapping.emergency.copernicus.eu/activations/EMSR927/) were used **only after inference** to check the output. Against their *mass-movement polygons* (not a complete flood boundary), our fixed optical-change rule covers 65.5% of the mapped area in Syapru Besi AOI01 and 56.3% in held-out Timure AOI02. Conversely, 40.4% and 34.2% of our candidate optical-change area lies inside those polygons. These overlap diagnostics are **not damage accuracy or flood precision/recall**. The official grades and our OSM-derived building/road counts are not interchangeable. The 27 August optical image precedes the 28 August radar image, so they may show different stages of the event.

## Known gaps before submission

1. Validate building and road candidates against independent reference data; current impact counts remain unverified.
2. Test historical OSM completeness and road-access detours in a second region, not just Syapru Besi.
3. Support larger AOIs by tiling and search for clear optical dates beyond the fixed Trishuli 12/27 August pair. Current maximum is 0.5° × 0.5°.
4. Validate the English/Nepali Q&A and map-derived figures with human reviewers.
5. Complete an explicit per-feature evaluation against EMSR927 **only for evaluation**.
6. Check OSM completeness and possible detours outside the analysis area.
7. Finish the one-page situation report layout, up-to-six-page technical report, and three-minute demo video.

## Submission checklist

The Devpost project needs a description, this public GitHub source and run guide, a 3–10 minute YouTube video (unlisted is fine, private is not) with English audio or subtitles, and every teammate listed under their real full name with a Devpost account. The track brief asks for a three-minute demo, so target approximately three minutes.

## Required attribution

Contains modified Copernicus Sentinel data 2026.

Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.

© OpenStreetMap contributors.
