import unittest
from unittest.mock import patch

from copilot import answer_question, situation_report


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


if __name__ == "__main__":
    unittest.main()
