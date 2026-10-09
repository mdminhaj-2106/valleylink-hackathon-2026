"""Run with: streamlit run app.py"""

from datetime import date
import importlib
from pathlib import Path

import numpy as np
import pydeck as pdk
import streamlit as st
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from copilot import answer_question_with_mode, report_html, situation_report
import valleylink
from valleylink import ATTRIBUTION, run


st.set_page_config(page_title="ValleyLink", page_icon="🛰️", layout="wide")
st.title("ValleyLink")
st.caption("Satellite evidence → suspected road disruption → settlement access")

with st.sidebar:
    st.header("Run an analysis")
    st.caption("Small bounding box, WGS84 longitude/latitude")
    west = st.number_input("West", value=85.318, format="%.5f")
    south = st.number_input("South", value=28.145, format="%.5f")
    east = st.number_input("East", value=85.353, format="%.5f")
    north = st.number_input("North", value=28.192, format="%.5f")
    flood_date = st.date_input("Flood date", value=date(2026, 8, 26))
    submitted = st.button("Run from satellite data", type="primary", use_container_width=True)

if submitted:
    try:
        bbox = (west, south, east, north)
        previous = None
        if (st.session_state.get("bbox") == bbox
                and st.session_state.get("flood_date") == flood_date
                and "analysis" in st.session_state and "imagery" in st.session_state):
            previous = (st.session_state.analysis, st.session_state.imagery)
        with st.spinner("Reusing previous radar images; retrying optical…" if previous else
                        "Finding same-orbit scenes and analysing roads…"):
            try:
                analysis, _, imagery = run(bbox, flood_date, previous=previous)
            except TypeError as exc:
                if "run() got an unexpected keyword argument 'previous'" not in str(exc):
                    raise
                analysis, _, imagery = importlib.reload(valleylink).run(
                    bbox, flood_date, previous=previous)
        st.session_state.analysis = analysis
        st.session_state.imagery = imagery
        st.session_state.bbox = bbox
        st.session_state.flood_date = flood_date
        st.session_state.pop("analysis_error", None)
    except Exception as exc:
        st.session_state.analysis_error = str(exc)

if "analysis_error" in st.session_state:
    st.error(f"New analysis failed: {st.session_state.analysis_error}")
    if "analysis" in st.session_state:
        st.warning("Showing the previous successful analysis below, not the failed request.")

if "analysis" not in st.session_state:
    st.info("Enter an area and date, then run the analysis. Copernicus OAuth credentials are required; see README.")
    st.stop()

result = st.session_state.analysis
west, south, east, north = st.session_state.bbox
st.caption(f"Showing analysis for {st.session_state.flood_date} · WGS84 box {west:.3f}, {south:.3f}, {east:.3f}, {north:.3f}")
scenes = result["scenes"]
st.caption(f"Sentinel-1 relative orbit {scenes['relative_orbit']} · Before: {scenes['before']} · After: {scenes['after']}")
if result["optical_dates"]:
    st.caption(f"Sentinel-2 · Before: {result['optical_dates'][0]} · After: {result['optical_dates'][1]}")
else:
    st.warning(f"No usable optical pair: {result['optical_error']}. Radar-only candidate impacts are lower confidence.")

cards = st.columns(5)
for column, label, value in zip(cards,
    ["Candidate change", "Buildings", "Road exposed", "Bridges", "Possibly cut off"],
    [f"{result['flood_km2']} km²", len(result["buildings"]),
     f"{result['affected_road_km']} km", len(result["affected_bridge_ids"]),
     len(result["cutoff"]) if result["access_available"] else "Unknown"],
):
    column.metric(label, value)

st.caption(f"Usable radar coverage: {result['valid_fraction']:.0%}. "
           + (f"Usable optical coverage: {result['optical_clear_fraction']:.0%}. "
              if result['optical_clear_fraction'] is not None else "")
           + "All impacts are candidates, not confirmed field damage.")

def preview(image):
    db = 10 * np.log10(np.maximum(image[0], 1e-8))
    return np.nan_to_num(np.clip((db + 25) / 25 * 255, 0, 255)).astype("uint8")

