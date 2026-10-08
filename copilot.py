"""Grounded English/Nepali situation reports and question answering.

An optional model classifies questions into known intents. All factual text,
including every number, is rendered from the analysis result here.
"""

from __future__ import annotations

import json
import os
import re
from urllib.request import Request, urlopen


INTENTS = ("summary", "flood", "buildings", "roads", "bridges", "cutoff",
           "scenarios", "coverage", "scenes", "limitations", "unknown")
UNKNOWN = {
    "English": "The available analysis does not contain enough information to answer that question.",
    "Nepali": "उपलब्ध विश्लेषणमा यो प्रश्नको उत्तर दिन पर्याप्त जानकारी छैन।",
}


def _language(language):
    if language not in UNKNOWN:
        raise ValueError("Language must be English or Nepali.")
    return language


def _fact(result, key):
    value = result.get(key)
    return value if value is not None else None


def _count(result, key):
    value = _fact(result, key)
    return len(value) if isinstance(value, list) else None


def _line(result, intent, language):
    nepali = language == "Nepali"
    if intent in ("cutoff", "scenarios") and result.get("access_available") is False:
        return ("सडक पहुँच विश्लेषणका लागि पर्याप्त सडक वा गन्तव्य विवरण छैन।" if nepali else
                "Road access analysis is unavailable because road or destination data is insufficient.")
    if intent == "flood" and (value := _fact(result, "flood_km2")) is not None:
        if result.get("evidence_mode") == "optical":
            return (f"सम्भावित बाढी वा भग्नावशेषसँग मेल खाने अप्टिकल परिवर्तन: {value} वर्ग किमी।" if nepali else
                    f"Optical change consistent with possible flood or debris: {value} km².")
        return (f"सम्भावित बाढी वा भग्नावशेषसँग मेल खाने राडार परिवर्तन: {value} वर्ग किमी।" if nepali else
                f"Radar change consistent with possible flood or debris: {value} km².")
    if intent == "buildings" and (value := _count(result, "buildings")) is not None:
        return (f"सम्भावित रूपमा प्रभावित भवन: {value}।" if nepali else
                f"Potentially affected buildings: {value}.")
    if intent == "roads" and (value := _fact(result, "affected_road_km")) is not None:
        return (f"सम्भावित रूपमा प्रभावित सडक: {value} किमी।" if nepali else
                f"Potentially affected road: {value} km.")
    if intent == "bridges" and (value := _count(result, "affected_bridge_ids")) is not None:
        return (f"सम्भावित रूपमा प्रभावित पुल: {value}।" if nepali else
                f"Potentially affected bridges: {value}.")
    if intent == "cutoff" and (items := _fact(result, "cutoff")) is not None:
        if not isinstance(items, list):
            return None
        names = [str(item.get("name", item.get("id", ""))) for item in items if isinstance(item, dict)]
        names = [name for name in names if name]
        prefix = (f"स्थानीय नक्सामा भएको सडक सञ्जालभित्र शहर वा अस्पतालसम्मको पहुँच गुमाएको हुन सक्ने बस्ती: {len(items)}।" if nepali else
                  f"Settlements that may have lost mapped road access to a town or hospital in the local road network: {len(items)}.")
        return prefix + ((" बस्तीहरू: " if nepali else " Settlements: ") + ", ".join(names) + "." if names else "")
    if intent == "scenarios" and (items := _fact(result, "scenarios")) is not None:
        if not isinstance(items, list):
            return None
        if not items:
            return ("एउटा मात्र अवरुद्ध सडक खण्ड खोल्दा पहुँच फर्किने अवस्था भेटिएन।" if nepali else
                    "No single suspected crossing restores settlement access in this area.")
        best = items[0]
        if not isinstance(best, dict) or not isinstance(best.get("restored"), int) or not best.get("feature_id"):
            return None
        return (f"यदि {best['feature_id']} सडक खण्ड पार गर्न मिल्ने भए, {best['restored']} बस्तीको पहुँच फर्किन सक्छ। यो सुरक्षा पुष्टि होइन।" if nepali else
                f"If suspected crossing {best['feature_id']} is passable, {best['restored']} settlements may regain access. This does not confirm that crossing is safe.")
    if intent == "coverage" and (value := _fact(result, "valid_fraction")) is not None:
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            return None
        optical = result.get("optical_clear_fraction")
        if isinstance(optical, (int, float)) and 0 <= optical <= 1:
            return (f"प्रयोगयोग्य राडार क्षेत्र: {value:.0%}; अप्टिकल क्षेत्र: {optical:.0%}।" if nepali else
                    f"Usable radar coverage: {value:.0%}; optical coverage: {optical:.0%}.")
        return (f"प्रयोगयोग्य राडार क्षेत्र: {value:.0%}।" if nepali else
                f"Usable radar coverage: {value:.0%}.")
    if intent == "scenes" and isinstance((scenes := _fact(result, "scenes")), dict):
        before, after, orbit = (scenes.get(k) for k in ("before", "after", "relative_orbit"))
        if before and after and orbit is not None:
            return (f"सेन्टिनेल-१ तुलनामा पहिले {before}, पछि {after}, सापेक्ष कक्षा {orbit} प्रयोग भयो।" if nepali else
                    f"Sentinel-1 comparison: before {before}; after {after}; relative orbit {orbit}.")
    if intent == "limitations":
        return ("यी उपग्रह र सडक-सञ्जालमा आधारित प्रारम्भिक अनुमान हुन्। वास्तविक क्षति, सडकको सुरक्षा र नक्सा क्षेत्रबाहिरका वैकल्पिक बाटो स्थलमै जाँच्नुपर्छ।" if nepali else
                "These are preliminary satellite and road-network estimates. Field checks are needed for damage, road safety, and alternative routes outside the mapped area.")
    if intent == "provenance" and _fact(result, "scenes") is not None:
        if result.get("optical_dates"):
            before, after = result["optical_dates"]
            return (f"आधार: माथिका सेन्टिनेल-१ दृश्य, {before} र {after} का सेन्टिनेल-२ दृश्य, र घटनाअघिको ओपनस्ट्रिटम्याप विवरण।" if nepali else
                    f"Inputs: the Sentinel-1 scenes listed above, Sentinel-2 images from {before} and {after}, and a pre-event OpenStreetMap snapshot.")
        return ("आधार: माथि उल्लेखित सेन्टिनेल-१ दृश्य र घटनाअघिको ओपनस्ट्रिटम्याप विवरण।" if nepali else
                "Inputs: the Sentinel-1 scenes listed above and a pre-event OpenStreetMap snapshot.")
    return None


