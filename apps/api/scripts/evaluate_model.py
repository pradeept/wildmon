"""Evaluate a Gemma vision endpoint on a labeled JSONL image manifest."""

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

from app.ai.vision import GemmaVisionIdentifier
from app.core.config import get_settings
from scripts.seed import SPECIES


def percentile(values: list[float], fraction: float) -> float:
    """Return nearest-rank percentile for a small benchmark set."""
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, int((len(ordered) - 1) * fraction)))]


async def evaluate(manifest: Path, output: Path) -> None:
    samples = [json.loads(line) for line in manifest.read_text().splitlines() if line.strip()]
    if len(samples) < 30:
        raise ValueError("Provide at least 30 labeled nature and negative images")
    catalog = [
        {
            "_id": identifier,
            "scientific_name": scientific,
            "common_name": common,
            "category": category,
            "supported": False,
        }
        for identifier, scientific, common, category in SPECIES
    ]
    identifier = GemmaVisionIdentifier(get_settings())
    results = []
    for sample in samples:
        image_path = (manifest.parent / sample["image_path"]).resolve()
        mime = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "webp": "image/webp",
        }[image_path.suffix[1:].lower()]
        started = time.perf_counter()
        try:
            finding = await identifier.identify(image_path.read_bytes(), mime, catalog)
            result = finding.model_dump()
            error = None
        except Exception as exc:
            result = None
            error = str(exc)
        results.append(
            {
                "image_path": sample["image_path"],
                "expected_category": sample.get("category"),
                "expected_scientific_name": sample.get("scientific_name"),
                "should_abstain": bool(sample.get("should_abstain", False)),
                "result": result,
                "error": error,
                "latency_seconds": round(time.perf_counter() - started, 3),
            }
        )
    valid = [row for row in results if row["result"]]
    exact = [row for row in valid if row["expected_scientific_name"]]
    category_preds = [row for row in valid if row["result"]["category"]]
    negative = [row for row in valid if row["should_abstain"]]
    latencies = [row["latency_seconds"] for row in results]
    summary = {
        "model": get_settings().gemma_model,
        "samples": len(results),
        "errors": sum(row["error"] is not None for row in results),
        "exact_species_accuracy": (
            sum(
                row["result"]["scientific_name"] == row["expected_scientific_name"] for row in exact
            )
            / len(exact)
            if exact
            else None
        ),
        "category_precision": (
            sum(row["result"]["category"] == row["expected_category"] for row in category_preds)
            / len(category_preds)
            if category_preds
            else None
        ),
        "false_positive_rate_on_negative": (
            sum(
                not row["result"]["insufficient_image"]
                and not row["result"]["unrelated_image"]
                and row["result"]["candidate_rank"] != "unknown"
                for row in negative
            )
            / len(negative)
            if negative
            else None
        ),
        "correct_abstention_rate": (
            sum(
                row["result"]["insufficient_image"]
                or row["result"]["unrelated_image"]
                or row["result"]["candidate_rank"] == "unknown"
                for row in negative
            )
            / len(negative)
            if negative
            else None
        ),
        "median_latency_seconds": statistics.median(latencies),
        "p95_latency_seconds": percentile(latencies, 0.95),
    }
    output.write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, default=Path("model-evaluation.json"))
    args = parser.parse_args()
    asyncio.run(evaluate(args.manifest, args.output))
