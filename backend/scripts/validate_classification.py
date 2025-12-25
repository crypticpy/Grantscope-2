#!/usr/bin/env python3
"""
Classification Accuracy Validation Script

This script helps validate AI classification accuracy by:
1. Selecting 100 random cards from the last 7 days
2. Facilitating ground truth label submission via API
3. Computing and reporting accuracy metrics
4. Generating a validation report

Usage:
    # Interactive validation (one card at a time)
    python -m scripts.validate_classification --mode interactive

    # Batch export for external review
    python -m scripts.validate_classification --mode export --output cards.json

    # Import reviewed labels
    python -m scripts.validate_classification --mode import --input reviewed_cards.json

    # Check accuracy
    python -m scripts.validate_classification --mode accuracy

    # Full report
    python -m scripts.validate_classification --mode report

Environment Variables:
    API_BASE_URL: Backend API URL (default: http://localhost:8000)
    API_TOKEN: Authentication token for API access
"""

import argparse
import asyncio
import json
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp


# Strategic pillar definitions for reference during validation
PILLAR_DEFINITIONS = {
    "CH": {
        "name": "Community Health & Sustainability",
        "description": "Public health, parks, climate, preparedness, and animal services",
    },
    "EW": {
        "name": "Economic & Workforce Development",
        "description": "Economic mobility, small business support, and creative economy",
    },
    "HG": {
        "name": "High-Performing Government",
        "description": "Fiscal integrity, technology, workforce, and community engagement",
    },
    "HH": {
        "name": "Homelessness & Housing",
        "description": "Complete communities, affordable housing, and homelessness reduction",
    },
    "MC": {
        "name": "Mobility & Critical Infrastructure",
        "description": "Transportation, transit, utilities, and facility management",
    },
    "PS": {
        "name": "Public Safety",
        "description": "Community relationships, fair delivery, and disaster preparedness",
    },
}


