import unittest
from datetime import UTC, datetime, timedelta

from app.domain.matching import assign, challenge_result


def evidence(
    identifier, *, species=None, category=None, categories=None, traits=None, status="verified"
):
    return {
        "id": identifier,
        "status": status,
        "species_id": species,
        "category": category,
        "categories": categories or ([category] if category else []),
        "traits": traits or [],
    }


class MatchingTests(unittest.TestCase):
    def test_exact_species_rejects_category_only(self):
        requirements = [{"id": "neem", "kind": "species", "species_id": "neem", "count": 1}]
        self.assertEqual(assign(requirements, [evidence("one", category="tree")]), {})

    def test_one_photo_fills_one_target_even_if_it_matches_both(self):
        requirements = [
            {"id": "tree", "kind": "taxon_category", "category": "tree", "count": 1},
            {"id": "plant", "kind": "taxon_category", "category": "plant", "count": 1},
        ]
        result = assign(
            requirements,
            [evidence("one", species="neem", category="tree", categories=["tree", "plant"])],
        )
        self.assertEqual(len(result), 1)

    def test_distinct_species_rejects_two_photos_of_same_species(self):
        requirements = [
            {
                "id": "flowers",
                "kind": "taxon_category",
                "category": "flowering_plant",
                "count": 2,
                "distinct_species": 2,
            }
        ]
        result = assign(
            requirements,
            [
                evidence("one", species="hibiscus", category="flowering_plant"),
                evidence("two", species="hibiscus", category="flowering_plant"),
            ],
        )
        self.assertEqual(len(result), 1)

    def test_weight_and_unit_tiebreaks(self):
        requirements = [
            {"id": "neem", "kind": "species", "species_id": "neem", "count": 1},
            {"id": "serrated", "kind": "visual_trait", "trait_code": "serrated_leaf", "count": 1},
            {"id": "yellow", "kind": "visual_trait", "trait_code": "yellow_flower", "count": 1},
            {"id": "striped", "kind": "visual_trait", "trait_code": "striped_wing", "count": 1},
        ]
        result = challenge_result(
            requirements,
            [evidence("a", species="neem", category="tree")],
            [
                evidence("b", traits=["serrated_leaf"]),
                evidence("c", traits=["yellow_flower"]),
                evidence("d", traits=["striped_wing"]),
            ],
        )
        self.assertEqual(result["scores"], [3, 3])
        self.assertEqual(result["winner_index"], 1)

    def test_unverified_does_not_score(self):
        requirements = [{"id": "bird", "kind": "taxon_category", "category": "bird", "count": 1}]
        result = challenge_result(
            requirements, [evidence("a", category="bird", status="needs_review")], []
        )
        self.assertEqual(result["scores"], [0, 0])
        self.assertIsNone(result["winner_index"])

    def test_done_time_breaks_only_a_nonzero_tie(self):
        requirements = [{"id": "bird", "kind": "taxon_category", "category": "bird", "count": 1}]
        early = datetime.now(UTC)
        late = early + timedelta(seconds=30)
        result = challenge_result(
            requirements,
            [evidence("a", category="bird")],
            [evidence("b", category="bird")],
            late,
            early,
        )
        self.assertEqual(result["winner_index"], 1)
        zero = challenge_result(requirements, [], [], late, early)
        self.assertIsNone(zero["winner_index"])

    def test_duplicate_evidence_id_cannot_fill_multiple_units(self):
        requirements = [{"id": "birds", "kind": "taxon_category", "category": "bird", "count": 2}]
        photo = evidence("one", category="bird")
        self.assertEqual(len(assign(requirements, [photo, photo])), 1)


if __name__ == "__main__":
    unittest.main()
