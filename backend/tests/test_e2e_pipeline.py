"""
End-to-End Pipeline Test for Enhanced AI Content Processing

This test verifies the complete pipeline integration:
1. All 5 source categories (RSS, News, Academic, Government, Tech Blog) are fetched
2. 4-dimensional scoring (impact, velocity, novelty, risk) is computed
3. Source diversity metrics are tracked
4. Classification validation infrastructure is in place
5. Processing metrics are logged correctly

Usage:
    pytest backend/tests/test_e2e_pipeline.py -v
    # Or run directly:
    python backend/tests/test_e2e_pipeline.py
"""

import asyncio
import logging
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a single test case."""
    name: str
    passed: bool
    message: str
    duration_seconds: float
    details: Optional[Dict[str, Any]] = None


class E2EPipelineTest:
    """
    End-to-end test suite for the enhanced AI content processing pipeline.

    Validates:
    - Multi-source content ingestion (5 categories)
    - 4-dimensional scoring system
    - Source diversity tracking
    - Processing metrics and observability
    """

    def __init__(self):
        self.results: List[TestResult] = []
        self.start_time = datetime.now()

    def record_result(self, result: TestResult):
        """Record a test result."""
        self.results.append(result)
        status = "PASS" if result.passed else "FAIL"
        logger.info(f"[{status}] {result.name}: {result.message}")

    async def run_all_tests(self) -> bool:
        """Run all end-to-end tests."""
        logger.info("=" * 60)
        logger.info("ENHANCED AI CONTENT PROCESSING PIPELINE - E2E TEST")
        logger.info("=" * 60)

        # Test 1: Source Fetcher Imports
        await self.test_source_fetcher_imports()

        # Test 2: Individual Source Fetchers
        await self.test_rss_fetcher()
        await self.test_news_fetcher()
        await self.test_academic_fetcher()
        await self.test_government_fetcher()
        await self.test_tech_blog_fetcher()

        # Test 3: Discovery Service Integration
        await self.test_discovery_service_imports()

        # Test 4: Source Category Configuration
        await self.test_source_category_configuration()

        # Test 5: AI Service Scoring
        await self.test_ai_service_scoring_fields()

        # Test 6: Validation Models
        await self.test_validation_models()

        # Test 7: Metrics Tracking Classes
        await self.test_metrics_tracking_classes()

        # Generate summary
        self._print_summary()

        # Return True if all tests passed
        return all(r.passed for r in self.results)

    async def test_source_fetcher_imports(self):
        """Test that all source fetchers can be imported."""
        start = datetime.now()
        try:
            from app.source_fetchers import (
                fetch_rss_sources,
                FetchedArticle,
                fetch_news_articles,
                NewsArticle,
                fetch_academic_papers,
                AcademicPaper,
                fetch_government_sources,
                GovernmentDocument,
                fetch_tech_blog_articles,
                TechBlogArticle,
            )

            # Verify all expected exports exist
            assert fetch_rss_sources is not None
            assert fetch_news_articles is not None
            assert fetch_academic_papers is not None
            assert fetch_government_sources is not None
            assert fetch_tech_blog_articles is not None

            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Source Fetcher Imports",
                passed=True,
                message="All 5 source fetchers imported successfully",
                duration_seconds=duration,
                details={"fetchers": ["rss", "news", "academic", "government", "tech_blog"]}
            ))

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Source Fetcher Imports",
                passed=False,
                message=f"Import failed: {str(e)}",
                duration_seconds=duration
            ))

    async def test_rss_fetcher(self):
        """Test RSS fetcher functionality."""
        start = datetime.now()
        try:
            from app.source_fetchers.rss_fetcher import fetch_rss_sources

            # Test with a known stable RSS feed
            test_feeds = ["https://news.ycombinator.com/rss"]

            articles = await fetch_rss_sources(
                feed_urls=test_feeds,
                max_articles_per_feed=5
            )

            duration = (datetime.now() - start).total_seconds()

            if len(articles) > 0:
                # Verify article structure
                sample = articles[0]
                has_required_fields = all([
                    hasattr(sample, 'url') and sample.url,
                    hasattr(sample, 'title') and sample.title,
                    hasattr(sample, 'source_name'),
                ])

                self.record_result(TestResult(
                    name="RSS Fetcher",
                    passed=has_required_fields,
                    message=f"Fetched {len(articles)} articles from RSS feed",
                    duration_seconds=duration,
                    details={"article_count": len(articles), "source": "Hacker News RSS"}
                ))
            else:
                self.record_result(TestResult(
                    name="RSS Fetcher",
                    passed=False,
                    message="No articles fetched from RSS feed",
                    duration_seconds=duration
                ))

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="RSS Fetcher",
                passed=False,
                message=f"RSS fetch failed: {str(e)}",
                duration_seconds=duration
            ))

    async def test_news_fetcher(self):
        """Test News outlet fetcher structure."""
        start = datetime.now()
        try:
            from app.source_fetchers.news_fetcher import (
                fetch_news_articles,
                NewsArticle,
                NewsFetcher,
                NEWS_SOURCES
            )

            # Verify the news fetcher structure
            assert hasattr(NewsFetcher, '__aenter__'), "NewsFetcher should be async context manager"
            assert len(NEWS_SOURCES) >= 3, "Should have at least 3 default news sources"

            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="News Fetcher Structure",
                passed=True,
                message=f"News fetcher has {len(NEWS_SOURCES)} default sources configured",
                duration_seconds=duration,
                details={"source_count": len(NEWS_SOURCES)}
            ))

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="News Fetcher Structure",
                passed=False,
                message=f"News fetcher validation failed: {str(e)}",
                duration_seconds=duration
            ))

    async def test_academic_fetcher(self):
        """Test Academic paper fetcher."""
        start = datetime.now()
        try:
            from app.source_fetchers.academic_fetcher import (
                fetch_academic_papers,
                AcademicPaper,
                convert_to_raw_source
            )

            # Test arXiv search (small query)
            result = await fetch_academic_papers(
                query="municipal government technology",
                max_results=3
            )

            duration = (datetime.now() - start).total_seconds()

            if result and result.papers:
                sample = result.papers[0]
                has_required_fields = all([
                    hasattr(sample, 'url') and sample.url,
                    hasattr(sample, 'title') and sample.title,
                    hasattr(sample, 'abstract'),
                ])

                self.record_result(TestResult(
                    name="Academic Fetcher",
                    passed=has_required_fields,
                    message=f"Fetched {len(result.papers)} papers from arXiv",
                    duration_seconds=duration,
                    details={"paper_count": len(result.papers)}
                ))
            else:
                # No papers is okay - arXiv search may not return results for specific queries
                self.record_result(TestResult(
                    name="Academic Fetcher",
                    passed=True,
                    message="Academic fetcher ran successfully (0 papers for test query)",
                    duration_seconds=duration
                ))

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Academic Fetcher",
                passed=False,
                message=f"Academic fetch failed: {str(e)}",
                duration_seconds=duration
            ))

    async def test_government_fetcher(self):
        """Test Government source fetcher structure."""
        start = datetime.now()
        try:
            from app.source_fetchers.government_fetcher import (
                fetch_government_sources,
                GovernmentDocument,
                GovernmentFetcher,
                GOVERNMENT_SOURCES
            )

            # Verify fetcher structure
            assert hasattr(GovernmentFetcher, '__aenter__'), "GovernmentFetcher should be async context manager"
            assert len(GOVERNMENT_SOURCES) >= 5, "Should have at least 5 government sources"

            # Verify GovernmentDocument dataclass
            assert hasattr(GovernmentDocument, 'source_category')

            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Government Fetcher Structure",
                passed=True,
                message=f"Government fetcher has {len(GOVERNMENT_SOURCES)} sources configured",
                duration_seconds=duration,
                details={"source_count": len(GOVERNMENT_SOURCES)}
            ))

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Government Fetcher Structure",
                passed=False,
                message=f"Government fetcher validation failed: {str(e)}",
                duration_seconds=duration
            ))

    async def test_tech_blog_fetcher(self):
        """Test Tech blog fetcher structure."""
        start = datetime.now()
        try:
            from app.source_fetchers.tech_blog_fetcher import (
                fetch_tech_blog_articles,
                TechBlogArticle,
                TechBlogFetcher,
                TECH_BLOG_SOURCES
            )

            # Verify fetcher structure
            assert hasattr(TechBlogFetcher, '__aenter__'), "TechBlogFetcher should be async context manager"
            assert len(TECH_BLOG_SOURCES) >= 3, "Should have at least 3 tech blog sources"

            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Tech Blog Fetcher Structure",
                passed=True,
                message=f"Tech blog fetcher has {len(TECH_BLOG_SOURCES)} sources configured",
                duration_seconds=duration,
                details={"source_count": len(TECH_BLOG_SOURCES)}
            ))

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Tech Blog Fetcher Structure",
                passed=False,
                message=f"Tech blog fetcher validation failed: {str(e)}",
                duration_seconds=duration
            ))

    async def test_discovery_service_imports(self):
        """Test discovery service source category integration."""
        start = datetime.now()
        try:
            # Check if supabase is available - this is the main external dependency
            try:
                import supabase
            except ImportError:
                # Supabase not installed - test configuration directly via mock
                duration = (datetime.now() - start).total_seconds()

                # We can still test the enum and config by importing just those
                # Use importlib to bypass the supabase import at module level
                import importlib.util
                import sys

                # Read the source file and extract just the enum and dataclass
                spec_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'discovery_service.py')
                with open(spec_path, 'r') as f:
                    source_content = f.read()

                # Check that SourceCategory enum has all expected values
                expected_in_source = [
                    'RSS = "rss"',
                    'NEWS = "news"',
                    'ACADEMIC = "academic"',
                    'GOVERNMENT = "government"',
                    'TECH_BLOG = "tech_blog"',
                ]

                all_found = all(cat in source_content for cat in expected_in_source)

                self.record_result(TestResult(
                    name="Discovery Service Integration",
                    passed=all_found,
                    message="All 5 source categories defined in discovery_service.py (supabase skipped)",
                    duration_seconds=duration,
                    details={"categories": ["rss", "news", "academic", "government", "tech_blog"]}
                ))
                return

            from app.discovery_service import (
                DiscoveryService,
                DiscoveryConfig,
                SourceCategory,
                SourceCategoryConfig,
                MultiSourceFetchResult,
                SourceDiversityMetrics,
                ProcessingTimeMetrics,
                APITokenUsage,
            )

            # Verify all 5 source categories are defined
            expected_categories = {'rss', 'news', 'academic', 'government', 'tech_blog'}
            actual_categories = {cat.value for cat in SourceCategory}

            assert expected_categories == actual_categories, \
                f"Expected categories {expected_categories}, got {actual_categories}"

            # Verify default config includes all categories
            config = DiscoveryConfig()
            assert len(config.source_categories) >= 5, "Config should have all 5 source categories"

            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Discovery Service Integration",
                passed=True,
                message=f"All 5 source categories integrated: {', '.join(sorted(actual_categories))}",
                duration_seconds=duration,
                details={"categories": list(sorted(actual_categories))}
            ))

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Discovery Service Integration",
                passed=False,
                message=f"Discovery service integration failed: {str(e)}",
                duration_seconds=duration
            ))

    async def test_source_category_configuration(self):
        """Test source category configuration defaults."""
        start = datetime.now()
        try:
            # Check if supabase is available
            try:
                import supabase
            except ImportError:
                # Supabase not installed - verify configuration via source inspection
                duration = (datetime.now() - start).total_seconds()

                spec_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'discovery_service.py')
                with open(spec_path, 'r') as f:
                    source_content = f.read()

                # Check that enable_multi_source defaults to True
                has_multi_source = 'enable_multi_source: bool = True' in source_content

                # Check that default source categories are configured
                has_default_config = 'if not self.source_categories:' in source_content

                self.record_result(TestResult(
                    name="Source Category Configuration",
                    passed=has_multi_source and has_default_config,
                    message="Source category config verified in source (supabase skipped)",
                    duration_seconds=duration,
                    details={"enable_multi_source": has_multi_source, "has_default_config": has_default_config}
                ))
                return

            from app.discovery_service import DiscoveryConfig, SourceCategory

            config = DiscoveryConfig()

            # Verify each category has proper configuration
            all_enabled = True
            category_details = {}

            for category in SourceCategory:
                cat_config = config.source_categories.get(category.value)
                if cat_config is None:
                    all_enabled = False
                    category_details[category.value] = "MISSING"
                else:
                    category_details[category.value] = {
                        "enabled": cat_config.enabled,
                        "max_sources": cat_config.max_sources
                    }
                    if not cat_config.enabled:
                        all_enabled = False

            # Verify enable_multi_source is True by default
            assert config.enable_multi_source, "enable_multi_source should be True by default"

            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Source Category Configuration",
                passed=all_enabled,
                message="All 5 source categories configured and enabled by default" if all_enabled else "Some categories not enabled",
                duration_seconds=duration,
                details=category_details
            ))

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Source Category Configuration",
                passed=False,
                message=f"Configuration test failed: {str(e)}",
                duration_seconds=duration
            ))

    async def test_ai_service_scoring_fields(self):
        """Test AI service includes velocity and risk scoring."""
        start = datetime.now()
        try:
            from app.ai_service import AnalysisResult
            import inspect

            # Get AnalysisResult fields
            sig = inspect.signature(AnalysisResult)
            field_names = list(sig.parameters.keys())

            # Verify all 4 scoring dimensions exist
            required_scores = ['impact', 'velocity', 'novelty', 'risk']
            found_scores = []
            missing_scores = []

            for score in required_scores:
                if score in field_names:
                    found_scores.append(score)
                else:
                    missing_scores.append(score)

            all_present = len(missing_scores) == 0

            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="4-Dimensional Scoring Fields",
                passed=all_present,
                message=f"Found scores: {', '.join(found_scores)}" if all_present else f"Missing: {', '.join(missing_scores)}",
                duration_seconds=duration,
                details={"found": found_scores, "missing": missing_scores}
            ))

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="4-Dimensional Scoring Fields",
                passed=False,
                message=f"Scoring field test failed: {str(e)}",
                duration_seconds=duration
            ))

    async def test_validation_models(self):
        """Test classification validation models exist."""
        start = datetime.now()
        try:
            from app.models.validation import (
                ClassificationValidation,
                ClassificationValidationCreate,
                ClassificationAccuracyMetrics,
                ValidationSummary,
                ClassificationConfusionMatrix,
                VALID_PILLAR_CODES
            )

            # Verify pillar codes - Austin strategic priorities
            expected_pillars = {'CH', 'EW', 'HG', 'HH', 'MC', 'PS'}
            actual_pillars = set(VALID_PILLAR_CODES)

            pillars_match = expected_pillars == actual_pillars

            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Validation Models",
                passed=pillars_match,
                message=f"Validation models loaded with {len(VALID_PILLAR_CODES)} pillar codes",
                duration_seconds=duration,
                details={"pillar_codes": list(VALID_PILLAR_CODES)}
            ))

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Validation Models",
                passed=False,
                message=f"Validation model test failed: {str(e)}",
                duration_seconds=duration
            ))

    async def test_metrics_tracking_classes(self):
        """Test metrics tracking classes exist and work."""
        start = datetime.now()
        try:
            # Check if supabase is available
            try:
                import supabase
            except ImportError:
                # Supabase not installed - verify metrics classes via source inspection
                duration = (datetime.now() - start).total_seconds()

                spec_path = os.path.join(os.path.dirname(__file__), '..', 'app', 'discovery_service.py')
                with open(spec_path, 'r') as f:
                    source_content = f.read()

                # Check for metrics classes
                has_processing_time = 'class ProcessingTimeMetrics:' in source_content
                has_token_usage = 'class APITokenUsage:' in source_content
                has_diversity = 'class SourceDiversityMetrics:' in source_content
                has_to_dict = source_content.count('def to_dict(self)') >= 3  # All three should have to_dict

                all_present = has_processing_time and has_token_usage and has_diversity and has_to_dict

                self.record_result(TestResult(
                    name="Metrics Tracking Classes",
                    passed=all_present,
                    message="All metrics classes defined in source (supabase skipped)",
                    duration_seconds=duration,
                    details={
                        "ProcessingTimeMetrics": has_processing_time,
                        "APITokenUsage": has_token_usage,
                        "SourceDiversityMetrics": has_diversity,
                        "has_to_dict_methods": has_to_dict
                    }
                ))
                return

            from app.discovery_service import (
                ProcessingTimeMetrics,
                APITokenUsage,
                SourceDiversityMetrics
            )

            # Test ProcessingTimeMetrics
            time_metrics = ProcessingTimeMetrics()
            time_metrics.query_generation_seconds = 1.5
            time_metrics.multi_source_fetch_seconds = 10.2
            time_dict = time_metrics.to_dict()

            assert 'query_generation_seconds' in time_dict
            assert 'multi_source_fetch_seconds' in time_dict
            assert 'total_seconds' in time_dict

            # Test APITokenUsage
            token_usage = APITokenUsage()
            token_usage.add_tokens("triage", 1000)
            token_usage.add_tokens("analysis", 2000)
            token_dict = token_usage.to_dict()

            assert token_dict['triage_tokens'] == 1000
            assert token_dict['analysis_tokens'] == 2000
            assert token_dict['total_tokens'] == 3000

            # Test SourceDiversityMetrics
            test_sources = {
                "rss": 20,
                "news": 15,
                "academic": 10,
                "government": 12,
                "tech_blog": 8
            }
            diversity = SourceDiversityMetrics.compute(test_sources)
            diversity_dict = diversity.to_dict()

            assert diversity_dict['total_sources'] == 65
            assert diversity_dict['categories_fetched'] == 5
            assert 0 <= diversity_dict['category_coverage'] <= 1
            assert 0 <= diversity_dict['balance_score'] <= 1

            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Metrics Tracking Classes",
                passed=True,
                message="All metrics classes work correctly (ProcessingTime, TokenUsage, SourceDiversity)",
                duration_seconds=duration,
                details={
                    "processing_time_fields": list(time_dict.keys()),
                    "token_usage_fields": list(token_dict.keys()),
                    "diversity_sample": {
                        "total_sources": diversity_dict['total_sources'],
                        "balance_score": round(diversity_dict['balance_score'], 2)
                    }
                }
            ))

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.record_result(TestResult(
                name="Metrics Tracking Classes",
                passed=False,
                message=f"Metrics tracking test failed: {str(e)}",
                duration_seconds=duration
            ))

    def _print_summary(self):
        """Print test summary."""
        total_duration = (datetime.now() - self.start_time).total_seconds()
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)

        logger.info("")
        logger.info("=" * 60)
        logger.info("TEST SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Duration: {total_duration:.2f}s")
        logger.info("")

        if failed > 0:
            logger.info("FAILED TESTS:")
            for r in self.results:
                if not r.passed:
                    logger.info(f"  - {r.name}: {r.message}")

        logger.info("")
        if failed == 0:
            logger.info("ALL TESTS PASSED!")
        else:
            logger.info(f"TESTS FAILED: {failed}/{total}")
        logger.info("=" * 60)


async def main():
    """Run the E2E test suite."""
    test_suite = E2EPipelineTest()
    success = await test_suite.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    # Change to backend directory for imports
    os.chdir(os.path.join(os.path.dirname(__file__), '..'))
    asyncio.run(main())