class ClassificationValidator:
    """Handles classification validation workflow."""

    def __init__(
        self,
        api_base_url: str = "http://localhost:8000",
        api_token: Optional[str] = None,
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.api_token = api_token
        self.reviewer_id = os.getenv("REVIEWER_ID", "validation-script")

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    async def fetch_pending_cards(
        self,
        limit: int = 100,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Fetch cards pending validation from the last N days.

        Args:
            limit: Maximum number of cards to fetch
            days: Number of days to look back

        Returns:
            List of card dictionaries
        """
        async with aiohttp.ClientSession() as session:
            # First try the pending endpoint
            url = f"{self.api_base_url}/api/v1/validation/pending"
            params = {"limit": limit}

            async with session.get(
                url,
                headers=self._get_headers(),
                params=params,
            ) as response:
                if response.status == 200:
                    cards = await response.json()
                    if cards:
                        return cards[:limit]

            # Fallback: fetch cards directly
            url = f"{self.api_base_url}/api/v1/cards"
            period_start = (datetime.now() - timedelta(days=days)).isoformat()

            params = {
                "limit": limit * 2,  # Fetch more to allow for random selection
                "status": "active",
            }

            async with session.get(
                url,
                headers=self._get_headers(),
                params=params,
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    cards = result.get("data", result) if isinstance(result, dict) else result

                    # Filter to cards with pillar_id and within date range
                    filtered_cards = [
                        c for c in cards
                        if c.get("pillar_id") and c.get("created_at", "") >= period_start
                    ]

                    # Random sample
                    if len(filtered_cards) > limit:
                        return random.sample(filtered_cards, limit)
                    return filtered_cards

                return []

    async def submit_validation(
        self,
        card_id: str,
        ground_truth_pillar: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Submit a ground truth label for a card.

        Args:
            card_id: UUID of the card
            ground_truth_pillar: Correct pillar code
            notes: Optional notes explaining the decision

        Returns:
            API response dictionary
        """
        url = f"{self.api_base_url}/api/v1/validation/submit"

        payload = {
            "card_id": card_id,
            "ground_truth_pillar": ground_truth_pillar,
            "reviewer_id": self.reviewer_id,
        }
        if notes:
            payload["notes"] = notes

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                headers=self._get_headers(),
                json=payload,
            ) as response:
                if response.status in (200, 201):
                    return await response.json()
                else:
                    text = await response.text()
                    return {"error": text, "status": response.status}

    async def get_accuracy_stats(self, days: Optional[int] = None) -> Dict[str, Any]:
        """
        Get classification accuracy statistics.

        Args:
            days: Optional number of days to filter

        Returns:
            Accuracy metrics dictionary
        """
        url = f"{self.api_base_url}/api/v1/validation/accuracy"
        params = {}
        if days:
            params["days"] = days

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=self._get_headers(),
                params=params,
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {"error": await response.text()}

    async def get_accuracy_by_pillar(self, days: Optional[int] = None) -> Dict[str, Any]:
        """
        Get classification accuracy broken down by pillar.

        Args:
            days: Optional number of days to filter

        Returns:
            Per-pillar accuracy metrics
        """
        url = f"{self.api_base_url}/api/v1/validation/accuracy/by-pillar"
        params = {}
        if days:
            params["days"] = days

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=self._get_headers(),
                params=params,
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {"error": await response.text()}


def display_card_for_validation(card: Dict[str, Any], index: int, total: int) -> None:
    """Display a card for interactive validation."""
    print("\n" + "=" * 80)
    print(f"Card {index + 1} of {total}")
    print("=" * 80)
    print(f"ID: {card.get('id', 'N/A')}")
    print(f"Name: {card.get('name', 'N/A')}")
    print(f"Created: {card.get('created_at', 'N/A')}")
    print(f"\nPredicted Pillar: {card.get('pillar_id', 'None')}")
    print("-" * 40)
    print("Summary:")
    print(card.get("summary", "No summary available"))
    print("-" * 40)
    print("\nAvailable Pillar Codes:")
    for code, info in PILLAR_DEFINITIONS.items():
        print(f"  {code}: {info['name']}")
        print(f"       {info['description']}")


def get_pillar_input() -> Optional[str]:
    """Get pillar code input from user."""
    while True:
        choice = input("\nEnter pillar code (or 's' to skip, 'q' to quit): ").strip().upper()

        if choice == "S":
            return None
        if choice == "Q":
            raise KeyboardInterrupt

        if choice in PILLAR_DEFINITIONS:
            return choice

        print(f"Invalid code. Must be one of: {', '.join(PILLAR_DEFINITIONS.keys())}")


async def interactive_mode(validator: ClassificationValidator, count: int = 100) -> None:
    """Run interactive validation mode."""
    print(f"\nFetching {count} cards for validation...")
    cards = await validator.fetch_pending_cards(limit=count)

    if not cards:
        print("No cards found for validation.")
        return

    print(f"Found {len(cards)} cards to validate.")

    validated = 0
    skipped = 0

    try:
        for i, card in enumerate(cards):
            display_card_for_validation(card, i, len(cards))

            pillar = get_pillar_input()

            if pillar:
                notes = input("Notes (optional, press Enter to skip): ").strip() or None

                result = await validator.submit_validation(
                    card_id=card["id"],
                    ground_truth_pillar=pillar,
                    notes=notes,
                )

                if "error" in result:
                    print(f"Error: {result['error']}")
                else:
                    is_correct = result.get("is_correct")
                    status = "Correct!" if is_correct else "Incorrect"
                    print(f"Validation submitted: {status}")
                    validated += 1
            else:
                print("Card skipped.")
                skipped += 1

    except KeyboardInterrupt:
        print("\n\nValidation session ended.")

    print(f"\nSession Summary:")
    print(f"  Validated: {validated}")
    print(f"  Skipped: {skipped}")
    print(f"  Remaining: {len(cards) - validated - skipped}")


async def export_mode(
    validator: ClassificationValidator,
    output_path: str,
    count: int = 100,
) -> None:
    """Export cards for external review."""
    print(f"\nFetching {count} cards for export...")
    cards = await validator.fetch_pending_cards(limit=count)

    if not cards:
        print("No cards found for export.")
        return

    # Prepare export format
    export_data = {
        "export_date": datetime.now().isoformat(),
        "total_cards": len(cards),
        "pillar_definitions": PILLAR_DEFINITIONS,
        "cards": [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "summary": c.get("summary"),
                "predicted_pillar": c.get("pillar_id"),
                "created_at": c.get("created_at"),
                "ground_truth_pillar": None,  # To be filled by reviewer
                "notes": None,  # To be filled by reviewer
            }
            for c in cards
        ],
    }

    with open(output_path, "w") as f:
        json.dump(export_data, f, indent=2)

    print(f"Exported {len(cards)} cards to {output_path}")
    print("\nInstructions:")
    print("1. Open the JSON file")
    print("2. For each card, fill in 'ground_truth_pillar' with the correct pillar code")
    print("3. Optionally add 'notes' explaining your decision")
    print("4. Run import mode to submit the validations")


