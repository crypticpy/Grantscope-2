"""
Processing Metrics Models for Monitoring Dashboard

This module provides Pydantic models for the processing metrics API endpoints,
enabling monitoring of discovery runs, research tasks, source diversity,
and classification accuracy.

Supports:
- SourceCategoryMetrics: Metrics for a single source category
- DiscoveryRunMetrics: Aggregated metrics for discovery runs
- ResearchTaskMetrics: Aggregated metrics for research tasks
- ClassificationMetrics: Classification accuracy metrics
- ProcessingMetrics: Comprehensive processing metrics for monitoring dashboard
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class SourceCategoryMetrics(BaseModel):
    """Metrics for a single source category."""

    category: str
    sources_fetched: int = 0
    articles_processed: int = 0
    cards_generated: int = 0
    errors: int = 0


class DiscoveryRunMetrics(BaseModel):
    """Aggregated metrics for discovery runs."""

    total_runs: int = 0
    completed_runs: int = 0
    failed_runs: int = 0
    avg_cards_per_run: float = 0.0
    avg_sources_per_run: float = 0.0
    total_cards_created: int = 0
    total_cards_enriched: int = 0


class ResearchTaskMetrics(BaseModel):
    """Aggregated metrics for research tasks."""

    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    queued_tasks: int = 0
    processing_tasks: int = 0
    avg_processing_time_seconds: Optional[float] = None


class ClassificationMetrics(BaseModel):
    """Classification accuracy metrics."""

    total_validations: int = 0
    correct_count: int = 0
    accuracy_percentage: Optional[float] = None
    target_accuracy: float = 85.0
    meets_target: bool = False


class ProcessingMetrics(BaseModel):
    """
    Comprehensive processing metrics for monitoring dashboard.

    Includes:
    - Source diversity metrics (sources fetched per category)
    - Discovery run metrics (runs, cards generated, etc.)
    - Research task metrics (tasks by status, processing time)
    - Classification accuracy metrics
    - Time period information
    """

    # Time range for metrics
    period_start: datetime
    period_end: datetime
    period_days: int = 7

    # Source diversity metrics
    sources_by_category: List[SourceCategoryMetrics] = []
    total_source_categories: int = 0

    # Discovery run metrics
    discovery_runs: DiscoveryRunMetrics = DiscoveryRunMetrics()

    # Research task metrics
    research_tasks: ResearchTaskMetrics = ResearchTaskMetrics()

    # Classification metrics
    classification: ClassificationMetrics = ClassificationMetrics()

    # Card generation summary
    cards_generated_in_period: int = 0
    cards_with_all_scores: int = 0

    # Error summary
    total_errors: int = 0
    error_rate_percentage: Optional[float] = None
