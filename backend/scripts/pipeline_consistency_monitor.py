#!/usr/bin/env python3
"""
Pipeline Consistency Monitor

This script monitors nightly pipeline executions for 7-day consistency validation.
It checks:
1. Daily runs complete successfully (no crashes)
2. Card count variance <20% across runs
3. All 5 source categories contribute daily
4. Errors are properly logged and recovered

Usage:
    python pipeline_consistency_monitor.py --days 7
    python pipeline_consistency_monitor.py --report
    python pipeline_consistency_monitor.py --check-today
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase package not installed. Run: pip install supabase")
    sys.exit(1)


# Required source categories for validation
REQUIRED_SOURCE_CATEGORIES = [
    "rss",
    "news",
    "academic",
    "government",
    "tech_blog"
]

# Thresholds for consistency validation
CARD_COUNT_VARIANCE_THRESHOLD = 0.20  # 20%
MIN_SOURCE_CATEGORIES_REQUIRED = 5


@dataclass
class DailyRunMetrics:
    """Metrics for a single day's pipeline run."""
    date: str
    run_id: Optional[str] = None
    status: str = "not_run"
    cards_created: int = 0
    sources_found: int = 0
    sources_by_category: Dict[str, int] = field(default_factory=dict)
    categories_present: int = 0
    errors: List[str] = field(default_factory=list)
    error_count: int = 0
    completed_at: Optional[str] = None
    duration_minutes: Optional[float] = None