async def import_mode(validator: ClassificationValidator, input_path: str) -> None:
    """Import reviewed labels from JSON file."""
    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return

    with open(input_path, "r") as f:
        data = json.load(f)

    cards = data.get("cards", [])
    if not cards:
        print("No cards found in import file.")
        return

    submitted = 0
    errors = 0
    skipped = 0

    for card in cards:
        ground_truth = card.get("ground_truth_pillar")
        if not ground_truth:
            skipped += 1
            continue

        result = await validator.submit_validation(
            card_id=card["id"],
            ground_truth_pillar=ground_truth,
            notes=card.get("notes"),
        )

        if "error" in result:
            errors += 1
            print(f"Error for card {card['id']}: {result['error']}")
        else:
            submitted += 1

    print(f"\nImport Summary:")
    print(f"  Submitted: {submitted}")
    print(f"  Errors: {errors}")
    print(f"  Skipped (no label): {skipped}")


async def accuracy_mode(validator: ClassificationValidator, days: Optional[int] = None) -> None:
    """Display accuracy statistics."""
    print("\n" + "=" * 60)
    print("Classification Accuracy Report")
    print("=" * 60)

    # Overall accuracy
    stats = await validator.get_accuracy_stats(days=days)

    if "error" in stats:
        print(f"Error fetching stats: {stats['error']}")
        return

    print(f"\nOverall Accuracy:")
    print(f"  Total Validations: {stats.get('total_validations', 0)}")
    print(f"  Correct: {stats.get('correct_count', 0)}")

    accuracy = stats.get("accuracy_percentage")
    if accuracy is not None:
        print(f"  Accuracy: {accuracy:.2f}%")
        print(f"  Target: {stats.get('target_accuracy', 85.0)}%")
        print(f"  Meets Target: {'Yes' if stats.get('meets_target') else 'No'}")
    else:
        print("  Accuracy: N/A (no validations)")

    # Per-pillar breakdown
    pillar_stats = await validator.get_accuracy_by_pillar(days=days)

    if "error" not in pillar_stats:
        by_pillar = pillar_stats.get("by_pillar", {})
        if by_pillar:
            print(f"\nAccuracy by Pillar:")
            print("-" * 50)
            for pillar, pstats in sorted(by_pillar.items()):
                name = PILLAR_DEFINITIONS.get(pillar, {}).get("name", pillar)
                total = pstats.get("total_validations", 0)
                acc = pstats.get("accuracy_percentage")
                acc_str = f"{acc:.1f}%" if acc is not None else "N/A"
                print(f"  {pillar} ({name}): {acc_str} ({total} validations)")

        # Confusion summary
        confusion = pillar_stats.get("confusion_summary", [])
        if confusion:
            print(f"\nTop Misclassifications:")
            print("-" * 50)
            for entry in confusion[:5]:
                pred = entry.get("predicted", "?")
                actual = entry.get("actual", "?")
                count = entry.get("count", 0)
                print(f"  {pred} predicted as {actual}: {count} times")