def situation_report(result, language="English"):
    """Build a concise report exclusively from available analysis fields."""
    _language(language)
    title = "प्रारम्भिक बाढी स्थिति प्रतिवेदन" if language == "Nepali" else "Preliminary flood situation report"
    lines = [_line(result, intent, language) for intent in
             ("flood", "buildings", "roads", "bridges", "cutoff", "coverage", "scenes", "provenance")]
    lines = [line for line in lines if line]
    return title + "\n\n" + ("\n".join(lines) if lines else UNKNOWN[language]) + "\n\n" + _line(result, "limitations", language)


def _local_intent(question):
    q = question.casefold()
    patterns = (
        ("scenarios", r"crossing|passab|reconnect|restore|priority|खोल|पार गर्न|पहुँच फर्क"),
        ("cutoff", r"cut.off|isolat|village|settlement|बस्ती|गाउँ|पहुँच"),
        ("bridges", r"bridge|पुल"),
        ("roads", r"road|highway|सडक|बाटो"),
        ("buildings", r"building|house|घर|भवन"),
        ("flood", r"flood|debris|area|water|बाढी|डुबान|क्षेत्र|पानी"),
        ("coverage", r"coverage|valid|shadow|गुणस्तर|उपयोगी"),
        ("scenes", r"satellite|sentinel|image|orbit|date|उपग्रह|चित्र|कक्षा|मिति"),
        ("limitations", r"limit|uncertain|confiden|verify|reliab|पुष्टि|सीमा|विश्वास"),
        ("summary", r"summary|report|overview|स्थिति|सारांश|प्रतिवेदन"),
    )
    return next((intent for intent, pattern in patterns if re.search(pattern, q)), "unknown")


def _model_intent(question):
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    schema = {"type": "object", "properties": {"intent": {"type": "string", "enum": list(INTENTS)}},
              "required": ["intent"], "additionalProperties": False}
    payload = {"model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
               "instructions": "Classify the user question into one intent. Return unknown for facts outside a satellite flood and road-access analysis. Do not answer the question.",
               "input": question,
               "text": {"format": {"type": "json_schema", "name": "question_intent", "strict": True,
                                   "schema": schema}},
               "max_output_tokens": 64}
    request = Request("https://api.openai.com/v1/responses", data=json.dumps(payload).encode(),
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:
            data = json.load(response)
        for item in data.get("output", []):
            for block in item.get("content", []):
                if block.get("type") == "output_text":
                    intent = json.loads(block["text"])["intent"]
                    return intent if intent in INTENTS else None
    except (OSError, ValueError, KeyError, TypeError):
        pass  # Offline or unavailable API: the deterministic classifier remains usable.
    return None


def answer_question(result, question, language="English"):
    """Answer from calculated facts; the optional model never writes answer text."""
    _language(language)
    if not question.strip():
        return UNKNOWN[language]
    if re.search(r"people|population|casualt|death|fatalit|injur|मानिस|जनसंख्या|मृत्यु|घाइते",
                 question.casefold()):
        return UNKNOWN[language]
    if re.search(r"confirm|verified|destroy|safe|operational|प्रमाणित|पुष्टि|सुरक्षित",
                 question.casefold()):
        return _line(result, "limitations", language)
    intent = _model_intent(question) or _local_intent(question)
    if intent == "summary":
        return situation_report(result, language)
    return _line(result, intent, language) or UNKNOWN[language]
