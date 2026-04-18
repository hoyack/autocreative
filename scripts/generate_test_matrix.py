"""Generate a matrix of flyers across events and style presets.

Standalone script — hits real APIs. Not part of the unit test suite.

Usage:
    python scripts/generate_test_matrix.py
    python scripts/generate_test_matrix.py --workflow standard_square
    python scripts/generate_test_matrix.py --presets photorealistic,anime
    python scripts/generate_test_matrix.py --events 0,2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Ensure project root is importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flyer_generator.config import Settings
from flyer_generator.logging_config import configure_logging
from flyer_generator.models import EventInput
from flyer_generator.pipeline import FlyerGenerator
from flyer_generator.presets import build_default_registry

SAMPLE_EVENTS = [
    {
        "title": "Neighborhood Clean-Up Day",
        "date": "Saturday, May 2, 2026",
        "time": "9:00 AM - 12:00 PM",
        "location_name": "Riverside Park Pavilion",
        "location_address": "123 Park Rd, San Antonio, TX 78205",
        "fees": "FREE",
        "org": "Friends of Riverside Park",
        "style_concept": "community outdoor event, park setting, sunny morning",
    },
    {
        "title": "Jazz Night at Blue Note",
        "date": "Friday, June 13, 2026",
        "time": "8:00 PM - 11:30 PM",
        "location_name": "Blue Note Jazz Club",
        "location_address": "131 W 3rd St, New York, NY 10012",
        "fees": "$25",
        "org": "NYC Jazz Society",
        "style_concept": "jazz club atmosphere, moody blue lighting, saxophone silhouette",
    },
    {
        "title": "Kids Coding Workshop",
        "date": "Sunday, July 20, 2026",
        "time": "10:00 AM - 2:00 PM",
        "location_name": "Downtown Library",
        "location_address": "500 Main St, Austin, TX 78701",
        "fees": "$10",
        "org": "Code for Kids Foundation",
        "style_concept": "colorful classroom with computers, children learning, bright cheerful",
    },
    {
        "title": "Summer Music Festival",
        "date": "August 8-10, 2026",
        "time": "12:00 PM - 10:00 PM",
        "location_name": "Zilker Park",
        "location_address": "2100 Barton Springs Rd, Austin, TX 78704",
        "fees": "$75",
        "org": "Austin Music Foundation",
        "style_concept": "outdoor music festival, stage lights, crowd, sunset sky",
        "color_accent": "#E11D48",
    },
    {
        "title": "Yoga in the Garden",
        "date": "Saturday, April 19, 2026",
        "time": "7:00 AM - 8:30 AM",
        "location_name": "Japanese Tea Garden",
        "location_address": "3853 N St Mary's St, San Antonio, TX 78212",
        "fees": "$15",
        "org": "Mindful Movement SA",
        "style_concept": "serene garden morning, yoga mats on grass, soft golden light, peaceful zen atmosphere",
        "color_accent": "#10B981",
    },
    {
        "title": "Taco Cook-Off",
        "date": "Sunday, September 7, 2026",
        "time": "11:00 AM - 4:00 PM",
        "location_name": "Market Square",
        "location_address": "514 W Commerce St, San Antonio, TX 78207",
        "fees": "$5",
        "org": "SA Foodies Association",
        "style_concept": "vibrant Mexican food market, colorful tacos, festive decorations, lively crowd",
        "color_accent": "#F97316",
    },
    {
        "title": "Stargazing Night",
        "date": "Friday, October 16, 2026",
        "time": "8:00 PM - 11:00 PM",
        "location_name": "Hill Country Observatory",
        "location_address": "9000 Ranch Rd, Fredericksburg, TX 78624",
        "fees": "FREE",
        "org": "Texas Astronomy Club",
        "style_concept": "dark night sky filled with stars, milky way, telescope silhouette, deep space nebula",
        "color_accent": "#6366F1",
    },
]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Generate test flyer matrix")
    parser.add_argument("--workflow", default=None, help="Workflow name or .json path")
    parser.add_argument("--presets", default=None, help="Comma-separated preset names (default: all)")
    parser.add_argument("--events", default=None, help="Comma-separated event indices (default: all)")
    parser.add_argument("--output-dir", default="output/test_matrix", help="Output directory")
    args = parser.parse_args()

    settings = Settings()
    if args.workflow:
        settings.workflow = args.workflow

    configure_logging(settings.log_format, settings.log_level)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Select presets
    all_presets = build_default_registry().list_names()
    if args.presets:
        presets = [p.strip() for p in args.presets.split(",")]
    else:
        presets = all_presets

    # Select events
    if args.events:
        event_indices = [int(i.strip()) for i in args.events.split(",")]
        events = [SAMPLE_EVENTS[i] for i in event_indices]
    else:
        events = SAMPLE_EVENTS

    results: dict[str, list] = {"success": [], "failed": []}
    total = len(events) * len(presets)
    current = 0

    for event_data in events:
        for preset_name in presets:
            current += 1
            event_copy = {**event_data, "style_preset": preset_name}
            event = EventInput(**event_copy)
            slug = f"{event.title[:25].replace(' ', '_').lower()}_{preset_name}"
            safe_slug = "".join(c if c.isalnum() or c == "_" else "_" for c in slug)

            print(f"[{current}/{total}] {safe_slug}...", end=" ", flush=True)

            generator = FlyerGenerator(settings)
            try:
                result = await generator.generate(event)
                out_path = output_dir / f"{safe_slug}.png"
                result.save(out_path)
                results["success"].append({
                    "slug": safe_slug,
                    "attempts": result.attempts_used,
                    "size_kb": result.file_size_kb,
                    "zones": {
                        "title": result.zones_used.title,
                        "details": result.zones_used.details,
                    },
                    "text_color": result.final_vision_verdict.text_color,
                })
                print(f"OK ({result.attempts_used} attempt(s), {result.file_size_kb}KB)")
            except Exception as exc:
                results["failed"].append({"slug": safe_slug, "error": str(exc)})
                print(f"FAIL: {exc}")

    # Summary
    print(f"\n{'=' * 60}")
    print(f"Results: {len(results['success'])} ok, {len(results['failed'])} failed out of {total}")
    print(f"{'=' * 60}")

    if results["failed"]:
        print("\nFailed:")
        for f in results["failed"]:
            print(f"  - {f['slug']}: {f['error'][:80]}")

    results_path = output_dir / "results.json"
    results_path.write_text(json.dumps(results, indent=2))
    print(f"\nResults saved to {results_path}")
    print(f"Flyers saved to {output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
