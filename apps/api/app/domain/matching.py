from functools import lru_cache
from typing import Any

WEIGHTS = {"species": 3, "taxon_category": 2, "visual_trait": 1}


def matches(requirement: dict[str, Any], discovery: dict[str, Any]) -> bool:
    """Check evidence at the required specificity; broad guesses never satisfy exact targets."""
    if discovery.get("status") != "verified":
        return False
    kind = requirement["kind"]
    if kind == "species":
        return discovery.get("species_id") == requirement["species_id"]
    if kind == "taxon_category":
        category = requirement["category"]
        available = set(discovery.get("categories", []))
        if category not in available and discovery.get("category") != category:
            return False
        return not requirement.get("distinct_species") or bool(discovery.get("species_id"))
    return requirement["trait_code"] in discovery.get("traits", [])


def assign(requirements: list[dict[str, Any]], discoveries: list[dict[str, Any]]) -> dict[str, str]:
    """Maximize weighted fulfilled units with deterministic, one-to-one evidence allocation.

    Each count becomes a separate slot. The memoized search considers skipping an
    observation, so evidence order cannot force a weaker assignment.
    """
    slots = [
        (f"{requirement['id']}:{index}", requirement)
        for requirement in requirements
        for index in range(requirement.get("count", 1))
    ]
    if len(slots) > 12:
        raise ValueError("Too many target units")
    evidence = sorted(
        {item["id"]: item for item in discoveries}.values(), key=lambda item: item["id"]
    )

    @lru_cache
    def solve(
        index: int, used: int, distinct: tuple[tuple[str, str], ...]
    ) -> tuple[int, int, tuple[tuple[str, str], ...]]:
        if index == len(evidence):
            return (0, 0, ())
        best = solve(index + 1, used, distinct)
        for slot_index, (slot_id, requirement) in enumerate(slots):
            if used & (1 << slot_index) or not matches(requirement, evidence[index]):
                continue
            next_distinct = distinct
            if requirement.get("distinct_species"):
                identity = (requirement["id"], evidence[index]["species_id"])
                if identity in distinct:
                    continue
                next_distinct = tuple(sorted((*distinct, identity)))
            score, units, pairs = solve(index + 1, used | (1 << slot_index), next_distinct)
            candidate = (
                score + WEIGHTS[requirement["kind"]],
                units + 1,
                ((slot_id, evidence[index]["id"]),) + pairs,
            )
            if candidate[:2] > best[:2] or (candidate[:2] == best[:2] and candidate[2] < best[2]):
                best = candidate
        return best

    return dict(solve(0, 0, ())[2])


def challenge_result(
    requirements: list[dict[str, Any]],
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
    first_done: Any = None,
    second_done: Any = None,
) -> dict[str, Any]:
    """Apply locked tie-breaks after deterministic target assignment."""
    left, right = assign(requirements, first), assign(requirements, second)

    def score(assignment: dict[str, str]) -> int:
        by_id = {requirement["id"]: requirement for requirement in requirements}
        return sum(WEIGHTS[by_id[slot.split(":")[0]]["kind"]] for slot in assignment)

    left_score, right_score = score(left), score(right)
    winner = None
    if left_score != right_score:
        winner = 0 if left_score > right_score else 1
    elif len(left) != len(right):
        winner = 0 if len(left) > len(right) else 1
    elif left and first_done and second_done and first_done != second_done:
        winner = 0 if first_done < second_done else 1
    return {"winner_index": winner, "scores": [left_score, right_score], "matches": [left, right]}
