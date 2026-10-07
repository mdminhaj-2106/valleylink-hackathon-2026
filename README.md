# ValleyLink

Satellite change → suspected road damage → settlement access. Built for Track B of the Multimodal AI Hackathon 2026.

This is an **early, unvalidated prototype**, not an emergency response tool. It currently combines Sentinel-1 radar, historical OpenStreetMap, road-access scenarios, and a grounded English/Nepali report and Q&A. The optional language model classifies questions only; all reported facts are rendered from computed map results.

## Run

Python 3.11+ is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export CDSE_CLIENT_ID='your-client-id'
export CDSE_CLIENT_SECRET='your-client-secret'
export OHSOME_API_KEY='your-ohsome-key'
# Optional: the Q&A works without this key, using a local intent classifier.
export OPENAI_API_KEY='your-openai-key'
streamlit run app.py
```

Create a free Copernicus Data Space account and an OAuth client in [Sentinel Hub user settings](https://shapps.dataspace.copernicus.eu/dashboard/#/account/settings). Also get a free [ohsome v2 API key](https://account.heigit.org/). Its legacy v1 geometry endpoint currently returns HTTP 403. Keep credentials out of Git. Select a WGS84 bounding box no larger than 0.5° by 0.5° and an event date. The app searches Sentinel-1 GRD, selects pre/post scenes from the same satellite and relative orbit, obtains terrain-corrected VV/VH radar data, calculates change, intersects pre-event OSM features, and computes road access.

Run the synthetic checks with `pip install pytest` and `python -m pytest tests -q`.

## What the result means

- Orange map areas indicate radar change consistent with possible water or rough debris. Radar change alone cannot prove the cause.
- Buildings, roads, and bridges are **potentially affected** when they intersect the stronger change layer.
- A settlement is **possibly cut off** if it had a route to a mapped town or hospital before suspected road closures and no route afterward **inside the selected area**. An outside-area detour may exist.
- The crossing scenario asks what would change if one suspected blocked segment were passable. It does not recommend using that segment.
- The strict/possible layers are threshold scenarios, not calibrated probabilities.

The inputs are Sentinel-1, Copernicus DEM for radar terrain correction, and OpenStreetMap state one day before the event via [ohsome v2](https://docs.ohsome.org/ohsome-api/v2/). Copernicus EMS and other published damage maps are **not used as inputs**. The [Copernicus processing documentation](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S1GRD.html) describes the radar calibration, terrain correction, and shadow mask used here. Scene IDs appear in the app for provenance.

## Known gaps before submission

1. Validate live scene search and processing with CDSE credentials; current automated checks use synthetic radar arrays.
2. Test the OSM historical extraction with an ohsome v2 API key on Trishuli and an unseen area.
3. Add Sentinel-2 when cloud conditions allow, and support larger AOIs by tiling. Current maximum is 0.5° × 0.5°.
4. Validate the English/Nepali Q&A and map-derived figures with human reviewers.
5. Compare the frozen Trishuli output with EMSR927 **only for evaluation**.
6. Check OSM completeness and possible detours outside the analysis area.
7. Finish the one-page situation report layout, up-to-six-page technical report, and three-minute demo video.

## Submission checklist

The Devpost project needs a description, this public GitHub source and run guide, a 3–10 minute YouTube video (unlisted is fine, private is not) with English audio or subtitles, and every teammate listed under their real full name with a Devpost account. The track brief asks for a three-minute demo, so target approximately three minutes.

## Required attribution

Contains modified Copernicus Sentinel data 2026.

Produced using Copernicus WorldDEM-30 © DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA; all rights reserved.

© OpenStreetMap contributors.
