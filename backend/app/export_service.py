"""
Export Service for Intelligence Cards and Workstream Reports.

This service handles generation of export files in multiple formats:
- PDF: Using ReportLab for professional document generation
- PowerPoint: Using python-pptx for presentation slides
- CSV: Using pandas for tabular data export

Chart Generation:
- Score radar charts showing all dimensions
- Score bar charts for individual scores
- Pillar distribution charts for workstream reports
- All charts use matplotlib with 'Agg' backend (non-GUI)

Usage:
    export_service = ExportService(supabase_client)
    pdf_path = await export_service.generate_pdf(card_data)
    pptx_path = await export_service.generate_pptx(card_data)
    csv_content = await export_service.generate_csv(card_data)
"""

import io
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import matplotlib
matplotlib.use('Agg')  # Non-GUI backend - must be set before importing pyplot
import matplotlib.pyplot as plt
import numpy as np

# PowerPoint imports
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ReportLab imports for PDF generation
from reportlab.lib import colors as rl_colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    PageBreak,
    HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from supabase import Client

from .models.export import (
    CardExportData,
    ExportFormat,
    EXPORT_CONTENT_TYPES,
    get_export_filename,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

# Foresight branding colors
FORESIGHT_COLORS = {
    "primary": "#1E3A5F",      # Deep blue
    "secondary": "#2E86AB",    # Lighter blue
    "accent": "#A23B72",       # Magenta accent
    "success": "#28A745",      # Green for positive metrics
    "warning": "#FFC107",      # Yellow for warnings
    "danger": "#DC3545",       # Red for negative/risk
    "light": "#F8F9FA",        # Light background
    "dark": "#343A40",         # Dark text
}

# Score colors for charts
SCORE_COLORS = {
    "Novelty": "#2E86AB",
    "Maturity": "#28A745",
    "Impact": "#A23B72",
    "Relevance": "#FFC107",
    "Velocity": "#17A2B8",
    "Risk": "#DC3545",
    "Opportunity": "#6F42C1",
}

# Chart settings
CHART_DPI = 300
CHART_FIGURE_SIZE = (8, 6)
RADAR_FIGURE_SIZE = (8, 8)

# PowerPoint settings
PPTX_SLIDE_WIDTH = Inches(13.333)  # 16:9 widescreen
PPTX_SLIDE_HEIGHT = Inches(7.5)
PPTX_TITLE_FONT_SIZE = Pt(44)
PPTX_SUBTITLE_FONT_SIZE = Pt(24)
PPTX_BODY_FONT_SIZE = Pt(18)
PPTX_SMALL_FONT_SIZE = Pt(14)
PPTX_MARGIN = Inches(0.5)
PPTX_CHART_WIDTH = Inches(5)
PPTX_CHART_HEIGHT = Inches(4)

# PDF settings
PDF_PAGE_SIZE = letter
PDF_MARGIN = 0.75 * inch
PDF_TITLE_FONT_SIZE = 24
PDF_HEADING_FONT_SIZE = 14
PDF_BODY_FONT_SIZE = 11
PDF_SMALL_FONT_SIZE = 9
PDF_CHART_WIDTH = 5.5 * inch
PDF_CHART_HEIGHT = 4 * inch

# ReportLab color conversion helper
def hex_to_rl_color(hex_color: str) -> rl_colors.Color:
    """Convert hex color string to ReportLab Color object."""
    hex_color = hex_color.lstrip('#')
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return rl_colors.Color(r, g, b)


# PDF color palette using Foresight colors
PDF_COLORS = {
    "primary": hex_to_rl_color(FORESIGHT_COLORS["primary"]),
    "secondary": hex_to_rl_color(FORESIGHT_COLORS["secondary"]),
    "accent": hex_to_rl_color(FORESIGHT_COLORS["accent"]),
    "success": hex_to_rl_color(FORESIGHT_COLORS["success"]),
    "warning": hex_to_rl_color(FORESIGHT_COLORS["warning"]),
    "danger": hex_to_rl_color(FORESIGHT_COLORS["danger"]),
    "light": hex_to_rl_color(FORESIGHT_COLORS["light"]),
    "dark": hex_to_rl_color(FORESIGHT_COLORS["dark"]),
}


# ============================================================================
# Export Service
# ============================================================================

class ExportService:
    """
    Service for generating export files from intelligence cards and workstreams.

    Supports PDF, PowerPoint, and CSV export formats with embedded visualizations.
    Follows the service class pattern from research_service.py.
    """

    def __init__(self, supabase: Client):
        """
        Initialize the ExportService.

        Args:
            supabase: Supabase client for database queries
        """
        self.supabase = supabase
        logger.info("ExportService initialized")

    # ========================================================================
    # Chart Generation Methods
    # ========================================================================

    def generate_score_chart(
        self,
        card_data: CardExportData,
        chart_type: str = "bar",
        dpi: int = CHART_DPI
    ) -> Optional[str]:
        """
        Generate a chart showing card scores.

        Args:
            card_data: Card data containing scores
            chart_type: Type of chart ('bar' or 'radar')
            dpi: Resolution for the chart image

        Returns:
            Path to the generated chart image, or None if generation fails
        """
        try:
            scores = card_data.get_all_scores()

            # Filter out None scores
            valid_scores = {k: v for k, v in scores.items() if v is not None}

            if not valid_scores:
                logger.warning(f"No valid scores for card {card_data.id}, skipping chart")
                return None

            if chart_type == "radar":
                return self._generate_radar_chart(valid_scores, card_data.name, dpi)
            else:
                return self._generate_bar_chart(valid_scores, card_data.name, dpi)

        except Exception as e:
            logger.error(f"Error generating score chart: {e}")
            return None

    def _generate_bar_chart(
        self,
        scores: Dict[str, int],
        title: str,
        dpi: int
    ) -> str:
        """
        Generate a horizontal bar chart of scores.

        Args:
            scores: Dictionary of score names to values
            title: Chart title
            dpi: Resolution for the image

        Returns:
            Path to the generated chart image
        """
        fig, ax = plt.subplots(figsize=CHART_FIGURE_SIZE)

        try:
            labels = list(scores.keys())
            values = list(scores.values())
            colors = [SCORE_COLORS.get(label, FORESIGHT_COLORS["primary"]) for label in labels]

            y_pos = np.arange(len(labels))

            bars = ax.barh(y_pos, values, color=colors, edgecolor='white', height=0.6)

            # Add value labels on bars
            for bar, value in zip(bars, values):
                width = bar.get_width()
                ax.text(
                    width + 2, bar.get_y() + bar.get_height() / 2,
                    f'{value}',
                    va='center', ha='left',
                    fontsize=10, fontweight='bold',
                    color=FORESIGHT_COLORS["dark"]
                )

            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels, fontsize=11)
            ax.set_xlim(0, 110)  # Extra space for labels
            ax.set_xlabel('Score (0-100)', fontsize=11)
            ax.set_title(f'Scores: {title[:40]}...', fontsize=12, fontweight='bold', pad=15)

            # Style the chart
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_color(FORESIGHT_COLORS["light"])
            ax.spines['left'].set_color(FORESIGHT_COLORS["light"])

            # Add gridlines
            ax.xaxis.grid(True, linestyle='--', alpha=0.3)
            ax.set_axisbelow(True)

            plt.tight_layout()

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.png',
                delete=False,
                prefix='foresight_chart_'
            )
            plt.savefig(temp_file.name, dpi=dpi, bbox_inches='tight', facecolor='white')

            return temp_file.name

        finally:
            plt.close(fig)  # CRITICAL: Prevent memory leaks

    def _generate_radar_chart(
        self,
        scores: Dict[str, int],
        title: str,
        dpi: int
    ) -> str:
        """
        Generate a radar/spider chart of scores.

        Args:
            scores: Dictionary of score names to values
            title: Chart title
            dpi: Resolution for the image

        Returns:
            Path to the generated chart image
        """
        fig, ax = plt.subplots(figsize=RADAR_FIGURE_SIZE, subplot_kw=dict(polar=True))

        try:
            labels = list(scores.keys())
            values = list(scores.values())

            # Number of variables
            num_vars = len(labels)

            # Compute angle for each axis
            angles = [n / float(num_vars) * 2 * np.pi for n in range(num_vars)]
            angles += angles[:1]  # Complete the loop

            # Complete the data loop
            values_plot = values + values[:1]

            # Plot the data
            ax.plot(angles, values_plot, 'o-', linewidth=2, color=FORESIGHT_COLORS["primary"])
            ax.fill(angles, values_plot, alpha=0.25, color=FORESIGHT_COLORS["secondary"])

            # Set the labels
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels, fontsize=11)

            # Set y-axis limits
            ax.set_ylim(0, 100)
            ax.set_yticks([20, 40, 60, 80, 100])
            ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=9, color='gray')

            # Add title
            ax.set_title(
                f'Score Profile: {title[:35]}...',
                fontsize=12, fontweight='bold', pad=20
            )

            plt.tight_layout()

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.png',
                delete=False,
                prefix='foresight_radar_'
            )
            plt.savefig(temp_file.name, dpi=dpi, bbox_inches='tight', facecolor='white')

            return temp_file.name

        finally:
            plt.close(fig)  # CRITICAL: Prevent memory leaks

    def generate_pillar_distribution_chart(
        self,
        pillar_counts: Dict[str, int],
        title: str = "Pillar Distribution",
        dpi: int = CHART_DPI
    ) -> Optional[str]:
        """
        Generate a pie/donut chart showing distribution of cards across pillars.

        Args:
            pillar_counts: Dictionary mapping pillar names to card counts
            title: Chart title
            dpi: Resolution for the image

        Returns:
            Path to the generated chart image, or None if no data
        """
        if not pillar_counts:
            logger.warning("No pillar data for distribution chart")
            return None

        fig, ax = plt.subplots(figsize=CHART_FIGURE_SIZE)

        try:
            labels = list(pillar_counts.keys())
            values = list(pillar_counts.values())

            # Generate colors from palette
            colors = plt.cm.Set2(np.linspace(0, 1, len(labels)))

            # Create donut chart
            wedges, texts, autotexts = ax.pie(
                values,
                labels=labels,
                autopct='%1.1f%%',
                colors=colors,
                pctdistance=0.75,
                wedgeprops=dict(width=0.5, edgecolor='white'),
                textprops={'fontsize': 10}
            )

            # Style the percentage text
            for autotext in autotexts:
                autotext.set_fontsize(9)
                autotext.set_fontweight('bold')

            ax.set_title(title, fontsize=12, fontweight='bold', pad=15)

            # Add legend
            ax.legend(
                wedges, [f'{l} ({v})' for l, v in zip(labels, values)],
                title="Pillars",
                loc="center left",
                bbox_to_anchor=(1, 0, 0.5, 1),
                fontsize=9
            )

            plt.tight_layout()

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.png',
                delete=False,
                prefix='foresight_pillar_'
            )
            plt.savefig(temp_file.name, dpi=dpi, bbox_inches='tight', facecolor='white')

            return temp_file.name

        finally:
            plt.close(fig)  # CRITICAL: Prevent memory leaks

    def generate_horizon_distribution_chart(
        self,
        horizon_counts: Dict[str, int],
        title: str = "Horizon Distribution",
        dpi: int = CHART_DPI
    ) -> Optional[str]:
        """
        Generate a bar chart showing distribution of cards across horizons.

        Args:
            horizon_counts: Dictionary mapping horizon names to card counts
            title: Chart title
            dpi: Resolution for the image

        Returns:
            Path to the generated chart image, or None if no data
        """
        if not horizon_counts:
            logger.warning("No horizon data for distribution chart")
            return None

        fig, ax = plt.subplots(figsize=(6, 4))

        try:
            # Order horizons properly
            horizon_order = ['H1', 'H2', 'H3']
            labels = []
            values = []

            for h in horizon_order:
                if h in horizon_counts:
                    labels.append(h)
                    values.append(horizon_counts[h])

            # Add any remaining horizons
            for h, v in horizon_counts.items():
                if h not in horizon_order:
                    labels.append(h)
                    values.append(v)

            # Horizon colors
            horizon_colors = {
                'H1': FORESIGHT_COLORS["success"],
                'H2': FORESIGHT_COLORS["warning"],
                'H3': FORESIGHT_COLORS["secondary"],
            }
            colors = [horizon_colors.get(l, FORESIGHT_COLORS["primary"]) for l in labels]

            x_pos = np.arange(len(labels))
            bars = ax.bar(x_pos, values, color=colors, edgecolor='white', width=0.6)

            # Add value labels on bars
            for bar, value in zip(bars, values):
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2, height + 0.5,
                    f'{value}',
                    ha='center', va='bottom',
                    fontsize=11, fontweight='bold'
                )

            ax.set_xticks(x_pos)
            ax.set_xticklabels(labels, fontsize=12, fontweight='bold')
            ax.set_ylabel('Number of Cards', fontsize=11)
            ax.set_title(title, fontsize=12, fontweight='bold', pad=15)

            # Style
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.yaxis.grid(True, linestyle='--', alpha=0.3)
            ax.set_axisbelow(True)

            plt.tight_layout()

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix='.png',
                delete=False,
                prefix='foresight_horizon_'
            )
            plt.savefig(temp_file.name, dpi=dpi, bbox_inches='tight', facecolor='white')

            return temp_file.name

        finally:
            plt.close(fig)  # CRITICAL: Prevent memory leaks

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def cleanup_temp_files(self, file_paths: List[str]) -> None:
        """
        Clean up temporary chart files.

        Args:
            file_paths: List of file paths to delete
        """
        for path in file_paths:
            try:
                if path and Path(path).exists():
                    Path(path).unlink()
                    logger.debug(f"Cleaned up temp file: {path}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {path}: {e}")

    async def get_card_data(self, card_id: str) -> Optional[CardExportData]:
        """
        Fetch card data from database and convert to CardExportData.

        Args:
            card_id: UUID of the card to fetch

        Returns:
            CardExportData object or None if not found
        """
        try:
            response = self.supabase.table("cards").select("*").eq("id", card_id).single().execute()

            if not response.data:
                return None

            return CardExportData(**response.data)

        except Exception as e:
            logger.error(f"Error fetching card {card_id}: {e}")
            return None

    async def get_workstream_cards(
        self,
        workstream_id: str,
        max_cards: int = 50
    ) -> Tuple[Optional[Dict[str, Any]], List[CardExportData]]:
        """
        Fetch workstream metadata and associated cards.

        Args:
            workstream_id: UUID of the workstream
            max_cards: Maximum number of cards to fetch

        Returns:
            Tuple of (workstream_data, list of CardExportData)
        """
        try:
            # Fetch workstream
            ws_response = self.supabase.table("workstreams").select("*").eq("id", workstream_id).single().execute()

            if not ws_response.data:
                return None, []

            workstream = ws_response.data

            # Fetch associated cards via workstream_cards junction table
            cards_response = self.supabase.table("workstream_cards").select(
                "card_id, cards(*)"
            ).eq("workstream_id", workstream_id).limit(max_cards).execute()

            cards = []
            if cards_response.data:
                for item in cards_response.data:
                    if item.get("cards"):
                        cards.append(CardExportData(**item["cards"]))

            return workstream, cards

        except Exception as e:
            logger.error(f"Error fetching workstream {workstream_id}: {e}")
            return None, []

    def format_score_display(self, score: Optional[int]) -> str:
        """
        Format a score for display, handling None values.

        Args:
            score: Score value (0-100) or None

        Returns:
            Formatted string representation
        """
        return str(score) if score is not None else "N/A"

    def get_content_type(self, format: ExportFormat) -> str:
        """
        Get the MIME content type for an export format.

        Args:
            format: Export format

        Returns:
            MIME content type string
        """
        return EXPORT_CONTENT_TYPES.get(format, "application/octet-stream")

    def generate_filename(self, name: str, format: ExportFormat) -> str:
        """
        Generate a safe filename for an export.

        Args:
            name: Card or workstream name
            format: Export format

        Returns:
            Safe filename with extension
        """
        return get_export_filename(name, format)

    # ========================================================================
    # CSV Export Methods
    # ========================================================================

    async def generate_csv(
        self,
        card_data: CardExportData,
    ) -> str:
        """
        Generate CSV export for a single intelligence card.

        Exports card data in a tabular format suitable for analysis
        in Excel or other spreadsheet applications. All card fields
        and scores are included as columns.

        Args:
            card_data: Card data to export

        Returns:
            CSV string content (not file path)

        Raises:
            ValueError: If card_data is invalid
        """
        import pandas as pd

        try:
            # Define the CSV columns in the specified order
            csv_columns = [
                "id",
                "name",
                "summary",
                "description",
                "pillar_id",
                "goal_id",
                "stage_id",
                "horizon",
                "novelty_score",
                "maturity_score",
                "impact_score",
                "relevance_score",
                "velocity_score",
                "risk_score",
                "opportunity_score",
            ]

            # Build the row data from card_data
            row_data = {
                "id": card_data.id,
                "name": card_data.name,
                "summary": card_data.summary or "",
                "description": card_data.description or "",
                "pillar_id": card_data.pillar_id or "",
                "goal_id": card_data.goal_id or "",
                "stage_id": card_data.stage_id or "",
                "horizon": card_data.horizon or "",
                "novelty_score": card_data.novelty_score,
                "maturity_score": card_data.maturity_score,
                "impact_score": card_data.impact_score,
                "relevance_score": card_data.relevance_score,
                "velocity_score": card_data.velocity_score,
                "risk_score": card_data.risk_score,
                "opportunity_score": card_data.opportunity_score,
            }

            # Create DataFrame with single row
            df = pd.DataFrame([row_data], columns=csv_columns)

            # Convert to CSV string without index column
            csv_content = df.to_csv(index=False)

            logger.info(f"Generated CSV export for card {card_data.id}: {card_data.name}")

            return csv_content

        except Exception as e:
            logger.error(f"Error generating CSV for card {card_data.id}: {e}")
            raise ValueError(f"Failed to generate CSV export: {e}")

    async def generate_csv_multi(
        self,
        cards: List[CardExportData],
    ) -> str:
        """
        Generate CSV export for multiple intelligence cards.

        Exports multiple cards as rows in a single CSV file,
        suitable for bulk data analysis in Excel or other tools.

        Args:
            cards: List of card data to export

        Returns:
            CSV string content with multiple rows

        Raises:
            ValueError: If cards list is empty or invalid
        """
        import pandas as pd

        if not cards:
            logger.warning("No cards provided for CSV export")
            return self._generate_empty_csv()

        try:
            # Define the CSV columns in the specified order
            csv_columns = [
                "id",
                "name",
                "summary",
                "description",
                "pillar_id",
                "goal_id",
                "stage_id",
                "horizon",
                "novelty_score",
                "maturity_score",
                "impact_score",
                "relevance_score",
                "velocity_score",
                "risk_score",
                "opportunity_score",
            ]

            # Build row data for all cards
            rows = []
            for card_data in cards:
                row = {
                    "id": card_data.id,
                    "name": card_data.name,
                    "summary": card_data.summary or "",
                    "description": card_data.description or "",
                    "pillar_id": card_data.pillar_id or "",
                    "goal_id": card_data.goal_id or "",
                    "stage_id": card_data.stage_id or "",
                    "horizon": card_data.horizon or "",
                    "novelty_score": card_data.novelty_score,
                    "maturity_score": card_data.maturity_score,
                    "impact_score": card_data.impact_score,
                    "relevance_score": card_data.relevance_score,
                    "velocity_score": card_data.velocity_score,
                    "risk_score": card_data.risk_score,
                    "opportunity_score": card_data.opportunity_score,
                }
                rows.append(row)

            # Create DataFrame with all rows
            df = pd.DataFrame(rows, columns=csv_columns)

            # Convert to CSV string without index column
            csv_content = df.to_csv(index=False)

            logger.info(f"Generated CSV export for {len(cards)} cards")

            return csv_content

        except Exception as e:
            logger.error(f"Error generating multi-card CSV: {e}")
            raise ValueError(f"Failed to generate CSV export: {e}")

    def _generate_empty_csv(self) -> str:
        """
        Generate an empty CSV with just headers.

        Returns:
            CSV string with headers only
        """
        import pandas as pd

        csv_columns = [
            "id",
            "name",
            "summary",
            "description",
            "pillar_id",
            "goal_id",
            "stage_id",
            "horizon",
            "novelty_score",
            "maturity_score",
            "impact_score",
            "relevance_score",
            "velocity_score",
            "risk_score",
            "opportunity_score",
        ]

        df = pd.DataFrame(columns=csv_columns)
        return df.to_csv(index=False)