async def report_mode(
    validator: ClassificationValidator,
    output_path: Optional[str] = None,
    days: int = 7,
) -> None:
    """Generate a comprehensive validation report."""
    report_lines = []
    timestamp = datetime.now().isoformat()

    report_lines.append("# Classification Accuracy Validation Report")
    report_lines.append(f"\n**Generated:** {timestamp}")
    report_lines.append(f"**Period:** Last {days} days")

    # Fetch statistics
    stats = await validator.get_accuracy_stats(days=days)
    pillar_stats = await validator.get_accuracy_by_pillar(days=days)

    if "error" in stats:
        report_lines.append(f"\n**Error:** {stats['error']}")
    else:
        report_lines.append("\n## Overall Accuracy")
        report_lines.append("")
        report_lines.append(f"| Metric | Value |")
        report_lines.append("|--------|-------|")
        report_lines.append(f"| Total Validations | {stats.get('total_validations', 0)} |")
        report_lines.append(f"| Correct Classifications | {stats.get('correct_count', 0)} |")

        accuracy = stats.get("accuracy_percentage")
        if accuracy is not None:
            report_lines.append(f"| Accuracy | {accuracy:.2f}% |")
            report_lines.append(f"| Target | {stats.get('target_accuracy', 85.0)}% |")
            report_lines.append(f"| Meets Target | {'Yes' if stats.get('meets_target') else 'No'} |")
        else:
            report_lines.append("| Accuracy | N/A (no validations) |")

    if "error" not in pillar_stats:
        by_pillar = pillar_stats.get("by_pillar", {})
        if by_pillar:
            report_lines.append("\n## Accuracy by Pillar")
            report_lines.append("")
            report_lines.append("| Pillar | Name | Validations | Accuracy | Meets Target |")
            report_lines.append("|--------|------|-------------|----------|--------------|")

            for pillar, pstats in sorted(by_pillar.items()):
                name = PILLAR_DEFINITIONS.get(pillar, {}).get("name", pillar)
                total = pstats.get("total_validations", 0)
                acc = pstats.get("accuracy_percentage")
                acc_str = f"{acc:.1f}%" if acc is not None else "N/A"
                meets = "Yes" if pstats.get("meets_target") else "No"
                report_lines.append(f"| {pillar} | {name} | {total} | {acc_str} | {meets} |")

        confusion = pillar_stats.get("confusion_summary", [])
        if confusion:
            report_lines.append("\n## Common Misclassifications")
            report_lines.append("")
            report_lines.append("| Predicted | Actual | Count |")
            report_lines.append("|-----------|--------|-------|")

            for entry in confusion[:10]:
                pred = entry.get("predicted", "?")
                actual = entry.get("actual", "?")
                count = entry.get("count", 0)
                report_lines.append(f"| {pred} | {actual} | {count} |")

    # Recommendations
    report_lines.append("\n## Recommendations")
    if "error" not in stats:
        accuracy = stats.get("accuracy_percentage")
        if accuracy is not None:
            if accuracy >= 85:
                report_lines.append("\n- Classification accuracy meets the >85% target.")
                report_lines.append("- Continue monitoring for consistency.")
            else:
                report_lines.append(f"\n- **Action Required:** Accuracy ({accuracy:.1f}%) is below target (85%).")
                report_lines.append("- Review AI prompts and classification logic.")
                report_lines.append("- Analyze confusion patterns to identify problematic pillars.")

        total = stats.get("total_validations", 0)
        if total < 100:
            report_lines.append(f"\n- **Note:** Only {total} validations submitted. Target is 100.")

    report_lines.append("\n---")
    report_lines.append(f"*Report generated by validate_classification.py*")

    report_text = "\n".join(report_lines)

    if output_path:
        with open(output_path, "w") as f:
            f.write(report_text)
        print(f"Report saved to {output_path}")
    else:
        print(report_text)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Classification Accuracy Validation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--mode",
        choices=["interactive", "export", "import", "accuracy", "report"],
        default="accuracy",
        help="Operation mode",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of cards to process (default: 100)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to look back (default: 7)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (for export/report modes)",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Input file path (for import mode)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=os.getenv("API_BASE_URL", "http://localhost:8000"),
        help="Backend API URL",
    )
    parser.add_argument(
        "--api-token",
        type=str,
        default=os.getenv("API_TOKEN"),
        help="API authentication token",
    )

    args = parser.parse_args()

    validator = ClassificationValidator(
        api_base_url=args.api_url,
        api_token=args.api_token,
    )

    if args.mode == "interactive":
        asyncio.run(interactive_mode(validator, count=args.count))
    elif args.mode == "export":
        output = args.output or "cards_for_validation.json"
        asyncio.run(export_mode(validator, output_path=output, count=args.count))
    elif args.mode == "import":
        if not args.input:
            print("Error: --input is required for import mode")
            sys.exit(1)
        asyncio.run(import_mode(validator, input_path=args.input))
    elif args.mode == "accuracy":
        asyncio.run(accuracy_mode(validator, days=args.days))
    elif args.mode == "report":
        asyncio.run(report_mode(validator, output_path=args.output, days=args.days))


if __name__ == "__main__":
    main()