before_col, after_col = st.columns(2)
before_col.image(preview(st.session_state.imagery[0]), caption="Before: Sentinel-1 VV radar")
after_col.image(preview(st.session_state.imagery[1]), caption="After: Sentinel-1 VV radar")
if len(st.session_state.imagery) == 4:
    optical_before, optical_after = st.columns(2)
    def rgb(image):
        return np.clip(np.moveaxis(image[[2, 1, 0]], 0, -1) * 2.5, 0, 1)
    optical_before.image(rgb(st.session_state.imagery[2]), caption="Before: Sentinel-2 false color (NIR/red/green)")
    optical_after.image(rgb(st.session_state.imagery[3]), caption="After: Sentinel-2 false color (NIR/red/green)")

st.subheader("Which crossing matters most?")
scenarios = result["scenarios"]
selected = None
if scenarios:
    choice = st.selectbox("If a suspected blocked segment is passable…",
                          range(len(scenarios)),
                          format_func=lambda i: f"{scenarios[i]['feature_id']} · {scenarios[i]['restored']} settlements regain access")
    selected = scenarios[choice]
    st.success(f"Scenario: {selected['restored']} settlements regain a route to a town or hospital. "
               "This does not establish that the road is safe to use.")
elif not result["access_available"]:
    st.write("Road-access analysis unavailable: no mapped destination connects to this local network.")
else:
    st.write("No single suspected crossing restores access within this area.")

layers = []
if result["possible_geometry"]["type"] != "GeometryCollection":
    layers.append(pdk.Layer("GeoJsonLayer", {"type": "Feature", "geometry": result["possible_geometry"], "properties": {}},
                            filled=True, get_fill_color=[255, 189, 89, 70], get_line_color=[255, 189, 89, 200]))
if result["strict_geometry"]["type"] != "GeometryCollection":
    layers.append(pdk.Layer("GeoJsonLayer", {"type": "Feature", "geometry": result["strict_geometry"], "properties": {}},
                            filled=True, get_fill_color=[229, 103, 25, 165], get_line_color=[229, 103, 25, 255]))
if result["affected_roads"]:
    layers.append(pdk.Layer("GeoJsonLayer", {"type": "FeatureCollection", "features": result["affected_roads"]},
                            filled=False, get_line_color=[178, 34, 34, 255], get_line_width=4, line_width_min_pixels=3))
if result["buildings"]:
    layers.append(pdk.Layer("GeoJsonLayer", {"type": "FeatureCollection", "features": result["buildings"]},
                            filled=True, get_fill_color=[101, 59, 156, 165], get_line_color=[101, 59, 156, 255]))
cutoff_ids = {place["id"] for place in result["cutoff"]}
for cut_off, color in ((False, [22, 132, 91]), (True, [192, 42, 42])):
    places = [{"position": place["point"], "name": place["name"]}
              for place in result["settlements"] if (place["id"] in cutoff_ids) == cut_off]
    if places:
        layers.append(pdk.Layer("ScatterplotLayer", places, get_position="position", get_fill_color=color,
                                get_radius=70, radius_min_pixels=6, pickable=True))
if selected:
    a, b = selected["edge"]
    layers.append(pdk.Layer("PathLayer", [{"path": [a, b]}], get_path="path",
                            get_color=[0, 188, 212], get_width=7, width_min_pixels=5))
st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=pdk.ViewState(
    latitude=(south + north) / 2, longitude=(west + east) / 2, zoom=12),
    tooltip={"text": "{name}"}), height=580, width="stretch")
st.caption("Map key: amber = possible change · orange = stronger candidate · red = exposed road or possibly cut off settlement · purple = building · green = settlement with mapped access")

st.subheader("Situation report")
language = st.radio("Language", ["English", "Nepali"], horizontal=True)
body = situation_report(result, language)
st.text(body)
st.download_button("Download one-page report", report_html(result, language, st.session_state.bbox,
                                                             st.session_state.flood_date, ATTRIBUTION),
                   file_name="situation-report.html", mime="text/html")

st.subheader("Ask about the map")
question = st.text_input("Question", placeholder="Which villages may have lost road access?")
if question:
    answer, ai_used = answer_question_with_mode(result, question, language)
    st.caption("AI-assisted question interpretation" if ai_used else "Offline rule-based answer")
    st.write(answer)

with st.expander("Evidence and limitations"):
    st.write("This is a research prototype. Satellite change is not field-verified flood or road closure. "
             "Road access uses a bounded local map; detours beyond it may exist. "
             "Building and bridge counts depend on OpenStreetMap completeness. Satellite revisit time "
             "means the images may miss the flood peak.")
    st.text(ATTRIBUTION)
