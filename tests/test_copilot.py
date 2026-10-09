import unittest
from unittest.mock import patch

from copilot import answer_question, answer_question_with_mode, report_html, situation_report


FACTS = {
    "flood_km2": 1.25,
    "buildings": [{"id": "one"}, {"id": "two"}],
    "affected_road_km": 3.5,
    "affected_bridge_ids": ["way/7"],
    "cutoff": [{"id": "node/1", "name": "Village A"}],
    "scenarios": [{"feature_id": "way/7", "restored": 1}],
    "valid_fraction": 0.8,
    "scenes": {"before": "S1_PRE", "after": "S1_POST", "relative_orbit": 42},
}


class CopilotTests(unittest.TestCase):
    @patch.dict("os.environ", {"OPENAI_API_KEY": ""})
    def test_report_and_questions_use_only_computed_numbers(self):
        report = situation_report(FACTS)
        self.assertIn("1.25 km²", report)
        self.assertIn("2", report)
        self.assertIn("3.5 km", report)
        self.assertIn("80%", report)
        self.assertIn("pre-event OpenStreetMap", report)
        self.assertIn("in the local road network", report)
        self.assertIn("Village A", answer_question(FACTS, "Which villages are cut off?"))
        self.assertIn("way/7", answer_question(FACTS, "Which crossing restores access?"))
        self.assertIn("बस्ती: 1", answer_question(FACTS, "कति बस्तीको पहुँच बन्द भयो?", "Nepali"))

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""})
    def test_missing_data_never_becomes_zero_or_guess(self):
        self.assertIn("does not contain", answer_question({}, "How many bridges?"))
        self.assertNotIn("0", situation_report({}))
        self.assertIn("पर्याप्त जानकारी छैन", answer_question({}, "कति पुल?", "Nepali"))
        self.assertIn("does not contain", answer_question(FACTS, "How many people died?"))
        self.assertIn("does not contain", answer_question(FACTS, "How many people are cut off?"))
        self.assertIn("Field checks", answer_question(FACTS, "How many bridges are confirmed destroyed?"))
        self.assertIn("Field checks", answer_question(FACTS, "Are these roads safe?"))

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""})
    def test_unavailable_road_access_is_not_reported_as_zero(self):
        result = {**FACTS, "access_available": False, "cutoff": [], "scenarios": []}
        for text in (situation_report(result),
                     answer_question(result, "How many settlements are cut off?"),
                     answer_question(result, "Which crossing restores access?")):
            self.assertIn("unavailable", text)
            self.assertNotIn("0 settlements", text)
            self.assertNotIn("No single", text)
        self.assertIn("पर्याप्त", answer_question(result, "कति बस्तीको पहुँच बन्द भयो?", "Nepali"))

    @patch("copilot._model_intent", return_value="bridges")
    def test_model_only_selects_a_grounded_intent(self, _model):
        self.assertEqual(answer_question(FACTS, "Invent a different bridge count"),
                         "Potentially affected bridges: 1.")
        self.assertEqual(answer_question_with_mode(FACTS, "How many bridges?"),
                         ("Potentially affected bridges: 1.", True))

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""})
    def test_offline_answer_is_labeled_rule_based(self):
        self.assertEqual(answer_question_with_mode(FACTS, "How many bridges?"),
                         ("Potentially affected bridges: 1.", False))

    @patch.dict("os.environ", {"OPENAI_API_KEY": ""})
    def test_optical_impact_provenance_and_bilingual_scenes(self):
        result = {**FACTS, "evidence_mode": "optical",
                  "optical_dates": ["2026-08-12T00:00:00Z", "2026-08-27T00:00:00Z"],
                  "optical_clear_fraction": 0.65}
        report = situation_report(result)
        self.assertIn("Optical change", report)
        self.assertIn("candidate impact layer comes from Sentinel-2", report)
        self.assertIn("Sentinel-2: before 2026-08-12", answer_question(result, "Which images were used?"))
        self.assertIn("candidate impact layer comes from Sentinel-2", answer_question(result, "What evidence supports the impact map?"))
        self.assertIn("सेन्टिनेल-२: पहिले 2026-08-12", answer_question(result, "कुन उपग्रह चित्र?", "Nepali"))
        self.assertIn("65%", situation_report(result, "Nepali"))

    def test_print_report_escapes_untrusted_fields_and_uses_computed_facts(self):
        result = {**FACTS, "cutoff": [{"name": "<script>alert(1)</script>"}]}
        page = report_html(result, "English", [85.1, 28.1, 85.2, 28.2],
                           "2026-08-26", "© <OpenStreetMap>")
        self.assertIn("size:A4", page)
        self.assertIn("1.25 km²", page)
        self.assertIn("Event date:</b> 2026-08-26", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        self.assertIn("© &lt;OpenStreetMap&gt;", page)
        self.assertNotIn("<script>alert", page)

    def test_long_settlement_list_stays_short_in_report(self):
        result = {**FACTS, "cutoff": [{"name": f"Village {i}"} for i in range(20)]}
        self.assertIn("and 15 more", situation_report(result))
        self.assertNotIn("Village 19", situation_report(result))
        self.assertIn("Village 19", answer_question(result, "Which settlements are cut off?"))


if __name__ == "__main__":
    unittest.main()
