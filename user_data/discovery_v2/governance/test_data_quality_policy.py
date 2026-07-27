import copy
import json
import unittest
from pathlib import Path

from data_quality_policy import CONDITIONAL, FAIL, PASS, classify, load_policy


def eligible_evidence():
    return {
        "mechanical_coverage_gate": 0.999,
        "mechanical_coverage_pass": False,
        "hard_integrity_gates_pass": True,
        "official_source_gap_confirmed": True,
        "reproducible_provenance": True,
        "pipeline_integrity_pass": True,
        "missing_timestamps_enumerated_immutable": True,
        "classification_pre_outcome": True,
        "same_source_recovery_unavailable": True,
        "no_imputation_or_synthetic_reconstruction": True,
        "coverage_proportion": 0.9986301369863013,
        "max_contiguous_gap_hours": 24,
        "max_affected_sessions_per_rolling_12m": 1,
        "symmetric_common_intersection_policy_frozen": True,
        "gap_not_hypothesis_defining_event": True,
        "sample_and_replication_minima_preserved": True,
        "holdout_sealed": True,
        "sensitivity_preregistered": True,
    }


class PolicyTests(unittest.TestCase):
    def test_policy_is_exact(self):
        policy = load_policy()
        self.assertEqual(policy["unconditional_coverage_gate"], 0.999)
        self.assertEqual(len(policy["conditional_criteria"]), 15)

    def test_all_criteria_yield_conditional(self):
        result = classify(eligible_evidence())
        self.assertEqual(result["mechanical_subgate"]["result"], FAIL)
        self.assertEqual(result["global_data_admissibility"], CONDITIONAL)
        self.assertEqual(result["hypothesis_status"], "UNTESTED")

    def test_each_boolean_criterion_is_mandatory(self):
        base = eligible_evidence()
        excluded = {"mechanical_coverage_pass", "hard_integrity_gates_pass"}
        for key, value in base.items():
            if isinstance(value, bool) and value and key not in excluded:
                trial = copy.deepcopy(base)
                trial[key] = False
                self.assertEqual(classify(trial)["global_data_admissibility"], FAIL, key)

    def test_numeric_limits_are_mandatory(self):
        for field, value in (("coverage_proportion", 0.9949), ("max_contiguous_gap_hours", 24.01), ("max_affected_sessions_per_rolling_12m", 2)):
            trial = eligible_evidence()
            trial[field] = value
            self.assertEqual(classify(trial)["global_data_admissibility"], FAIL, field)

    def test_clean_dataset_passes_unconditionally(self):
        trial = eligible_evidence()
        trial["coverage_proportion"] = 0.999
        trial["mechanical_coverage_pass"] = True
        self.assertEqual(classify(trial)["global_data_admissibility"], PASS)

    def test_gate_cannot_be_changed(self):
        trial = eligible_evidence()
        trial["mechanical_coverage_gate"] = 0.998
        with self.assertRaises(ValueError):
            classify(trial)


if __name__ == "__main__":
    unittest.main()