@dataclass
class ConsistencyReport:
    """7-day consistency validation report."""
    report_date: str
    days_monitored: int = 0
    days_with_runs: int = 0
    days_successful: int = 0

    # Consistency metrics
    all_runs_successful: bool = False
    card_count_variance: float = 0.0
    meets_variance_threshold: bool = False

    # Source diversity metrics
    all_categories_present_daily: bool = False
    missing_category_days: Dict[str, List[str]] = field(default_factory=dict)

    # Error tracking
    total_errors: int = 0
    errors_by_day: Dict[str, List[str]] = field(default_factory=dict)

    # Daily breakdown
    daily_metrics: List[DailyRunMetrics] = field(default_factory=list)

    # Overall assessment
    passes_validation: bool = False
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class PipelineConsistencyMonitor:
    """Monitor for pipeline consistency validation."""

    def __init__(self):
        """Initialize the monitor with Supabase connection."""
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")

        if not supabase_url or not supabase_key:
            raise ValueError("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY environment variables")

        self.supabase: Client = create_client(supabase_url, supabase_key)

    def get_discovery_runs(self, days: int = 7) -> List[Dict[str, Any]]:
        """Fetch discovery runs from the last N days."""
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        response = self.supabase.table("discovery_runs").select(
            "*"
        ).gte(
            "started_at", start_date
        ).order(
            "started_at", desc=False
        ).execute()

        return response.data or []

    def get_cards_count_by_date(self, days: int = 7) -> Dict[str, int]:
        """Get card counts grouped by date for variance calculation."""
        start_date = (datetime.utcnow() - timedelta(days=days)).isoformat()

        response = self.supabase.table("cards").select(
            "id, created_at"
        ).gte(
            "created_at", start_date
        ).execute()

        cards_data = response.data or []

        # Group by date
        counts_by_date: Dict[str, int] = {}
        for card in cards_data:
            created_at = card.get("created_at", "")
            if created_at:
                date_str = created_at[:10]  # Extract YYYY-MM-DD
                counts_by_date[date_str] = counts_by_date.get(date_str, 0) + 1

        return counts_by_date

    def calculate_variance(self, values: List[int]) -> float:
        """Calculate coefficient of variation (CV) for card counts."""
        if not values or len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        if mean == 0:
            return 0.0

        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5

        # Coefficient of variation (CV) = std_dev / mean
        return std_dev / mean

    def analyze_daily_run(self, run: Dict[str, Any]) -> DailyRunMetrics:
        """Analyze a single discovery run and extract metrics."""
        started_at = run.get("started_at", "")
        completed_at = run.get("completed_at")

        # Extract date
        date_str = started_at[:10] if started_at else "unknown"

        # Calculate duration
        duration = None
        if started_at and completed_at:
            try:
                start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                end = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                duration = (end - start).total_seconds() / 60.0
            except ValueError:
                pass

        # Extract source categories from summary report
        summary_report = run.get("summary_report") or {}
        sources_by_category = summary_report.get("sources_by_category", {})

        # Count errors
        errors = []
        error_message = run.get("error_message")
        if error_message:
            errors.append(error_message)

        error_details = run.get("error_details") or {}
        if error_details:
            errors.extend([str(e) for e in error_details.get("errors", [])])

        return DailyRunMetrics(
            date=date_str,
            run_id=run.get("id"),
            status=run.get("status", "unknown"),
            cards_created=run.get("cards_created", 0),
            sources_found=run.get("sources_found", 0),
            sources_by_category=sources_by_category,
            categories_present=len(sources_by_category),
            errors=errors,
            error_count=len(errors),
            completed_at=completed_at,
            duration_minutes=round(duration, 2) if duration else None
        )

    def check_source_categories(
        self,
        daily_metrics: List[DailyRunMetrics]
    ) -> Dict[str, List[str]]:
        """Check which categories are missing on which days."""
        missing_by_category: Dict[str, List[str]] = {}

        for metrics in daily_metrics:
            if metrics.status not in ("completed", "completed_with_errors"):
                continue

            present_categories = set(metrics.sources_by_category.keys())
            required = set(REQUIRED_SOURCE_CATEGORIES)

            missing = required - present_categories
            for category in missing:
                if category not in missing_by_category:
                    missing_by_category[category] = []
                missing_by_category[category].append(metrics.date)

        return missing_by_category

    def generate_report(self, days: int = 7) -> ConsistencyReport:
        """Generate a comprehensive 7-day consistency report."""
        report = ConsistencyReport(
            report_date=datetime.utcnow().isoformat()[:19] + "Z",
            days_monitored=days
        )

        # Fetch data
        runs = self.get_discovery_runs(days)
        cards_by_date = self.get_cards_count_by_date(days)

        # Group runs by date (take the latest run per day)
        runs_by_date: Dict[str, Dict[str, Any]] = {}
        for run in runs:
            started_at = run.get("started_at", "")
            date_str = started_at[:10] if started_at else "unknown"
            # Keep the latest run for each date
            runs_by_date[date_str] = run

        # Analyze each day
        daily_metrics: List[DailyRunMetrics] = []
        for date_str, run in sorted(runs_by_date.items()):
            metrics = self.analyze_daily_run(run)

            # Override cards_created with actual card count if available
            if date_str in cards_by_date:
                metrics.cards_created = cards_by_date[date_str]

            daily_metrics.append(metrics)

        report.daily_metrics = daily_metrics
        report.days_with_runs = len(daily_metrics)

        # Count successful days
        report.days_successful = sum(
            1 for m in daily_metrics
            if m.status in ("completed", "completed_with_errors")
        )

        # Check if all runs were successful
        report.all_runs_successful = (
            report.days_with_runs >= days and
            report.days_successful == report.days_with_runs
        )

        # Calculate card count variance
        card_counts = [m.cards_created for m in daily_metrics if m.cards_created > 0]
        if card_counts:
            report.card_count_variance = round(self.calculate_variance(card_counts), 4)
            report.meets_variance_threshold = (
                report.card_count_variance <= CARD_COUNT_VARIANCE_THRESHOLD
            )

        # Check source categories
        report.missing_category_days = self.check_source_categories(daily_metrics)
        report.all_categories_present_daily = len(report.missing_category_days) == 0

        # Aggregate errors
        for metrics in daily_metrics:
            if metrics.errors:
                report.errors_by_day[metrics.date] = metrics.errors
                report.total_errors += metrics.error_count

        # Determine overall validation status
        issues = []
        recommendations = []

        if report.days_with_runs < days:
            issues.append(
                f"Only {report.days_with_runs}/{days} days have pipeline runs"
            )
            recommendations.append(
                "Ensure nightly scheduler is running and triggering daily"
            )

        if not report.all_runs_successful:
            failed_days = [
                m.date for m in daily_metrics
                if m.status not in ("completed", "completed_with_errors")
            ]
            issues.append(
                f"Pipeline failed on: {', '.join(failed_days)}"
            )
            recommendations.append(
                "Review error logs for failed runs and fix underlying issues"
            )

        if not report.meets_variance_threshold:
            issues.append(
                f"Card count variance ({report.card_count_variance:.2%}) exceeds "
                f"threshold ({CARD_COUNT_VARIANCE_THRESHOLD:.0%})"
            )
            recommendations.append(
                "Investigate source stability and ensure consistent content availability"
            )

        if not report.all_categories_present_daily:
            for category, dates in report.missing_category_days.items():
                issues.append(
                    f"Category '{category}' missing on: {', '.join(dates)}"
                )
            recommendations.append(
                "Check source fetchers for categories with missing days"
            )

        if report.total_errors > 0:
            issues.append(f"Total errors across period: {report.total_errors}")
            recommendations.append(
                "Review error details and implement additional error handling"
            )

        report.issues = issues
        report.recommendations = recommendations

        # Overall validation passes if:
        # 1. All days have successful runs
        # 2. Card variance is within threshold
        # 3. All 5 source categories present daily
        report.passes_validation = (
            report.all_runs_successful and
            report.meets_variance_threshold and
            report.all_categories_present_daily and
            report.days_with_runs >= days
        )

        return report

    def check_today(self) -> DailyRunMetrics:
        """Check today's pipeline run status."""
        today = datetime.utcnow().date().isoformat()

        response = self.supabase.table("discovery_runs").select(
            "*"
        ).gte(
            "started_at", today
        ).order(
            "started_at", desc=True
        ).limit(1).execute()

        runs = response.data or []

        if not runs:
            return DailyRunMetrics(
                date=today,
                status="not_run"
            )

        return self.analyze_daily_run(runs[0])

    def print_report(self, report: ConsistencyReport):
        """Print a formatted report to console."""
        print("\n" + "=" * 70)
        print("PIPELINE CONSISTENCY VALIDATION REPORT")
        print("=" * 70)
        print(f"Report Date: {report.report_date}")
        print(f"Monitoring Period: {report.days_monitored} days")
        print()

        # Overall Status
        status_icon = "PASS" if report.passes_validation else "FAIL"
        print(f"Overall Status: [{status_icon}]")
        print("-" * 70)

        # Summary Metrics
        print("\nSUMMARY METRICS:")
        print(f"  Days with runs: {report.days_with_runs}/{report.days_monitored}")
        print(f"  Successful runs: {report.days_successful}/{report.days_with_runs}")
        print(f"  Card count variance: {report.card_count_variance:.2%} "
              f"(threshold: {CARD_COUNT_VARIANCE_THRESHOLD:.0%})")
        print(f"  All 5 categories daily: {'Yes' if report.all_categories_present_daily else 'No'}")
        print(f"  Total errors: {report.total_errors}")
        print()

        # Daily Breakdown
        print("DAILY BREAKDOWN:")
        print("-" * 70)
        print(f"{'Date':<12} {'Status':<12} {'Cards':<8} {'Sources':<10} {'Categories':<12} {'Errors':<8}")
        print("-" * 70)

        for metrics in report.daily_metrics:
            categories = f"{metrics.categories_present}/5"
            print(f"{metrics.date:<12} {metrics.status:<12} {metrics.cards_created:<8} "
                  f"{metrics.sources_found:<10} {categories:<12} {metrics.error_count:<8}")

        print()

        # Issues
        if report.issues:
            print("ISSUES FOUND:")
            for i, issue in enumerate(report.issues, 1):
                print(f"  {i}. {issue}")
            print()

        # Recommendations
        if report.recommendations:
            print("RECOMMENDATIONS:")
            for i, rec in enumerate(report.recommendations, 1):
                print(f"  {i}. {rec}")
            print()

        # Missing categories detail
        if report.missing_category_days:
            print("MISSING SOURCE CATEGORIES:")
            for category, dates in report.missing_category_days.items():
                print(f"  - {category}: missing on {', '.join(dates)}")
            print()

        print("=" * 70)

        return report.passes_validation


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Pipeline Consistency Monitor for 7-day validation"
    )
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=7,
        help="Number of days to analyze (default: 7)"
    )
    parser.add_argument(
        "--report", "-r",
        action="store_true",
        help="Generate full consistency report"
    )
    parser.add_argument(
        "--check-today", "-t",
        action="store_true",
        help="Check only today's pipeline run"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output in JSON format"
    )

    args = parser.parse_args()

    try:
        monitor = PipelineConsistencyMonitor()

        if args.check_today:
            metrics = monitor.check_today()
            if args.json:
                print(json.dumps(metrics.__dict__, indent=2, default=str))
            else:
                print(f"\nToday's Pipeline Status ({metrics.date}):")
                print(f"  Status: {metrics.status}")
                print(f"  Cards created: {metrics.cards_created}")
                print(f"  Sources found: {metrics.sources_found}")
                print(f"  Categories: {metrics.categories_present}/5")
                if metrics.errors:
                    print(f"  Errors: {', '.join(metrics.errors[:3])}")

            sys.exit(0 if metrics.status in ("completed", "completed_with_errors") else 1)

        # Generate full report
        report = monitor.generate_report(args.days)

        if args.json:
            # Convert dataclasses to dict for JSON output
            report_dict = {
                "report_date": report.report_date,
                "days_monitored": report.days_monitored,
                "days_with_runs": report.days_with_runs,
                "days_successful": report.days_successful,
                "all_runs_successful": report.all_runs_successful,
                "card_count_variance": report.card_count_variance,
                "meets_variance_threshold": report.meets_variance_threshold,
                "all_categories_present_daily": report.all_categories_present_daily,
                "missing_category_days": report.missing_category_days,
                "total_errors": report.total_errors,
                "errors_by_day": report.errors_by_day,
                "passes_validation": report.passes_validation,
                "issues": report.issues,
                "recommendations": report.recommendations,
                "daily_metrics": [
                    {
                        "date": m.date,
                        "status": m.status,
                        "cards_created": m.cards_created,
                        "sources_found": m.sources_found,
                        "categories_present": m.categories_present,
                        "errors": m.errors
                    }
                    for m in report.daily_metrics
                ]
            }
            print(json.dumps(report_dict, indent=2))
        else:
            passes = monitor.print_report(report)
            sys.exit(0 if passes else 1)

    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
