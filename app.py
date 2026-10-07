"""Run with: streamlit run app.py"""

from datetime import date

import folium
import numpy as np
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from copilot import answer_question, situation_report
from valleylink import ATTRIBUTION, run


st.set_page_config(page_title="ValleyLink", page_icon="🛰️", layout="wide")
st.title("ValleyLink")
st.caption("Satellite evidence → suspected road disruption → settlement access")

with st.sidebar:
    st.header("Run an analysis")
    st.caption("Small bounding box, WGS84 longitude/latitude")
    west = st.number_input("West", value=85.10, format="%.5f")
    south = st.number_input("South", value=27.90, format="%.5f")
    east = st.number_input("East", value=85.25, format="%.5f")
    north = st.number_input("North", value=28.05, format="%.5f")
    flood_date = st.date_input("Flood date", value=date(2026, 8, 26))
    submitted = st.button("Run from satellite data", type="primary", use_container_width=True)

if submitted:
    try:
        with st.spinner("Finding same-orbit scenes and analysing roads…"):
            st.session_state.analysis, _, st.session_state.imagery = run((west, south, east, north), flood_date)
            st.session_state.bbox = (west, south, east, north)
    except Exception as exc:
        st.error(str(exc))

if "analysis" not in st.session_state:
    st.info("Enter an area and date, then run the analysis. Copernicus OAuth credentials are required; see README.")
    st.stop()

result = st.session_state.analysis
west, south, east, north = st.session_state.bbox
scenes = result["scenes"]
st.caption(f"Sentinel-1 relative orbit {scenes['relative_orbit']} · Before: {scenes['before']} · After: {scenes['after']}")

cards = st.columns(5)
for column, label, value in zip(cards,
    ["Changed area", "Buildings", "Road exposed", "Bridges", "Possibly cut off"],
    [f"{result['flood_km2']} km²", len(result["buildings"]),
     f"{result['affected_road_km']} km", len(result["affected_bridge_ids"]),
     len(result["cutoff"]) if result["access_available"] else "Unknown"],
):
    column.metric(label, value)

st.caption(f"Valid radar coverage: {result['valid_fraction']:.0%}. All impacts are potential, not confirmed field damage.")

def preview(image):
    db = 10 * np.log10(np.maximum(image[0], 1e-8))
    return np.clip((db + 25) / 25 * 255, 0, 255).astype("uint8")

before_col, after_col = st.columns(2)
before_col.image(preview(st.session_state.imagery[0]), caption="Before: Sentinel-1 VV radar")
after_col.image(preview(st.session_state.imagery[1]), caption="After: Sentinel-1 VV radar")

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
else:
    st.write("No single suspected crossing restores access within this area.")

map_view = folium.Map(location=[(south + north)/2, (west + east)/2], zoom_start=11,
                      tiles="CartoDB positron")
if result["possible_geometry"]["type"] != "GeometryCollection":
    folium.GeoJson(result["possible_geometry"], name="Possible change",
                   style_function=lambda _: {"color": "#ffbd59", "fillOpacity": 0.25, "weight": 1}).add_to(map_view)
if result["strict_geometry"]["type"] != "GeometryCollection":
    folium.GeoJson(result["strict_geometry"], name="Stronger change",
                   style_function=lambda _: {"color": "#e56719", "fillOpacity": 0.65, "weight": 1}).add_to(map_view)
if result["affected_roads"]:
    folium.GeoJson({"type": "FeatureCollection", "features": result["affected_roads"]},
                   name="Potentially affected roads",
                   style_function=lambda _: {"color": "#b22222", "weight": 3}).add_to(map_view)
if result["buildings"]:
    folium.GeoJson({"type": "FeatureCollection", "features": result["buildings"]},
                   name="Potentially affected buildings",
                   style_function=lambda _: {"color": "#653b9c", "fillOpacity": 0.6}).add_to(map_view)
for place in result["cutoff"]:
    folium.CircleMarker(location=[place["point"][1], place["point"][0]], radius=6,
                        color="#c02a2a", fill=True, tooltip=f"Possibly cut off: {place['name']}").add_to(map_view)
if selected:
    a, b = selected["edge"]
    folium.PolyLine([[a[1], a[0]], [b[1], b[0]]], color="#00bcd4", weight=7,
                    tooltip="Scenario crossing").add_to(map_view)
folium.LayerControl().add_to(map_view)
st.components.v1.html(map_view._repr_html_(), height=580)

st.subheader("Situation report")
language = st.radio("Language", ["English", "Nepali"], horizontal=True)
body = situation_report(result, language)
st.text(body)
st.download_button("Download report", body + "\n\n" + ATTRIBUTION, file_name="situation-report.txt")

st.subheader("Ask about the map")
question = st.text_input("Question", placeholder="Which villages may have lost road access?")
if question:
    st.write(answer_question(result, question, language))

with st.expander("Evidence and limitations"):
    st.write("This is a research prototype. Radar change is not field-verified flood or road closure. "
             "Road access is computed only within the selected map area; routes outside it may exist. "
             "Building and bridge counts depend on OpenStreetMap completeness. Satellite revisit time "
             "means the images may miss the flood peak.")
    st.text(ATTRIBUTION)
