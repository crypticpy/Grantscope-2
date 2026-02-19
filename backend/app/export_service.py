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
    export_service = ExportService(db)
    pdf_path = await export_service.generate_pdf(card_data)
    pptx_path = await export_service.generate_pptx(card_data)
    csv_content = await export_service.generate_csv(card_data)
"""

import io
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import matplotlib

matplotlib.use("Agg")  # Non-GUI backend - must be set before importing pyplot
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
    BaseDocTemplate,
    Frame,
    PageTemplate,
    KeepTogether,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db.card import Card
from app.models.db.workstream import Workstream, WorkstreamCard

from .models.export import (
    CardExportData,
    ExportFormat,
    EXPORT_CONTENT_TYPES,
    get_export_filename,
)

# Import classification definitions from gamma_service for backup slides
# DEPRECATED: HORIZON_*/STAGE_* - use PIPELINE_STATUSES for new code
from .gamma_service import (
    HORIZON_NAMES,
    HORIZON_DEFINITIONS,
    STAGE_NAMES,
    STAGE_DEFINITIONS,
)
from .taxonomy import (
    PILLAR_COLORS,
    PILLAR_DEFINITIONS,
    PILLAR_NAMES,
    PIPELINE_STATUSES,
    get_pipeline_phase,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Utility helpers
# ============================================================================


def _parse_float_safe(value: Any, default: float = 0.0) -> float:
    """Safely parse a value to float, stripping common currency chars.

    Handles values like "$50k", "TBD", "$1,000,000", etc.
    Returns default on failure.
    """
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().replace(",", "").replace("$", "")
    # Handle k/m suffixes
    multiplier = 1.0
    if s.lower().endswith("k"):
        s = s[:-1]
        multiplier = 1000.0
    elif s.lower().endswith("m"):
        s = s[:-1]
        multiplier = 1_000_000.0
    try:
        return float(s) * multiplier
    except (ValueError, TypeError):
        return default


# ============================================================================
# Constants
# ============================================================================

# Official City of Austin Brand Colors
# https://austin.gov/design/brand
COA_BRAND_COLORS = {
    # Official Palette
    "logo_blue": "#44499C",  # Primary - headers, titles, accents
    "logo_green": "#009F4D",  # Secondary - highlights, positive indicators
    "faded_white": "#f7f6f5",  # Backgrounds
    # Supporting Palette
    "dark_blue": "#22254E",  # Emphasis text
    "dark_green": "#005027",
    "light_blue": "#dcf2fd",  # Subtle backgrounds
    "light_green": "#dff0e3",  # Callout boxes
    # Extended Palette
    "red": "#F83125",  # Risks, concerns
    "orange": "#FF8F00",
    "yellow": "#FFC600",
    "cyan": "#009CDE",
    "dark_gray": "#636262",  # Body text
    "black": "#000000",
}

# GrantScope branding colors - mapped to City of Austin brand
GRANTSCOPE_COLORS = {
    "primary": COA_BRAND_COLORS["logo_blue"],  # Official Logo Blue
    "secondary": COA_BRAND_COLORS["logo_green"],  # Official Logo Green
    "accent": COA_BRAND_COLORS["cyan"],  # Cyan accent
    "success": COA_BRAND_COLORS["logo_green"],  # Green for positive metrics
    "warning": COA_BRAND_COLORS["yellow"],  # Yellow for warnings
    "danger": COA_BRAND_COLORS["red"],  # Red for negative/risk
    "light": COA_BRAND_COLORS["faded_white"],  # Light background
    "dark": COA_BRAND_COLORS["dark_gray"],  # Dark text
}

# Score colors for charts - using COA brand palette
SCORE_COLORS = {
    "Novelty": COA_BRAND_COLORS["cyan"],
    "Maturity": COA_BRAND_COLORS["logo_green"],
    "Impact": COA_BRAND_COLORS["logo_blue"],
    "Relevance": COA_BRAND_COLORS["yellow"],
    "Velocity": COA_BRAND_COLORS["orange"],
    "Risk": COA_BRAND_COLORS["red"],
    "Opportunity": COA_BRAND_COLORS["dark_blue"],
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
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0
    return rl_colors.Color(r, g, b)


# PDF color palette using GrantScope colors
PDF_COLORS = {
    "primary": hex_to_rl_color(GRANTSCOPE_COLORS["primary"]),
    "secondary": hex_to_rl_color(GRANTSCOPE_COLORS["secondary"]),
    "accent": hex_to_rl_color(GRANTSCOPE_COLORS["accent"]),
    "success": hex_to_rl_color(GRANTSCOPE_COLORS["success"]),
    "warning": hex_to_rl_color(GRANTSCOPE_COLORS["warning"]),
    "danger": hex_to_rl_color(GRANTSCOPE_COLORS["danger"]),
    "light": hex_to_rl_color(GRANTSCOPE_COLORS["light"]),
    "dark": hex_to_rl_color(GRANTSCOPE_COLORS["dark"]),
}

# ============================================================================
# Classification Taxonomy (Pillars, Horizons, Stages)
# ============================================================================

# PILLAR_COLORS imported from taxonomy.py (canonical source of truth)

# DEPRECATED: Horizon colors - use PIPELINE_STATUSES[status]["color"] for new code.
HORIZON_COLORS = {
    "H1": {
        "name": "Mainstream",
        "timeframe": "0-3 years",
        "color": "#22c55e",
        "bg": "#dcfce7",
        "description": "Current system, confirms baseline",
    },
    "H2": {
        "name": "Transitional",
        "timeframe": "3-7 years",
        "color": "#f59e0b",
        "bg": "#fef3c7",
        "description": "Emerging alternatives, pilots",
    },
    "H3": {
        "name": "Transformative",
        "timeframe": "7-15+ years",
        "color": "#a855f7",
        "bg": "#f3e8ff",
        "description": "Weak signals, novel possibilities",
    },
}

# DEPRECATED: Stage definitions - use PIPELINE_STATUSES for new code.
STAGE_INFO = {
    1: {
        "name": "Concept",
        "horizon": "H3",
        "description": "Academic research, theoretical exploration",
    },
    2: {
        "name": "Emerging",
        "horizon": "H3",
        "description": "Startups forming, patents filed",
    },
    3: {"name": "Prototype", "horizon": "H2", "description": "Working demos exist"},
    4: {
        "name": "Pilot",
        "horizon": "H2",
        "description": "Real-world testing (private sector)",
    },
    5: {
        "name": "Municipal Pilot",
        "horizon": "H2",
        "description": "Government entity testing",
    },
    6: {
        "name": "Early Adoption",
        "horizon": "H1",
        "description": "Multiple cities implementing",
    },
    7: {"name": "Mainstream", "horizon": "H1", "description": "Widespread adoption"},
    8: {"name": "Mature", "horizon": "H1", "description": "Established, commoditized"},
}

# ============================================================================
# Branding Assets & AI Disclosure
# ============================================================================


# Path to City of Austin logo (relative to backend directory)
def _get_logo_path() -> Optional[str]:
    """Get the path to the City of Austin logo, checking multiple locations."""
    # Check relative to this file's location
    base_dir = Path(
        __file__
    ).parent.parent.parent  # Go up from app/ to backend/ to project root
    possible_paths = [
        base_dir / "branding" / "COA-Logo-Horizontal-Official-RGB.png",
        base_dir / "branding" / "COA-Icon-Official-RGB.png",
        Path(
            "/app/branding/COA-Logo-Horizontal-Official-RGB.png"
        ),  # Railway deployment
        Path("/app/branding/COA-Icon-Official-RGB.png"),  # Railway deployment fallback
    ]

    for path in possible_paths:
        if path.exists():
            return str(path)

    logger.warning("City of Austin logo not found in expected locations")
    return None


COA_LOGO_PATH = _get_logo_path()

# AI Technology Disclosure - transparent listing of all AI systems used
AI_TECHNOLOGY_DISCLOSURE = """
AI-Powered Research & Analysis Platform

This strategic intelligence report was generated using advanced artificial intelligence technologies:

• Anthropic Claude (Opus/Sonnet) - Strategic analysis, synthesis, and report generation
• OpenAI GPT-4o - Classification, scoring, and natural language processing  
• GPT Researcher - Autonomous deep research and source discovery
• Exa AI - High-quality source search and content retrieval
• Firecrawl - Web content extraction and PDF processing
• Tavily - Real-time news and research aggregation

The City of Austin is committed to transparent and responsible use of AI technology 
in public service. All AI-generated content is reviewed for accuracy and relevance 
to municipal government operations.
""".strip()

# Shorter disclosure for footer
AI_DISCLOSURE_SHORT = (
    "Generated by GrantScope2 Strategic Intelligence Platform | "
    "AI Technologies: Anthropic Claude, OpenAI GPT-4o, GPT Researcher, Exa AI, Firecrawl, Tavily"
)


# ============================================================================
# Professional PDF Builder with Header/Footer
# ============================================================================


class ProfessionalPDFBuilder:
    """
    Custom PDF document builder with professional header and footer.

    Used for executive briefs and workstream reports that will be shared
    with senior city leadership.
    """

    def __init__(
        self,
        filename: str,
        title: str,
        subtitle: Optional[str] = None,
        include_logo: bool = True,
        include_ai_disclosure: bool = True,
    ):
        """
        Initialize the PDF builder.

        Args:
            filename: Output PDF file path
            title: Document title for header
            subtitle: Optional subtitle
            include_logo: Whether to include City of Austin logo
            include_ai_disclosure: Whether to include AI technology disclosure
        """
        self.filename = filename
        self.title = title
        self.subtitle = subtitle
        self.include_logo = include_logo
        self.include_ai_disclosure = include_ai_disclosure
        self.page_width, self.page_height = letter

        # Margins - extra space at top/bottom for header/footer
        self.left_margin = 0.75 * inch
        self.right_margin = 0.75 * inch
        self.top_margin = 1.4 * inch  # Extra space for header
        self.bottom_margin = 1.2 * inch  # Extra space for footer

    def _draw_header(self, canvas_obj: canvas.Canvas, doc):
        """Draw the professional header on each page."""
        canvas_obj.saveState()

        # Header background - clean white
        canvas_obj.setFillColor(rl_colors.white)
        canvas_obj.rect(
            0,
            self.page_height - 1.1 * inch,
            self.page_width,
            1.1 * inch,
            fill=True,
            stroke=False,
        )

        # Add accent line below header - primary blue for brand consistency
        canvas_obj.setStrokeColor(PDF_COLORS["primary"])
        canvas_obj.setLineWidth(2)
        canvas_obj.line(
            0,
            self.page_height - 1.1 * inch,
            self.page_width,
            self.page_height - 1.1 * inch,
        )

        # City of Austin logo (if available and enabled)
        logo_width = 0
        if self.include_logo and COA_LOGO_PATH and Path(COA_LOGO_PATH).exists():
            try:
                # Draw logo on left side of header
                logo_height = 0.55 * inch
                logo_width = 1.65 * inch  # Aspect ratio ~3:1 for horizontal logo
                canvas_obj.drawImage(
                    COA_LOGO_PATH,
                    self.left_margin,
                    self.page_height - 0.85 * inch,
                    width=logo_width,
                    height=logo_height,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                logo_width += 0.25 * inch  # Add spacing after logo
            except Exception as e:
                logger.warning(f"Failed to add logo to PDF header: {e}")
                logo_width = 0

        # Vertical separator line after logo
        if logo_width > 0:
            canvas_obj.setStrokeColor(hex_to_rl_color("#E0E0E0"))
            canvas_obj.setLineWidth(1)
            sep_x = self.left_margin + logo_width + 0.1 * inch
            canvas_obj.line(
                sep_x,
                self.page_height - 0.25 * inch,
                sep_x,
                self.page_height - 0.95 * inch,
            )
            logo_width += 0.25 * inch  # Extra spacing after separator

        # GrantScope branding text
        text_x = self.left_margin + logo_width

        # "GRANTSCOPE" title - primary blue to match website
        canvas_obj.setFillColor(PDF_COLORS["primary"])
        canvas_obj.setFont("Helvetica-Bold", 16)
        canvas_obj.drawString(text_x, self.page_height - 0.45 * inch, "GRANTSCOPE")

        # "Strategic Intelligence Platform" subtitle - gray
        canvas_obj.setFillColor(rl_colors.gray)
        canvas_obj.setFont("Helvetica", 9)
        canvas_obj.drawString(
            text_x, self.page_height - 0.62 * inch, "Strategic Intelligence Platform"
        )

        # Document title on right side - black
        canvas_obj.setFillColor(PDF_COLORS["dark"])
        canvas_obj.setFont("Helvetica-Bold", 11)
        title_text = f"{self.title[:45]}..." if len(self.title) > 45 else self.title
        title_width = canvas_obj.stringWidth(title_text, "Helvetica-Bold", 11)
        canvas_obj.drawString(
            self.page_width - self.right_margin - title_width,
            self.page_height - 0.45 * inch,
            title_text,
        )

        # Page generation date on right - black
        canvas_obj.setFillColor(PDF_COLORS["dark"])
        canvas_obj.setFont("Helvetica", 9)
        date_text = datetime.now(timezone.utc).strftime("%B %d, %Y")
        date_width = canvas_obj.stringWidth(date_text, "Helvetica", 9)
        canvas_obj.drawString(
            self.page_width - self.right_margin - date_width,
            self.page_height - 0.62 * inch,
            date_text,
        )

        canvas_obj.restoreState()

    def _draw_footer(self, canvas_obj: canvas.Canvas, doc):
        """Draw the professional footer on each page."""
        canvas_obj.saveState()

        # Footer background
        canvas_obj.setFillColor(hex_to_rl_color("#F8F9FA"))
        canvas_obj.rect(0, 0, self.page_width, 1.0 * inch, fill=True, stroke=False)

        # Top border line
        canvas_obj.setStrokeColor(PDF_COLORS["primary"])
        canvas_obj.setLineWidth(1)
        canvas_obj.line(
            self.left_margin,
            1.0 * inch,
            self.page_width - self.right_margin,
            1.0 * inch,
        )

        # AI Technology Disclosure (if enabled)
        if self.include_ai_disclosure:
            canvas_obj.setFillColor(PDF_COLORS["dark"])
            canvas_obj.setFont("Helvetica", 7)

            # Multi-line disclosure
            disclosure_lines = [
                "AI-Powered Intelligence: This report was generated using Anthropic Claude, OpenAI GPT-4o,",
                "GPT Researcher, Exa AI, Firecrawl, and Tavily. The City of Austin is committed to",
                "transparent and responsible use of AI technology in public service.",
            ]

            y_pos = 0.75 * inch
            for line in disclosure_lines:
                canvas_obj.drawString(self.left_margin, y_pos, line)
                y_pos -= 0.12 * inch

        # Page number on right
        canvas_obj.setFont("Helvetica", 9)
        page_text = f"Page {doc.page}"
        page_width = canvas_obj.stringWidth(page_text, "Helvetica", 9)
        canvas_obj.drawString(
            self.page_width - self.right_margin - page_width, 0.4 * inch, page_text
        )

        # Confidentiality notice
        canvas_obj.setFont("Helvetica-Oblique", 7)
        canvas_obj.setFillColor(rl_colors.gray)
        canvas_obj.drawString(
            self.left_margin,
            0.25 * inch,
            "City of Austin Internal Document - For Official Use",
        )

        canvas_obj.restoreState()

    def _draw_header_footer(self, canvas_obj: canvas.Canvas, doc):
        """Combined callback for header and footer."""
        self._draw_header(canvas_obj, doc)
        self._draw_footer(canvas_obj, doc)

    def build(self, elements: List[Any]) -> str:
        """
        Build the PDF document with all elements.

        Args:
            elements: List of ReportLab flowable elements

        Returns:
            Path to the generated PDF file
        """
        # Create document with custom page template
        doc = BaseDocTemplate(
            self.filename,
            pagesize=letter,
            leftMargin=self.left_margin,
            rightMargin=self.right_margin,
            topMargin=self.top_margin,
            bottomMargin=self.bottom_margin,
        )

        # Create frame for content
        frame = Frame(
            self.left_margin,
            self.bottom_margin,
            self.page_width - self.left_margin - self.right_margin,
            self.page_height - self.top_margin - self.bottom_margin,
            id="normal",
        )

        # Create page template with header/footer
        template = PageTemplate(
            id="professional", frames=[frame], onPage=self._draw_header_footer
        )

        doc.addPageTemplates([template])
        doc.build(elements)

        return self.filename


def get_professional_pdf_styles() -> Dict[str, ParagraphStyle]:
    """
    Create custom paragraph styles for professional PDF generation.

    Returns:
        Dictionary of ParagraphStyle objects for executive documents
    """
    styles = getSampleStyleSheet()

    return {
        "DocTitle": ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=28,
            textColor=PDF_COLORS["primary"],
            spaceAfter=16,
            spaceBefore=8,
            alignment=TA_LEFT,
            fontName="Helvetica-Bold",
            leading=34,
        ),
        "DocSubtitle": ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontSize=14,
            textColor=PDF_COLORS["secondary"],
            spaceAfter=20,
            fontName="Helvetica",
            leading=18,
        ),
        "SectionHeading": ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=PDF_COLORS["primary"],
            spaceBefore=20,
            spaceAfter=10,
            fontName="Helvetica-Bold",
            borderPadding=(0, 0, 4, 0),
        ),
        "SubsectionHeading": ParagraphStyle(
            "SubsectionHeading",
            parent=styles["Heading2"],
            fontSize=13,
            textColor=PDF_COLORS["secondary"],
            spaceBefore=14,
            spaceAfter=6,
            fontName="Helvetica-Bold",
        ),
        "BodyText": ParagraphStyle(
            "BodyText",
            parent=styles["Normal"],
            fontSize=11,
            textColor=PDF_COLORS["dark"],
            spaceBefore=4,
            spaceAfter=8,
            leading=15,
            alignment=TA_JUSTIFY,
        ),
        "BulletText": ParagraphStyle(
            "BulletText",
            parent=styles["Normal"],
            fontSize=11,
            textColor=PDF_COLORS["dark"],
            spaceBefore=2,
            spaceAfter=4,
            leftIndent=20,
            bulletIndent=10,
            leading=14,
        ),
        "SmallText": ParagraphStyle(
            "SmallText",
            parent=styles["Normal"],
            fontSize=9,
            textColor=rl_colors.gray,
            spaceBefore=2,
            spaceAfter=2,
        ),
        "MetadataText": ParagraphStyle(
            "MetadataText",
            parent=styles["Normal"],
            fontSize=10,
            textColor=PDF_COLORS["dark"],
            spaceBefore=2,
            spaceAfter=2,
            fontName="Helvetica",
        ),
        "CalloutText": ParagraphStyle(
            "CalloutText",
            parent=styles["Normal"],
            fontSize=11,
            textColor=PDF_COLORS["primary"],
            spaceBefore=8,
            spaceAfter=8,
            leftIndent=15,
            rightIndent=15,
            borderPadding=10,
            backColor=hex_to_rl_color("#F0F4F8"),
            leading=15,
        ),
        "ExecutiveSummary": ParagraphStyle(
            "ExecutiveSummary",
            parent=styles["Normal"],
            fontSize=12,
            textColor=PDF_COLORS["dark"],
            spaceBefore=6,
            spaceAfter=12,
            leading=17,
            alignment=TA_JUSTIFY,
            fontName="Helvetica",
        ),
        "NumberedItem": ParagraphStyle(
            "NumberedItem",
            parent=styles["Normal"],
            fontSize=11,
            textColor=PDF_COLORS["dark"],
            spaceBefore=6,
            spaceAfter=4,
            leftIndent=25,
            firstLineIndent=-15,
            leading=14,
        ),
        "AppendixTitle": ParagraphStyle(
            "AppendixTitle",
            parent=styles["Heading1"],
            fontSize=18,
            textColor=PDF_COLORS["primary"],
            spaceBefore=24,
            spaceAfter=16,
            fontName="Helvetica-Bold",
        ),
        "AppendixHeading": ParagraphStyle(
            "AppendixHeading",
            parent=styles["Heading2"],
            fontSize=14,
            textColor=PDF_COLORS["secondary"],
            spaceBefore=16,
            spaceAfter=8,
            fontName="Helvetica-Bold",
        ),
        "AppendixBody": ParagraphStyle(
            "AppendixBody",
            parent=styles["Normal"],
            fontSize=10,
            textColor=PDF_COLORS["dark"],
            spaceBefore=2,
            spaceAfter=4,
            leading=13,
        ),
    }


# ============================================================================
# Robust Markdown Parser for AI-Generated Content
# ============================================================================


class MarkdownToPDFParser:
    """
    Robust parser for converting markdown to ReportLab PDF elements.

    Handles various AI-generated content formats gracefully:
    - Multiple heading styles (# ## ###, underlines, bold headings)
    - Bullet points (-, *, •, >, numbered)
    - Bold/italic formatting (**bold**, *italic*, __bold__, _italic_)
    - Links [text](url) - extracts text only for PDF
    - Code blocks (``` and inline `)
    - Horizontal rules (---, ***, ___)
    - Edge cases: mixed formatting, incomplete markers, nested lists
    """

    def __init__(self, styles: Dict[str, ParagraphStyle]):
        """Initialize with PDF styles dictionary."""
        self.styles = styles
        self.import_re()

    def import_re(self):
        """Import regex module."""
        import re

        self.re = re

    def clean_text(self, text: str) -> str:
        """
        Clean and sanitize text for PDF rendering.

        - Escapes XML special characters
        - Removes problematic unicode
        - Normalizes whitespace
        """
        if not text:
            return ""

        # Replace common problematic characters
        text = text.replace("\u200b", "")  # Zero-width space
        text = text.replace("\u00a0", " ")  # Non-breaking space
        text = text.replace("\r\n", "\n")
        text = text.replace("\r", "\n")

        # Normalize multiple spaces
        text = self.re.sub(r"  +", " ", text)

        return text.strip()

    def escape_xml(self, text: str) -> str:
        """Escape XML special characters for ReportLab."""
        if not text:
            return ""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        return text.replace(">", "&gt;")

    def convert_inline_formatting(self, text: str) -> str:
        """
        Convert markdown inline formatting to ReportLab XML tags.

        Handles: **bold**, *italic*, __bold__, _italic_, `code`, [links](url)
        """
        if not text:
            return ""

        # First escape XML characters
        text = self.escape_xml(text)

        # Convert bold: **text** or __text__
        text = self.re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
        text = self.re.sub(r"__(.+?)__", r"<b>\1</b>", text)

        # Convert italic: *text* or _text_ (but not within words)
        # Be careful not to match already-converted bold markers
        text = self.re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
        text = self.re.sub(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)", r"<i>\1</i>", text)

        # Convert inline code: `code`
        text = self.re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', text)

        # Convert links: [text](url) -> just the text
        text = self.re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

        # Clean up any leftover asterisks that didn't match patterns
        # This handles edge cases like "* Urgency:" which isn't meant to be italic

        return text

    def is_heading(self, line: str) -> Optional[Tuple[int, str]]:
        """
        Check if line is a heading. Returns (level, text) or None.

        Handles:
        - # Heading 1
        - ## Heading 2
        - ### Heading 3
        - **HEADING IN BOLD**
        - HEADING WITH COLON:
        """
        line = line.strip()

        if match := self.re.match(r"^(#{1,3})\s+(.+)$", line):
            level = len(match.group(1))
            text = match.group(2).strip()
            # Remove trailing # if present
            text = self.re.sub(r"\s*#+\s*$", "", text)
            return (level, text)

        # All caps section headers (common AI pattern)
        if self.re.match(r"^[A-Z][A-Z\s&\-]{5,}$", line) and not line.startswith("•"):
            return (2, line.title())

        return None

    def is_bullet_point(self, line: str) -> Optional[str]:
        """
        Check if line is a bullet point. Returns the bullet text or None.

        Handles: -, *, •, >, and numbered lists (1., 2., etc.)
        """
        line = line.strip()

        if match := self.re.match(r"^[\-\*•]\s+(.+)$", line):
            return match.group(1)

        return match.group(1) if (match := self.re.match(r"^>\s+(.+)$", line)) else None

    def is_numbered_item(self, line: str) -> Optional[Tuple[str, str]]:
        """
        Check if line is a numbered list item.
        Returns (number, text) or None.
        """
        line = line.strip()

        if match := self.re.match(r"^(\d+)[.\)]\s+(.+)$", line):
            return (match.group(1), match.group(2))

        return None

    def is_horizontal_rule(self, line: str) -> bool:
        """Check if line is a horizontal rule."""
        line = line.strip()
        return bool(self.re.match(r"^[-*_]{3,}$", line))

    def parse_to_elements(self, markdown_content: str) -> List[Any]:
        """
        Parse markdown content to ReportLab flowable elements.

        This is the main entry point for converting AI-generated markdown
        into properly formatted PDF elements.
        """
        if not markdown_content:
            return [Paragraph("No content available.", self.styles["BodyText"])]

        elements = []
        markdown_content = self.clean_text(markdown_content)
        lines = markdown_content.split("\n")

        current_paragraph_lines = []
        in_code_block = False
        code_block_content = []

        def flush_paragraph():
            """Helper to flush accumulated paragraph lines."""
            nonlocal current_paragraph_lines
            if current_paragraph_lines:
                para_text = " ".join(current_paragraph_lines)
                para_text = self.convert_inline_formatting(para_text)
                if para_text.strip():
                    elements.append(Paragraph(para_text, self.styles["BodyText"]))
                current_paragraph_lines = []

        for i, line in enumerate(lines):
            original_line = line
            line_stripped = line.strip()

            # Handle code blocks
            if line_stripped.startswith("```"):
                if in_code_block:
                    # End code block
                    in_code_block = False
                    if code_block_content:
                        code_text = "\n".join(code_block_content)
                        code_text = self.escape_xml(code_text)
                        elements.append(
                            Paragraph(
                                f'<font face="Courier" size="9">{code_text}</font>',
                                self.styles["BodyText"],
                            )
                        )
                        code_block_content = []
                else:
                    # Start code block
                    flush_paragraph()
                    in_code_block = True
                continue

            if in_code_block:
                code_block_content.append(line)
                continue

            # Empty line - flush paragraph
            if not line_stripped:
                flush_paragraph()
                continue

            # Check for horizontal rule
            if self.is_horizontal_rule(line_stripped):
                flush_paragraph()
                elements.append(Spacer(1, 8))
                elements.append(
                    HRFlowable(
                        width="60%",
                        thickness=1,
                        color=PDF_COLORS["light"],
                        spaceBefore=4,
                        spaceAfter=8,
                    )
                )
                continue

            # Check for headings
            heading = self.is_heading(line_stripped)
            if heading:
                flush_paragraph()
                level, text = heading
                text = self.convert_inline_formatting(text)

                if level == 1:
                    elements.append(Spacer(1, 10))
                    elements.append(Paragraph(text, self.styles["SectionHeading"]))
                elif level == 2:
                    elements.append(Paragraph(text, self.styles["SubsectionHeading"]))
                else:
                    elements.append(
                        Paragraph(f"<b>{text}</b>", self.styles["BodyText"])
                    )
                continue

            # Check for numbered items
            numbered = self.is_numbered_item(line_stripped)
            if numbered:
                flush_paragraph()
                num, text = numbered
                text = self.convert_inline_formatting(text)
                elements.append(
                    Paragraph(f"<b>{num}.</b> {text}", self.styles["NumberedItem"])
                )
                continue

            # Check for bullet points
            bullet = self.is_bullet_point(line_stripped)
            if bullet:
                flush_paragraph()
                bullet_text = self.convert_inline_formatting(bullet)
                elements.append(
                    Paragraph(f"• {bullet_text}", self.styles["BulletText"])
                )
                continue

            # Regular text - accumulate for paragraph
            current_paragraph_lines.append(line_stripped)

        # Flush any remaining content
        flush_paragraph()

        if in_code_block and code_block_content:
            code_text = "\n".join(code_block_content)
            code_text = self.escape_xml(code_text)
            elements.append(
                Paragraph(
                    f'<font face="Courier" size="9">{code_text}</font>',
                    self.styles["BodyText"],
                )
            )

        return elements


def create_classification_badges(
    classification: Dict[str, str], styles: Dict[str, ParagraphStyle]
) -> List[Any]:
    """
    Create visually styled classification badges for PDF.

    Args:
        classification: Dict with 'pillar', 'horizon', 'stage' keys
        styles: PDF styles dictionary

    Returns:
        List of ReportLab flowable elements showing colored badges
    """
    if not classification:
        return []

    elements = []
    badge_parts = []

    if pillar_code := classification.get("pillar", "").upper():
        if pillar_code in PILLAR_COLORS:
            pillar_info = PILLAR_COLORS[pillar_code]
            badge_parts.append(
                f'<font color="{pillar_info["color"]}"><b>{pillar_code}</b></font> {pillar_info["name"]}'
            )
        else:
            badge_parts.append(f"<b>Pillar:</b> {pillar_code}")

    # Pipeline status badge (preferred over horizon/stage)
    pipeline_status = classification.get("pipeline_status", "")
    if pipeline_status and pipeline_status in PIPELINE_STATUSES:
        ps_info = PIPELINE_STATUSES[pipeline_status]
        badge_parts.append(
            f'<font color="{ps_info["color"]}"><b>{ps_info["label"]}</b></font>'
        )
    elif pipeline_status:
        badge_parts.append(
            f"<b>Status:</b> {pipeline_status.replace('_', ' ').title()}"
        )

    # Legacy horizon badge (kept for backward compatibility)
    if horizon_code := classification.get("horizon", "").upper():
        if horizon_code in HORIZON_COLORS:
            horizon_info = HORIZON_COLORS[horizon_code]
            badge_parts.append(
                f'<font color="{horizon_info["color"]}"><b>{horizon_code}</b></font> {horizon_info["name"]} ({horizon_info["timeframe"]})'
            )
        else:
            badge_parts.append(f"<b>Horizon:</b> {horizon_code}")

    # Legacy stage badge (kept for backward compatibility)
    stage_raw = classification.get("stage", "")
    stage_num = None

    # Parse stage - can be "4", "stage 4", "4_proof", etc.
    import re

    if stage_match := re.search(r"(\d+)", str(stage_raw)):
        stage_num = int(stage_match.group(1))

    if stage_num and stage_num in STAGE_INFO:
        stage_info = STAGE_INFO[stage_num]
        horizon_for_stage = stage_info["horizon"]
        stage_color = HORIZON_COLORS.get(horizon_for_stage, {}).get("color", "#6366f1")
        badge_parts.append(
            f'<font color="{stage_color}"><b>Stage {stage_num}</b></font> {stage_info["name"]}'
        )
    elif stage_raw:
        badge_parts.append(f"<b>Stage:</b> {stage_raw}")

    if badge_parts:
        # Create a styled classification line with link hint
        badge_text = "   |   ".join(badge_parts)
        elements.extend(
            (
                Paragraph(badge_text, styles.get("MetadataText", styles["SmallText"])),
                Paragraph(
                    '<i><font size="8" color="gray">See Appendix A for classification definitions</font></i>',
                    styles.get("SmallText", styles["BodyText"]),
                ),
            )
        )
    return elements


def create_classification_appendix(styles: Dict[str, ParagraphStyle]) -> List[Any]:
    """
    Create an appendix explaining the GrantScope classification system.

    Returns a list of ReportLab flowable elements.
    """
    elements = [PageBreak()]

    # Appendix title
    elements.append(
        Paragraph(
            "Appendix A: Classification Framework",
            styles.get("AppendixTitle", styles["SectionHeading"]),
        )
    )

    elements.append(
        Paragraph(
            "This report uses the City of Austin's GrantScope2 strategic classification framework to categorize emerging trends and technologies.",
            styles.get("AppendixBody", styles["BodyText"]),
        )
    )
    elements.append(Spacer(1, 12))

    # Pillars section
    elements.append(
        Paragraph(
            "Strategic Pillars",
            styles.get("AppendixHeading", styles["SubsectionHeading"]),
        )
    )
    elements.append(
        Paragraph(
            "Pillars represent the six core areas of Austin's Comprehensive Strategic Plan (CSP):",
            styles.get("AppendixBody", styles["BodyText"]),
        )
    )

    elements.extend(
        Paragraph(
            f'<font color="{info["color"]}"><b>{code}</b></font> - <b>{info["name"]}</b>',
            styles.get("AppendixBody", styles["BodyText"]),
        )
        for code, info in PILLAR_COLORS.items()
    )
    elements.append(Spacer(1, 12))

    # Horizons section
    elements.append(
        Paragraph(
            "Planning Horizons",
            styles.get("AppendixHeading", styles["SubsectionHeading"]),
        )
    )
    elements.append(
        Paragraph(
            "Horizons indicate the expected timeline for impact:",
            styles.get("AppendixBody", styles["BodyText"]),
        )
    )

    elements.extend(
        Paragraph(
            f'<font color="{info["color"]}"><b>{code}: {info["name"]}</b></font> ({info["timeframe"]}) - {info["description"]}',
            styles.get("AppendixBody", styles["BodyText"]),
        )
        for code, info in HORIZON_COLORS.items()
    )
    elements.append(Spacer(1, 12))

    # Stages section
    elements.append(
        Paragraph(
            "Maturity Stages",
            styles.get("AppendixHeading", styles["SubsectionHeading"]),
        )
    )
    elements.append(
        Paragraph(
            "Stages indicate how mature a trend or technology is in its development lifecycle:",
            styles.get("AppendixBody", styles["BodyText"]),
        )
    )

    for stage_num, info in STAGE_INFO.items():
        horizon_color = HORIZON_COLORS.get(info["horizon"], {}).get("color", "#6366f1")
        elements.append(
            Paragraph(
                f'<font color="{horizon_color}"><b>Stage {stage_num}: {info["name"]}</b></font> ({info["horizon"]}) - {info["description"]}',
                styles.get("AppendixBody", styles["BodyText"]),
            )
        )
    elements.append(Spacer(1, 12))

    # Pipeline Statuses section
    elements.append(
        Paragraph(
            "Grant Pipeline Statuses",
            styles.get("AppendixHeading", styles["SubsectionHeading"]),
        )
    )
    elements.append(
        Paragraph(
            "Pipeline statuses track a grant opportunity through its lifecycle:",
            styles.get("AppendixBody", styles["BodyText"]),
        )
    )

    for ps_key, ps_info in PIPELINE_STATUSES.items():
        elements.append(
            Paragraph(
                f'<font color="{ps_info["color"]}"><b>{ps_info["label"]}</b></font> - {ps_info["description"]}',
                styles.get("AppendixBody", styles["BodyText"]),
            )
        )

    return elements


# ============================================================================
# Export Service
# ============================================================================


class ExportService:
    """
    Service for generating export files from intelligence cards and workstreams.

    Supports PDF, PowerPoint, and CSV export formats with embedded visualizations.
    Follows the service class pattern from research_service.py.
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the ExportService.

        Args:
            db: AsyncSession instance for database queries
        """
        self.db = db
        logger.info("ExportService initialized")

    # ========================================================================
    # Chart Generation Methods
    # ========================================================================

    def generate_score_chart(
        self, card_data: CardExportData, chart_type: str = "bar", dpi: int = CHART_DPI
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
                logger.warning(
                    f"No valid scores for card {card_data.id}, skipping chart"
                )
                return None

            if chart_type == "radar":
                return self._generate_radar_chart(valid_scores, card_data.name, dpi)
            else:
                return self._generate_bar_chart(valid_scores, card_data.name, dpi)

        except Exception as e:
            logger.error(f"Error generating score chart: {e}")
            return None

    def _generate_bar_chart(self, scores: Dict[str, int], title: str, dpi: int) -> str:
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
            colors = [
                SCORE_COLORS.get(label, GRANTSCOPE_COLORS["primary"])
                for label in labels
            ]

            y_pos = np.arange(len(labels))

            bars = ax.barh(y_pos, values, color=colors, edgecolor="white", height=0.6)

            # Add value labels on bars
            for bar, value in zip(bars, values):
                width = bar.get_width()
                ax.text(
                    width + 2,
                    bar.get_y() + bar.get_height() / 2,
                    f"{value}",
                    va="center",
                    ha="left",
                    fontsize=10,
                    fontweight="bold",
                    color=GRANTSCOPE_COLORS["dark"],
                )

            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels, fontsize=11)
            ax.set_xlim(0, 110)  # Extra space for labels
            ax.set_xlabel("Score (0-100)", fontsize=11)
            ax.set_title(
                f"Scores: {title[:40]}...", fontsize=12, fontweight="bold", pad=15
            )

            # Style the chart
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.spines["bottom"].set_color(GRANTSCOPE_COLORS["light"])
            ax.spines["left"].set_color(GRANTSCOPE_COLORS["light"])

            # Add gridlines
            ax.xaxis.grid(True, linestyle="--", alpha=0.3)
            ax.set_axisbelow(True)

            plt.tight_layout()

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, prefix="grantscope_chart_"
            )
            plt.savefig(temp_file.name, dpi=dpi, bbox_inches="tight", facecolor="white")

            return temp_file.name

        finally:
            plt.close(fig)  # CRITICAL: Prevent memory leaks

    def _generate_radar_chart(
        self, scores: Dict[str, int], title: str, dpi: int
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
            ax.plot(
                angles,
                values_plot,
                "o-",
                linewidth=2,
                color=GRANTSCOPE_COLORS["primary"],
            )
            ax.fill(
                angles, values_plot, alpha=0.25, color=GRANTSCOPE_COLORS["secondary"]
            )

            # Set the labels
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(labels, fontsize=11)

            # Set y-axis limits
            ax.set_ylim(0, 100)
            ax.set_yticks([20, 40, 60, 80, 100])
            ax.set_yticklabels(
                ["20", "40", "60", "80", "100"], fontsize=9, color="gray"
            )

            # Add title
            ax.set_title(
                f"Score Profile: {title[:35]}...",
                fontsize=12,
                fontweight="bold",
                pad=20,
            )

            plt.tight_layout()

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, prefix="grantscope_radar_"
            )
            plt.savefig(temp_file.name, dpi=dpi, bbox_inches="tight", facecolor="white")

            return temp_file.name

        finally:
            plt.close(fig)  # CRITICAL: Prevent memory leaks

    def generate_pillar_distribution_chart(
        self,
        pillar_counts: Dict[str, int],
        title: str = "Pillar Distribution",
        dpi: int = CHART_DPI,
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
                autopct="%1.1f%%",
                colors=colors,
                pctdistance=0.75,
                wedgeprops=dict(width=0.5, edgecolor="white"),
                textprops={"fontsize": 10},
            )

            # Style the percentage text
            for autotext in autotexts:
                autotext.set_fontsize(9)
                autotext.set_fontweight("bold")

            ax.set_title(title, fontsize=12, fontweight="bold", pad=15)

            # Add legend
            ax.legend(
                wedges,
                [f"{l} ({v})" for l, v in zip(labels, values)],
                title="Pillars",
                loc="center left",
                bbox_to_anchor=(1, 0, 0.5, 1),
                fontsize=9,
            )

            plt.tight_layout()

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, prefix="grantscope_pillar_"
            )
            plt.savefig(temp_file.name, dpi=dpi, bbox_inches="tight", facecolor="white")

            return temp_file.name

        finally:
            plt.close(fig)  # CRITICAL: Prevent memory leaks

    def generate_horizon_distribution_chart(
        self,
        horizon_counts: Dict[str, int],
        title: str = "Horizon Distribution",
        dpi: int = CHART_DPI,
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
            horizon_order = ["H1", "H2", "H3"]
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
                "H1": GRANTSCOPE_COLORS["success"],
                "H2": GRANTSCOPE_COLORS["warning"],
                "H3": GRANTSCOPE_COLORS["secondary"],
            }
            colors = [
                horizon_colors.get(l, GRANTSCOPE_COLORS["primary"]) for l in labels
            ]

            x_pos = np.arange(len(labels))
            bars = ax.bar(x_pos, values, color=colors, edgecolor="white", width=0.6)

            # Add value labels on bars
            for bar, value in zip(bars, values):
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    height + 0.5,
                    f"{value}",
                    ha="center",
                    va="bottom",
                    fontsize=11,
                    fontweight="bold",
                )

            ax.set_xticks(x_pos)
            ax.set_xticklabels(labels, fontsize=12, fontweight="bold")
            ax.set_ylabel("Number of Cards", fontsize=11)
            ax.set_title(title, fontsize=12, fontweight="bold", pad=15)

            # Style
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.yaxis.grid(True, linestyle="--", alpha=0.3)
            ax.set_axisbelow(True)

            plt.tight_layout()

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, prefix="grantscope_horizon_"
            )
            plt.savefig(temp_file.name, dpi=dpi, bbox_inches="tight", facecolor="white")

            return temp_file.name

        finally:
            plt.close(fig)  # CRITICAL: Prevent memory leaks

    # ========================================================================
    # PDF Generation Methods
    # ========================================================================

    def _get_pdf_styles(self) -> Dict[str, ParagraphStyle]:
        """
        Create custom paragraph styles for PDF generation.

        Returns:
            Dictionary of ParagraphStyle objects
        """
        styles = getSampleStyleSheet()

        return {
            "Title": ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=PDF_TITLE_FONT_SIZE,
                textColor=PDF_COLORS["primary"],
                spaceAfter=12,
                alignment=TA_CENTER,
                fontName="Helvetica-Bold",
            ),
            "Heading1": ParagraphStyle(
                "CustomHeading1",
                parent=styles["Heading1"],
                fontSize=PDF_HEADING_FONT_SIZE,
                textColor=PDF_COLORS["primary"],
                spaceBefore=18,
                spaceAfter=8,
                fontName="Helvetica-Bold",
            ),
            "Heading2": ParagraphStyle(
                "CustomHeading2",
                parent=styles["Heading2"],
                fontSize=PDF_BODY_FONT_SIZE + 1,
                textColor=PDF_COLORS["secondary"],
                spaceBefore=12,
                spaceAfter=6,
                fontName="Helvetica-Bold",
            ),
            "Body": ParagraphStyle(
                "CustomBody",
                parent=styles["Normal"],
                fontSize=PDF_BODY_FONT_SIZE,
                textColor=PDF_COLORS["dark"],
                spaceBefore=4,
                spaceAfter=4,
                leading=14,
            ),
            "Small": ParagraphStyle(
                "CustomSmall",
                parent=styles["Normal"],
                fontSize=PDF_SMALL_FONT_SIZE,
                textColor=rl_colors.gray,
                spaceBefore=2,
                spaceAfter=2,
            ),
            "Badge": ParagraphStyle(
                "Badge",
                parent=styles["Normal"],
                fontSize=PDF_SMALL_FONT_SIZE,
                textColor=rl_colors.white,
                alignment=TA_CENTER,
            ),
        }

    def _create_pdf_header(
        self, card_data: CardExportData, styles: Dict[str, ParagraphStyle]
    ) -> List[Any]:
        """
        Create PDF header elements for a card.

        Args:
            card_data: Card data to display
            styles: PDF styles dictionary

        Returns:
            List of flowable elements for the header
        """
        elements = []

        # Title
        title = Paragraph(card_data.name, styles["Title"])
        elements.extend((title, Spacer(1, 6)))
        # Horizontal rule
        elements.append(
            HRFlowable(
                width="100%",
                thickness=2,
                color=PDF_COLORS["primary"],
                spaceBefore=6,
                spaceAfter=12,
            )
        )

        # Metadata badges (pillar, horizon, stage)
        badge_data = []
        if card_data.pillar_name or card_data.pillar_id:
            badge_data.append(("Pillar", card_data.pillar_name or card_data.pillar_id))
        if card_data.horizon:
            badge_data.append(("Horizon", card_data.horizon))
        if card_data.stage_name or card_data.stage_id:
            badge_data.append(("Stage", card_data.stage_name or card_data.stage_id))
        if card_data.goal_name or card_data.goal_id:
            badge_data.append(("Goal", card_data.goal_name or card_data.goal_id))

        if badge_data:
            badge_table_data = [[]]
            for label, value in badge_data:
                badge_text = f"<b>{label}:</b> {value}"
                badge_table_data[0].append(Paragraph(badge_text, styles["Small"]))

            badge_table = Table(
                badge_table_data, colWidths=[1.5 * inch] * len(badge_data)
            )
            badge_table.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            elements.append(badge_table)
            elements.append(Spacer(1, 12))

        return elements

    def _create_pdf_summary_section(
        self, card_data: CardExportData, styles: Dict[str, ParagraphStyle]
    ) -> List[Any]:
        """
        Create PDF summary section for a card.

        Args:
            card_data: Card data to display
            styles: PDF styles dictionary

        Returns:
            List of flowable elements for the summary
        """
        elements = [Paragraph("Classification Overview", styles["Heading1"])]

        classification_items = []
        if card_data.pillar_name or card_data.pillar_id:
            classification_items.append(
                f"<b>Strategic Pillar:</b> {card_data.pillar_name or card_data.pillar_id}"
            )
        if card_data.goal_name or card_data.goal_id:
            classification_items.append(
                f"<b>Strategic Goal:</b> {card_data.goal_name or card_data.goal_id}"
            )
        if card_data.horizon:
            horizon_desc = {
                "H1": "Near-term (0-2 years)",
                "H2": "Mid-term (2-5 years)",
                "H3": "Long-term (5+ years)",
            }
            classification_items.append(
                f"<b>Time Horizon:</b> {card_data.horizon} - {horizon_desc.get(card_data.horizon, '')}"
            )
        if card_data.stage_name or card_data.stage_id:
            classification_items.append(
                f"<b>Maturity Stage:</b> {card_data.stage_name or card_data.stage_id}"
            )

        if classification_items:
            for item in classification_items:
                elements.append(Paragraph(item, styles["Body"]))
            elements.append(Spacer(1, 12))

        # Executive Summary
        if card_data.summary:
            elements.append(Paragraph("Executive Summary", styles["Heading1"]))
            elements.append(Paragraph(card_data.summary, styles["Body"]))
            elements.append(Spacer(1, 12))

        # Full Description
        if card_data.description:
            elements.append(Paragraph("Detailed Analysis", styles["Heading1"]))
            # Truncate very long descriptions
            description = card_data.description
            if len(description) > 3000:
                description = description[:3000] + "... [truncated]"
            elements.append(Paragraph(description, styles["Body"]))
            elements.append(Spacer(1, 12))

        return elements

    def _create_pdf_research_section(
        self, card_data: CardExportData, styles: Dict[str, ParagraphStyle]
    ) -> List[Any]:
        """
        Create PDF section for deep research report.

        Args:
            card_data: Card data containing research report
            styles: PDF styles dictionary

        Returns:
            List of flowable elements for the research section
        """
        elements = []

        if not card_data.deep_research_report:
            return elements

        elements.extend(
            (
                PageBreak(),
                Paragraph("Strategic Intelligence Report", styles["Title"]),
                Spacer(1, 6),
                Paragraph(
                    "<i>The following strategic intelligence report was generated through deep research analysis, "
                    "synthesizing multiple sources to provide actionable insights for decision-makers.</i>",
                    styles["Small"],
                ),
                Spacer(1, 12),
                HRFlowable(
                    width="100%",
                    thickness=1,
                    color=PDF_COLORS["secondary"],
                    spaceBefore=6,
                    spaceAfter=12,
                ),
            )
        )
        # Parse and render the markdown report
        # Simple markdown-to-PDF conversion for common elements
        report = card_data.deep_research_report

        # Truncate if extremely long
        if len(report) > 15000:
            report = (
                report[:15000]
                + "\n\n... [Report truncated for PDF export. View full report in the application.]"
            )

        # Process the report line by line
        lines = report.split("\n")
        for line in lines:
            line = line.strip()
            if not line:
                elements.append(Spacer(1, 6))
            elif line.startswith("# "):
                # Main heading
                elements.append(Paragraph(line[2:], styles["Heading1"]))
            elif line.startswith("## "):
                # Section heading
                elements.append(Paragraph(line[3:], styles["Heading2"]))
            elif line.startswith("### "):
                # Subsection heading
                text = f"<b>{line[4:]}</b>"
                elements.append(Paragraph(text, styles["Body"]))
            elif line.startswith("- ") or line.startswith("* "):
                # Bullet point
                text = f"• {line[2:]}"
                elements.append(Paragraph(text, styles["Body"]))
            elif line.startswith("**") and line.endswith("**"):
                # Bold text
                text = f"<b>{line[2:-2]}</b>"
                elements.append(Paragraph(text, styles["Body"]))
            else:
                # Regular paragraph
                # Escape any XML-unsafe characters
                safe_line = (
                    line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                )
                elements.append(Paragraph(safe_line, styles["Body"]))

        return elements

    def _create_pdf_scores_table(
        self, card_data: CardExportData, styles: Dict[str, ParagraphStyle]
    ) -> List[Any]:
        """
        Create PDF scores table for a card.

        Args:
            card_data: Card data to display
            styles: PDF styles dictionary

        Returns:
            List of flowable elements for the scores section
        """
        elements = [Paragraph("Scores", styles["Heading1"])]

        # Build scores table
        scores = card_data.get_all_scores()
        table_data = [["Metric", "Score", "Rating"]]

        for name, score in scores.items():
            score_display = self.format_score_display(score)

            # Determine rating based on score
            if score is None:
                rating = "Not Scored"
            elif score >= 80:
                rating = "Excellent"
            elif score >= 60:
                rating = "Good"
            elif score >= 40:
                rating = "Fair"
            else:
                rating = "Low"

            table_data.append([name, score_display, rating])

        # Create table with styling
        table = Table(table_data, colWidths=[2 * inch, 1 * inch, 1.5 * inch])
        table.setStyle(
            TableStyle(
                [
                    # Header styling
                    ("BACKGROUND", (0, 0), (-1, 0), PDF_COLORS["primary"]),
                    ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), PDF_BODY_FONT_SIZE),
                    ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                    # Body styling
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), PDF_BODY_FONT_SIZE),
                    ("ALIGN", (1, 1), (1, -1), "CENTER"),  # Center score column
                    ("ALIGN", (2, 1), (2, -1), "CENTER"),  # Center rating column
                    # Alternating row colors
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [rl_colors.white, PDF_COLORS["light"]],
                    ),
                    # Grid
                    ("GRID", (0, 0), (-1, -1), 0.5, PDF_COLORS["light"]),
                    ("BOX", (0, 0), (-1, -1), 1, PDF_COLORS["primary"]),
                    # Padding
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 18))

        return elements

    def _create_pdf_chart_section(
        self, card_data: CardExportData, styles: Dict[str, ParagraphStyle]
    ) -> Tuple[List[Any], List[str]]:
        """
        Create PDF chart section for a card.

        Args:
            card_data: Card data to display
            styles: PDF styles dictionary

        Returns:
            Tuple of (list of flowable elements, list of temp file paths to clean up)
        """
        elements = []
        temp_files = []

        if chart_path := self.generate_score_chart(card_data, chart_type="bar"):
            temp_files.append(chart_path)
            elements.append(Paragraph("Score Visualization", styles["Heading1"]))

            try:
                img = RLImage(
                    chart_path, width=PDF_CHART_WIDTH, height=PDF_CHART_HEIGHT
                )
                elements.extend((img, Spacer(1, 12)))
            except Exception as e:
                logger.warning(f"Failed to add chart image to PDF: {e}")

        return elements, temp_files

    def _create_pdf_footer(
        self, card_data: CardExportData, styles: Dict[str, ParagraphStyle]
    ) -> List[Any]:
        """
        Create PDF footer elements for a card.

        Args:
            card_data: Card data to display
            styles: PDF styles dictionary

        Returns:
            List of flowable elements for the footer
        """
        elements = [Spacer(1, 24)]

        elements.append(
            HRFlowable(
                width="100%",
                thickness=1,
                color=PDF_COLORS["light"],
                spaceBefore=6,
                spaceAfter=6,
            )
        )

        # Metadata footer
        footer_parts = []
        if card_data.created_at:
            footer_parts.append(f"Created: {card_data.created_at.strftime('%Y-%m-%d')}")
        if card_data.updated_at:
            footer_parts.append(f"Updated: {card_data.updated_at.strftime('%Y-%m-%d')}")
        footer_parts.append(
            f"Export Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
        )

        footer_text = " | ".join(footer_parts)
        elements.append(Paragraph(footer_text, styles["Small"]))

        # Branding
        elements.append(Spacer(1, 6))
        elements.append(
            Paragraph("Generated by GrantScope2 Intelligence Platform", styles["Small"])
        )

        return elements

    async def generate_pdf(
        self, card_data: CardExportData, include_charts: bool = True
    ) -> str:
        """
        Generate a professional PDF export for an intelligence card.

        Uses the professional PDF builder with City of Austin branding,
        GrantScope header, and AI technology disclosure footer.

        Args:
            card_data: CardExportData object containing all card information
            include_charts: Whether to include chart visualizations

        Returns:
            Path to the generated PDF file

        Raises:
            Exception: If PDF generation fails
        """
        import re

        temp_files = []

        try:
            # Create temp file for PDF
            pdf_file = tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False, prefix="grantscope_card_export_"
            )
            pdf_path = pdf_file.name
            pdf_file.close()

            # Get professional styles
            styles = get_professional_pdf_styles()

            # Build document elements
            elements = [Paragraph(card_data.name, styles["DocTitle"])]

            # Classification subtitle
            subtitle_parts = []
            if card_data.pillar_name or card_data.pillar_id:
                subtitle_parts.append(
                    f"Pillar: {card_data.pillar_name or card_data.pillar_id}"
                )
            if card_data.horizon:
                subtitle_parts.append(f"Horizon: {card_data.horizon}")
            if card_data.stage_name or card_data.stage_id:
                subtitle_parts.append(
                    f"Stage: {card_data.stage_name or card_data.stage_id}"
                )
            if subtitle_parts:
                elements.append(
                    Paragraph(" | ".join(subtitle_parts), styles["DocSubtitle"])
                )

            elements.append(Spacer(1, 6))
            elements.append(
                HRFlowable(
                    width="100%",
                    thickness=2,
                    color=PDF_COLORS["secondary"],
                    spaceBefore=4,
                    spaceAfter=16,
                )
            )

            # Executive Summary
            if card_data.summary:
                elements.append(
                    Paragraph("Executive Summary", styles["SectionHeading"])
                )
                elements.append(
                    Paragraph(card_data.summary, styles["ExecutiveSummary"])
                )
                elements.append(Spacer(1, 12))

            # Detailed Analysis / Description
            if card_data.description:
                elements.append(
                    Paragraph("Detailed Analysis", styles["SectionHeading"])
                )
                # Truncate very long descriptions
                description = card_data.description
                if len(description) > 5000:
                    description = description[:5000] + "... [truncated]"
                elements.append(Paragraph(description, styles["BodyText"]))
                elements.append(Spacer(1, 12))

            # Scores Section
            scores = card_data.get_all_scores()
            valid_scores = {k: v for k, v in scores.items() if v is not None}
            if valid_scores:
                elements.append(Paragraph("Score Analysis", styles["SectionHeading"]))

                # Build scores table
                table_data = [["Metric", "Score", "Rating"]]
                for name, score in valid_scores.items():
                    if score >= 80:
                        rating = "Excellent"
                    elif score >= 60:
                        rating = "Good"
                    elif score >= 40:
                        rating = "Fair"
                    else:
                        rating = "Low"
                    table_data.append([name, str(score), rating])

                table = Table(table_data, colWidths=[2 * inch, 1 * inch, 1.2 * inch])
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), PDF_COLORS["primary"]),
                            ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), 10),
                            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 1), (-1, -1), 10),
                            ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                            (
                                "ROWBACKGROUNDS",
                                (0, 1),
                                (-1, -1),
                                [rl_colors.white, hex_to_rl_color("#F8F9FA")],
                            ),
                            ("GRID", (0, 0), (-1, -1), 0.5, hex_to_rl_color("#E0E0E0")),
                            ("BOX", (0, 0), (-1, -1), 1, PDF_COLORS["primary"]),
                            ("TOPPADDING", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ]
                    )
                )
                elements.append(table)
                elements.append(Spacer(1, 16))

            # Charts (if enabled)
            if include_charts and valid_scores:
                if chart_path := self.generate_score_chart(card_data, chart_type="bar"):
                    temp_files.append(chart_path)
                    try:
                        img = RLImage(chart_path, width=5 * inch, height=3.5 * inch)
                        elements.append(img)
                        elements.append(Spacer(1, 16))
                    except Exception as e:
                        logger.warning(f"Failed to add chart image to PDF: {e}")

            # Deep Research Report (if available)
            if card_data.deep_research_report:
                elements.append(PageBreak())
                elements.append(
                    Paragraph("Strategic Intelligence Report", styles["SectionHeading"])
                )
                elements.append(Spacer(1, 8))

                # Parse and render the markdown report
                report = card_data.deep_research_report
                if len(report) > 20000:
                    report = (
                        report[:20000] + "\n\n... [Report truncated for PDF export]"
                    )

                lines = report.split("\n")
                current_paragraph = []

                for line in lines:
                    line_stripped = line.strip()

                    if not line_stripped:
                        if current_paragraph:
                            para_text = " ".join(current_paragraph)
                            para_text = re.sub(
                                r"\*\*(.+?)\*\*", r"<b>\1</b>", para_text
                            )
                            para_text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", para_text)
                            elements.append(Paragraph(para_text, styles["BodyText"]))
                            current_paragraph = []
                        continue

                    if line_stripped.startswith("# "):
                        if current_paragraph:
                            elements.append(
                                Paragraph(
                                    " ".join(current_paragraph), styles["BodyText"]
                                )
                            )
                            current_paragraph = []
                        elements.append(Spacer(1, 8))
                        elements.append(
                            Paragraph(line_stripped[2:], styles["SectionHeading"])
                        )
                    elif line_stripped.startswith("## "):
                        if current_paragraph:
                            elements.append(
                                Paragraph(
                                    " ".join(current_paragraph), styles["BodyText"]
                                )
                            )
                            current_paragraph = []
                        elements.append(
                            Paragraph(line_stripped[3:], styles["SubsectionHeading"])
                        )
                    elif line_stripped.startswith("### "):
                        if current_paragraph:
                            elements.append(
                                Paragraph(
                                    " ".join(current_paragraph), styles["BodyText"]
                                )
                            )
                            current_paragraph = []
                        elements.append(
                            Paragraph(f"<b>{line_stripped[4:]}</b>", styles["BodyText"])
                        )
                    elif line_stripped.startswith("- ") or line_stripped.startswith(
                        "* "
                    ):
                        if current_paragraph:
                            elements.append(
                                Paragraph(
                                    " ".join(current_paragraph), styles["BodyText"]
                                )
                            )
                            current_paragraph = []
                        bullet_text = re.sub(
                            r"\*\*(.+?)\*\*", r"<b>\1</b>", line_stripped[2:]
                        )
                        elements.append(
                            Paragraph(f"• {bullet_text}", styles["BulletText"])
                        )
                    elif re.match(r"^\d+\.\s", line_stripped):
                        if current_paragraph:
                            elements.append(
                                Paragraph(
                                    " ".join(current_paragraph), styles["BodyText"]
                                )
                            )
                            current_paragraph = []
                        elements.append(Paragraph(line_stripped, styles["BulletText"]))
                    elif line_stripped in ["---", "***"]:
                        if current_paragraph:
                            elements.append(
                                Paragraph(
                                    " ".join(current_paragraph), styles["BodyText"]
                                )
                            )
                            current_paragraph = []
                        elements.append(Spacer(1, 6))
                        elements.append(
                            HRFlowable(
                                width="50%", thickness=1, color=PDF_COLORS["light"]
                            )
                        )
                        elements.append(Spacer(1, 6))
                    else:
                        current_paragraph.append(line_stripped)

                if current_paragraph:
                    para_text = " ".join(current_paragraph)
                    para_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", para_text)
                    elements.append(Paragraph(para_text, styles["BodyText"]))

            # Metadata footer
            elements.append(Spacer(1, 20))
            elements.append(
                HRFlowable(width="100%", thickness=1, color=PDF_COLORS["light"])
            )
            elements.append(Spacer(1, 6))

            meta_items = []
            if card_data.created_at:
                meta_items.append(
                    f"Created: {card_data.created_at.strftime('%B %d, %Y')}"
                )
            if card_data.updated_at:
                meta_items.append(
                    f"Updated: {card_data.updated_at.strftime('%B %d, %Y')}"
                )
            for item in meta_items:
                elements.append(Paragraph(item, styles["SmallText"]))

            # Build PDF using professional builder with header/footer
            builder = ProfessionalPDFBuilder(
                filename=pdf_path,
                title=card_data.name,
                include_logo=True,
                include_ai_disclosure=True,
            )
            builder.build(elements)

            logger.info(f"Generated professional PDF export for card: {card_data.name}")
            return pdf_path

        except Exception as e:
            logger.error(f"Error generating PDF for card {card_data.name}: {e}")
            raise

        finally:
            # Clean up chart temp files
            self.cleanup_temp_files(temp_files)

    async def generate_workstream_pdf(
        self, workstream_id: str, include_charts: bool = True, max_cards: int = 50
    ) -> str:
        """
        Generate a PDF report for a workstream containing all associated cards.

        Args:
            workstream_id: UUID of the workstream
            include_charts: Whether to include chart visualizations
            max_cards: Maximum number of cards to include

        Returns:
            Path to the generated PDF file

        Raises:
            Exception: If PDF generation fails
        """
        temp_files = []

        try:
            # Fetch workstream and cards
            workstream, cards = await self.get_workstream_cards(
                workstream_id, max_cards
            )

            if not workstream:
                raise ValueError(f"Workstream {workstream_id} not found")

            # Create temp file for PDF
            pdf_file = tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False, prefix="grantscope_workstream_"
            )
            pdf_path = pdf_file.name
            pdf_file.close()

            # Get professional styles
            styles = get_professional_pdf_styles()

            # Build document elements
            elements = []

            # Title page
            workstream_name = workstream.get("name", "Workstream Report")
            elements.extend(
                (Paragraph(workstream_name, styles["DocTitle"]), Spacer(1, 12))
            )
            elements.append(
                HRFlowable(
                    width="100%",
                    thickness=2,
                    color=PDF_COLORS["secondary"],
                    spaceBefore=6,
                    spaceAfter=12,
                )
            )

            # Workstream description
            if workstream.get("description"):
                elements.append(Paragraph("Overview", styles["SectionHeading"]))
                elements.append(
                    Paragraph(workstream["description"], styles["BodyText"])
                )
                elements.append(Spacer(1, 12))

            # Summary statistics
            elements.append(Paragraph("Summary", styles["SectionHeading"]))

            if not cards:
                elements.append(
                    Paragraph(
                        "No cards currently match this workstream criteria.",
                        styles["BodyText"],
                    )
                )
            else:
                summary_text = (
                    f"This workstream contains <b>{len(cards)}</b> intelligence cards."
                )
                if len(cards) >= max_cards:
                    summary_text += f" (Showing first {max_cards})"
                elements.append(Paragraph(summary_text, styles["BodyText"]))
                elements.append(Spacer(1, 12))

                # Distribution charts
                if include_charts and cards:
                    # Pillar distribution
                    pillar_counts = {}
                    horizon_counts = {}
                    for card in cards:
                        pillar = card.pillar_name or card.pillar_id or "Unknown"
                        pillar_counts[pillar] = pillar_counts.get(pillar, 0) + 1

                        if card.horizon:
                            horizon_counts[card.horizon] = (
                                horizon_counts.get(card.horizon, 0) + 1
                            )

                    if pillar_chart_path := self.generate_pillar_distribution_chart(
                        pillar_counts
                    ):
                        temp_files.append(pillar_chart_path)
                        try:
                            img = RLImage(
                                pillar_chart_path,
                                width=PDF_CHART_WIDTH,
                                height=PDF_CHART_HEIGHT,
                            )
                            elements.append(img)
                            elements.append(Spacer(1, 12))
                        except Exception as e:
                            logger.warning(f"Failed to add pillar chart to PDF: {e}")

                    if horizon_chart_path := self.generate_horizon_distribution_chart(
                        horizon_counts
                    ):
                        temp_files.append(horizon_chart_path)
                        try:
                            img = RLImage(
                                horizon_chart_path, width=4.5 * inch, height=3 * inch
                            )
                            elements.append(img)
                            elements.append(Spacer(1, 12))
                        except Exception as e:
                            logger.warning(f"Failed to add horizon chart to PDF: {e}")

                # Cards table summary
                elements.append(PageBreak())
                elements.append(Paragraph("Cards Overview", styles["SectionHeading"]))

                table_data = [["Name", "Pillar", "Horizon", "Impact"]]
                for card in cards:
                    table_data.append(
                        [
                            card.name[:40] + ("..." if len(card.name) > 40 else ""),
                            card.pillar_name or card.pillar_id or "N/A",
                            card.horizon or "N/A",
                            self.format_score_display(card.impact_score),
                        ]
                    )

                table = Table(
                    table_data,
                    colWidths=[2.5 * inch, 1.5 * inch, 0.8 * inch, 0.8 * inch],
                )
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), PDF_COLORS["primary"]),
                            ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, 0), PDF_BODY_FONT_SIZE),
                            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 1), (-1, -1), PDF_SMALL_FONT_SIZE),
                            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                            (
                                "ROWBACKGROUNDS",
                                (0, 1),
                                (-1, -1),
                                [rl_colors.white, PDF_COLORS["light"]],
                            ),
                            ("GRID", (0, 0), (-1, -1), 0.5, PDF_COLORS["light"]),
                            ("BOX", (0, 0), (-1, -1), 1, PDF_COLORS["primary"]),
                            ("TOPPADDING", (0, 0), (-1, -1), 6),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                elements.append(table)

                # Individual card details (paginated)
                elements.append(PageBreak())
                elements.append(Paragraph("Card Details", styles["SectionHeading"]))
                elements.append(Spacer(1, 12))

                for i, card in enumerate(cards):
                    if i > 0:
                        elements.append(Spacer(1, 18))
                        elements.append(
                            HRFlowable(
                                width="80%",
                                thickness=0.5,
                                color=PDF_COLORS["light"],
                                spaceBefore=6,
                                spaceAfter=12,
                            )
                        )

                    # Card mini-header
                    elements.append(Paragraph(card.name, styles["SubsectionHeading"]))

                    # Badges row
                    badge_parts = []
                    if card.pillar_name or card.pillar_id:
                        badge_parts.append(
                            f"<b>Pillar:</b> {card.pillar_name or card.pillar_id}"
                        )
                    if card.horizon:
                        badge_parts.append(f"<b>Horizon:</b> {card.horizon}")
                    if card.stage_name or card.stage_id:
                        badge_parts.append(
                            f"<b>Stage:</b> {card.stage_name or card.stage_id}"
                        )
                    if badge_parts:
                        elements.append(
                            Paragraph(" | ".join(badge_parts), styles["SmallText"])
                        )
                        elements.append(Spacer(1, 6))

                    # Summary
                    if card.summary:
                        elements.append(Paragraph(card.summary, styles["BodyText"]))

                    # Key scores
                    key_scores = []
                    if card.impact_score is not None:
                        key_scores.append(f"Impact: {card.impact_score}")
                    if card.relevance_score is not None:
                        key_scores.append(f"Relevance: {card.relevance_score}")
                    if card.maturity_score is not None:
                        key_scores.append(f"Maturity: {card.maturity_score}")
                    if key_scores:
                        elements.append(
                            Paragraph(
                                "<i>Scores: " + " | ".join(key_scores) + "</i>",
                                styles["SmallText"],
                            )
                        )

            # Metadata footer
            elements.append(Spacer(1, 24))
            elements.append(
                HRFlowable(
                    width="100%",
                    thickness=1,
                    color=PDF_COLORS["light"],
                    spaceBefore=6,
                    spaceAfter=6,
                )
            )

            footer_text = (
                f"Export Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            )
            elements.append(Paragraph(footer_text, styles["SmallText"]))

            # Build PDF using professional builder with header/footer
            builder = ProfessionalPDFBuilder(
                filename=pdf_path,
                title=workstream_name,
                include_logo=True,
                include_ai_disclosure=True,
            )
            builder.build(elements)

            logger.info(
                f"Generated professional workstream PDF for: {workstream_name} with {len(cards)} cards"
            )
            return pdf_path

        except Exception as e:
            logger.error(f"Error generating workstream PDF {workstream_id}: {e}")
            raise

        finally:
            # Clean up chart temp files
            self.cleanup_temp_files(temp_files)

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
            result = await self.db.execute(select(Card).where(Card.id == card_id))
            card = result.scalar_one_or_none()
            if not card:
                return None

            # Convert ORM object to dict for CardExportData
            card_dict = {c.key: getattr(card, c.key) for c in Card.__table__.columns}
            return CardExportData(**card_dict)
        except Exception as e:
            logger.error(f"Error fetching card {card_id}: {e}")
            return None

    async def get_workstream_cards(
        self, workstream_id: str, max_cards: int = 50
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
            ws_result = await self.db.execute(
                select(Workstream).where(Workstream.id == workstream_id)
            )
            ws_obj = ws_result.scalar_one_or_none()

            if not ws_obj:
                return None, []

            # Convert ORM object to dict for downstream compatibility
            workstream = {
                c.key: getattr(ws_obj, c.key) for c in Workstream.__table__.columns
            }

            # Fetch associated cards via workstream_cards junction table
            wc_result = await self.db.execute(
                select(WorkstreamCard.card_id)
                .where(WorkstreamCard.workstream_id == workstream_id)
                .limit(max_cards)
            )
            card_ids = [row[0] for row in wc_result.all()]

            cards = []
            if card_ids:
                cards_result = await self.db.execute(
                    select(Card).where(Card.id.in_(card_ids))
                )
                for card_obj in cards_result.scalars().all():
                    card_dict = {
                        c.key: getattr(card_obj, c.key) for c in Card.__table__.columns
                    }
                    cards.append(CardExportData(**card_dict))

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

            logger.info(
                f"Generated CSV export for card {card_data.id}: {card_data.name}"
            )

            return csv_content

        except Exception as e:
            logger.error(f"Error generating CSV for card {card_data.id}: {e}")
            raise ValueError(f"Failed to generate CSV export: {e}") from e

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
            raise ValueError(f"Failed to generate CSV export: {e}") from e

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

    # ========================================================================
    # PowerPoint Export Methods
    # ========================================================================

    def _hex_to_rgb(self, hex_color: str) -> RGBColor:
        """
        Convert hex color string to RGBColor for PowerPoint.

        Args:
            hex_color: Hex color string (e.g., '#1E3A5F')

        Returns:
            RGBColor object for use with python-pptx
        """
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        return RGBColor(r, g, b)

    def _add_pptx_header(self, slide, include_logo: bool = True) -> None:
        """
        Add professional header to a PowerPoint slide.

        White background with City of Austin logo and GrantScope branding,
        matching the website daylight mode and PDF exports.

        Args:
            slide: PowerPoint slide object
            include_logo: Whether to include the City of Austin logo
        """
        # White header background
        header_bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), PPTX_SLIDE_WIDTH, Inches(1.1)
        )
        header_bg.fill.solid()
        header_bg.fill.fore_color.rgb = RGBColor(255, 255, 255)
        header_bg.line.fill.background()

        # Blue accent line below header
        accent_line = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0), Inches(1.08), PPTX_SLIDE_WIDTH, Inches(0.03)
        )
        accent_line.fill.solid()
        accent_line.fill.fore_color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["primary"])
        accent_line.line.fill.background()

        # City of Austin logo (if available)
        logo_right_edge = PPTX_MARGIN
        if include_logo and COA_LOGO_PATH and Path(COA_LOGO_PATH).exists():
            try:
                logo = slide.shapes.add_picture(
                    COA_LOGO_PATH, PPTX_MARGIN, Inches(0.25), height=Inches(0.6)
                )
                logo_right_edge = logo.left + logo.width + Inches(0.2)
            except Exception as e:
                logger.warning(f"Failed to add logo to PPTX slide: {e}")

        # FORESIGHT branding text - primary blue
        brand_box = slide.shapes.add_textbox(
            logo_right_edge, Inches(0.2), Inches(3), Inches(0.5)
        )
        brand_frame = brand_box.text_frame
        brand_para = brand_frame.paragraphs[0]
        brand_para.text = "FORESIGHT"
        brand_para.font.size = Pt(18)
        brand_para.font.bold = True
        brand_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["primary"])

        # Subtitle - gray
        subtitle_box = slide.shapes.add_textbox(
            logo_right_edge, Inches(0.55), Inches(3), Inches(0.4)
        )
        subtitle_frame = subtitle_box.text_frame
        subtitle_para = subtitle_frame.paragraphs[0]
        subtitle_para.text = "Strategic Intelligence Platform"
        subtitle_para.font.size = Pt(10)
        subtitle_para.font.color.rgb = RGBColor(128, 128, 128)

        # Date on right side - black
        date_box = slide.shapes.add_textbox(
            PPTX_SLIDE_WIDTH - Inches(2.5), Inches(0.4), Inches(2), Inches(0.4)
        )
        date_frame = date_box.text_frame
        date_para = date_frame.paragraphs[0]
        date_para.text = datetime.now(timezone.utc).strftime("%B %d, %Y")
        date_para.font.size = Pt(11)
        date_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["dark"])
        date_para.alignment = PP_ALIGN.RIGHT

    def _add_pptx_footer(self, slide, include_ai_disclosure: bool = True) -> None:
        """
        Add professional footer to a PowerPoint slide.

        Args:
            slide: PowerPoint slide object
            include_ai_disclosure: Whether to include AI technology disclosure
        """
        # Footer background
        footer_bg = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0),
            PPTX_SLIDE_HEIGHT - Inches(0.6),
            PPTX_SLIDE_WIDTH,
            Inches(0.6),
        )
        footer_bg.fill.solid()
        footer_bg.fill.fore_color.rgb = RGBColor(248, 249, 250)  # Light gray
        footer_bg.line.fill.background()

        # AI disclosure text
        if include_ai_disclosure:
            disclosure_box = slide.shapes.add_textbox(
                PPTX_MARGIN,
                PPTX_SLIDE_HEIGHT - Inches(0.5),
                PPTX_SLIDE_WIDTH - Inches(2),
                Inches(0.4),
            )
            disclosure_frame = disclosure_box.text_frame
            disclosure_para = disclosure_frame.paragraphs[0]
            disclosure_para.text = "AI Technologies: Anthropic Claude, OpenAI GPT-4o, GPT Researcher, Exa AI, Firecrawl, Tavily"
            disclosure_para.font.size = Pt(8)
            disclosure_para.font.color.rgb = RGBColor(100, 100, 100)

        # City of Austin notice
        notice_box = slide.shapes.add_textbox(
            PPTX_SLIDE_WIDTH - Inches(3),
            PPTX_SLIDE_HEIGHT - Inches(0.5),
            Inches(2.5),
            Inches(0.4),
        )
        notice_frame = notice_box.text_frame
        notice_para = notice_frame.paragraphs[0]
        notice_para.text = "City of Austin Internal Document"
        notice_para.font.size = Pt(8)
        notice_para.font.italic = True
        notice_para.font.color.rgb = RGBColor(128, 128, 128)
        notice_para.alignment = PP_ALIGN.RIGHT

    def _add_title_slide(
        self, prs: Presentation, title: str, subtitle: Optional[str] = None
    ) -> None:
        """
        Add a professional title slide to the presentation.

        Features white header with logo, clean typography, and AI disclosure footer.

        Args:
            prs: Presentation object
            title: Main title text
            subtitle: Optional subtitle text
        """
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)

        # White background
        background = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0),
            Inches(0),
            PPTX_SLIDE_WIDTH,
            PPTX_SLIDE_HEIGHT,
        )
        background.fill.solid()
        background.fill.fore_color.rgb = RGBColor(255, 255, 255)
        background.line.fill.background()

        # Add professional header
        self._add_pptx_header(slide)

        # Main title - centered, primary blue
        title_box = slide.shapes.add_textbox(
            PPTX_MARGIN, Inches(2.8), PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN), Inches(1.5)
        )
        title_frame = title_box.text_frame
        title_frame.word_wrap = True
        title_para = title_frame.paragraphs[0]
        title_para.text = title[:80]
        title_para.font.size = PPTX_TITLE_FONT_SIZE
        title_para.font.bold = True
        title_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["primary"])
        title_para.alignment = PP_ALIGN.CENTER

        # Subtitle if provided - gray
        if subtitle:
            subtitle_box = slide.shapes.add_textbox(
                PPTX_MARGIN,
                Inches(4.3),
                PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN),
                Inches(1),
            )
            subtitle_frame = subtitle_box.text_frame
            subtitle_frame.word_wrap = True
            subtitle_para = subtitle_frame.paragraphs[0]
            subtitle_para.text = subtitle[:150]
            subtitle_para.font.size = PPTX_SUBTITLE_FONT_SIZE
            subtitle_para.font.color.rgb = RGBColor(100, 100, 100)
            subtitle_para.alignment = PP_ALIGN.CENTER

        # Add professional footer with AI disclosure
        self._add_pptx_footer(slide)

    def _add_content_slide(
        self,
        prs: Presentation,
        title: str,
        content_items: List[Tuple[str, str]],
        chart_path: Optional[str] = None,
    ) -> None:
        """
        Add a content slide with text and optional chart.

        Uses professional white header with logo and footer with AI disclosure.

        Args:
            prs: Presentation object
            title: Slide title
            content_items: List of (label, value) tuples
            chart_path: Optional path to chart image to include
        """
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)

        # Add professional header and footer
        self._add_pptx_header(slide)
        self._add_pptx_footer(slide)

        # Slide title - below header, primary blue
        title_box = slide.shapes.add_textbox(
            PPTX_MARGIN, Inches(1.25), PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_para = title_frame.paragraphs[0]
        title_para.text = title[:60]
        title_para.font.size = Pt(28)
        title_para.font.bold = True
        title_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["primary"])

        # Determine layout based on whether chart is included
        if chart_path:
            content_width = Inches(6.5)
            chart_left = Inches(7.5)
        else:
            content_width = PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN)
            chart_left = None

        # Add content items - adjusted for header/footer
        content_top = Inches(1.95)
        content_box = slide.shapes.add_textbox(
            PPTX_MARGIN,
            content_top,
            content_width,
            Inches(4.5),  # Reduced height to account for footer
        )
        content_frame = content_box.text_frame
        content_frame.word_wrap = True

        for i, (label, value) in enumerate(content_items):
            para = (
                content_frame.paragraphs[0] if i == 0 else content_frame.add_paragraph()
            )
            para.space_before = Pt(8)
            para.space_after = Pt(4)

            # Add label in bold
            run_label = para.add_run()
            run_label.text = f"{label}: "
            run_label.font.size = PPTX_BODY_FONT_SIZE
            run_label.font.bold = True
            run_label.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["dark"])

            # Add value
            run_value = para.add_run()
            run_value.text = str(value) if value else "N/A"
            run_value.font.size = PPTX_BODY_FONT_SIZE
            run_value.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["dark"])

        # Add chart if provided - adjusted for header/footer
        if chart_path and Path(chart_path).exists():
            try:
                slide.shapes.add_picture(
                    chart_path,
                    chart_left,
                    Inches(2.0),
                    width=PPTX_CHART_WIDTH,
                    height=Inches(4.0),
                )
            except Exception as e:
                logger.warning(f"Failed to add chart to slide: {e}")

    def _add_scores_slide(
        self,
        prs: Presentation,
        card_data: CardExportData,
        chart_path: Optional[str] = None,
    ) -> None:
        """
        Add a slide showing all scores with optional chart.

        Uses professional white header and footer.

        Args:
            prs: Presentation object
            card_data: Card data with scores
            chart_path: Optional path to score chart image
        """
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)

        # Add professional header and footer
        self._add_pptx_header(slide)
        self._add_pptx_footer(slide)

        # Slide title - below header
        title_box = slide.shapes.add_textbox(
            PPTX_MARGIN, Inches(1.25), PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_para = title_frame.paragraphs[0]
        title_para.text = "Score Analysis"
        title_para.font.size = Pt(28)
        title_para.font.bold = True
        title_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["primary"])

        # Add chart if available - adjusted for header/footer
        if chart_path and Path(chart_path).exists():
            try:
                slide.shapes.add_picture(
                    chart_path,
                    Inches(0.5),
                    Inches(2.0),
                    width=Inches(5.5),
                    height=Inches(4.0),
                )
            except Exception as e:
                logger.warning(f"Failed to add score chart: {e}")

        # Add score details on the right side - adjusted positions
        scores = card_data.get_all_scores()
        scores_box = slide.shapes.add_textbox(
            Inches(6.5), Inches(2.0), Inches(5.5), Inches(4.0)
        )
        scores_frame = scores_box.text_frame
        scores_frame.word_wrap = True

        for i, (score_name, score_value) in enumerate(scores.items()):
            para = (
                scores_frame.paragraphs[0] if i == 0 else scores_frame.add_paragraph()
            )
            para.space_before = Pt(12)
            para.space_after = Pt(4)

            # Score name
            run_name = para.add_run()
            run_name.text = f"{score_name}: "
            run_name.font.size = Pt(20)
            run_name.font.bold = True
            run_name.font.color.rgb = self._hex_to_rgb(
                SCORE_COLORS.get(score_name, GRANTSCOPE_COLORS["dark"])
            )

            # Score value
            run_value = para.add_run()
            run_value.text = str(score_value) if score_value is not None else "N/A"
            run_value.font.size = Pt(20)
            run_value.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["dark"])

    def _add_description_slide(
        self, prs: Presentation, title: str, description: Optional[str]
    ) -> None:
        """
        Add a slide for long-form description text.

        Uses professional white header and footer.

        Args:
            prs: Presentation object
            title: Slide title
            description: Description text (will be truncated if too long)
        """
        if not description:
            return

        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)

        # Add professional header and footer
        self._add_pptx_header(slide)
        self._add_pptx_footer(slide)

        # Slide title - below header
        title_box = slide.shapes.add_textbox(
            PPTX_MARGIN, Inches(1.25), PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_para = title_frame.paragraphs[0]
        title_para.text = title
        title_para.font.size = Pt(28)
        title_para.font.bold = True
        title_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["primary"])

        # Add description text - truncate if too long for slide
        max_chars = 1800  # Adjusted for header/footer space
        display_text = description[:max_chars]
        if len(description) > max_chars:
            display_text += "..."

        desc_box = slide.shapes.add_textbox(
            PPTX_MARGIN, Inches(1.95), PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN), Inches(4.5)
        )
        desc_frame = desc_box.text_frame
        desc_frame.word_wrap = True
        desc_para = desc_frame.paragraphs[0]
        desc_para.text = display_text
        desc_para.font.size = PPTX_BODY_FONT_SIZE
        desc_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["dark"])
        desc_para.line_spacing = 1.3

    async def generate_pptx(
        self,
        card_data: CardExportData,
        include_charts: bool = True,
        include_description: bool = True,
    ) -> str:
        """
        Generate a PowerPoint presentation for an individual card.

        Creates a multi-slide presentation with:
        - Title slide with card name and summary
        - Overview slide with key metadata
        - Scores slide with visualization
        - Description slide (if enabled)

        Args:
            card_data: Card data to export
            include_charts: Whether to include score charts
            include_description: Whether to include description slide

        Returns:
            Path to the generated PowerPoint file

        Raises:
            Exception: If PowerPoint generation fails
        """
        temp_files_to_cleanup = []

        try:
            logger.info(f"Generating PowerPoint for card: {card_data.name}")

            # Create presentation
            prs = Presentation()
            prs.slide_width = PPTX_SLIDE_WIDTH
            prs.slide_height = PPTX_SLIDE_HEIGHT

            # 1. Title slide
            self._add_title_slide(prs, title=card_data.name, subtitle=card_data.summary)

            # 2. Overview slide with metadata
            overview_items = [
                ("Pillar", card_data.pillar_name or card_data.pillar_id),
                ("Goal", card_data.goal_name or card_data.goal_id),
                ("Anchor", card_data.anchor_name or card_data.anchor_id),
                ("Stage", card_data.stage_name or card_data.stage_id),
                ("Horizon", card_data.horizon),
                ("Status", card_data.status),
            ]
            # Filter out items with no value
            overview_items = [(k, v) for k, v in overview_items if v]

            self._add_content_slide(
                prs, title="Card Overview", content_items=overview_items
            )

            # 3. Scores slide with chart
            chart_path = None
            if include_charts:
                chart_path = self.generate_score_chart(card_data, chart_type="radar")
                if chart_path:
                    temp_files_to_cleanup.append(chart_path)

            self._add_scores_slide(prs, card_data, chart_path)

            # 4. Description slide (optional)
            if include_description and card_data.description:
                self._add_description_slide(
                    prs, title="Full Description", description=card_data.description
                )

            # Save presentation to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".pptx", delete=False, prefix="grantscope_card_"
            )
            prs.save(temp_file.name)

            logger.info(f"PowerPoint generated successfully: {temp_file.name}")
            return temp_file.name

        except Exception as e:
            logger.error(f"Error generating PowerPoint: {e}")
            raise

        finally:
            # Clean up chart temp files
            self.cleanup_temp_files(temp_files_to_cleanup)

    async def generate_workstream_pptx(
        self,
        workstream: Dict[str, Any],
        cards: List[CardExportData],
        include_charts: bool = True,
        include_card_details: bool = True,
    ) -> str:
        """
        Generate a PowerPoint presentation for a workstream report.

        Creates a comprehensive presentation with:
        - Title slide with workstream name
        - Summary slide with statistics
        - Distribution charts (pillar, horizon)
        - Individual card slides (if enabled)

        Args:
            workstream: Workstream metadata dict
            cards: List of cards in the workstream
            include_charts: Whether to include distribution charts
            include_card_details: Whether to include individual card slides

        Returns:
            Path to the generated PowerPoint file

        Raises:
            Exception: If PowerPoint generation fails
        """
        temp_files_to_cleanup = []

        try:
            workstream_name = workstream.get("name", "Workstream Report")
            logger.info(f"Generating workstream PowerPoint: {workstream_name}")

            # Create presentation
            prs = Presentation()
            prs.slide_width = PPTX_SLIDE_WIDTH
            prs.slide_height = PPTX_SLIDE_HEIGHT

            # 1. Title slide
            self._add_title_slide(
                prs,
                title=workstream_name,
                subtitle=f"Intelligence Report • {len(cards)} Cards",
            )

            # 2. Summary slide
            summary_items = [
                ("Total Cards", str(len(cards))),
                ("Description", workstream.get("description", "N/A")),
            ]

            # Calculate pillar distribution
            pillar_counts: Dict[str, int] = {}
            horizon_counts: Dict[str, int] = {}
            for card in cards:
                pillar = card.pillar_name or card.pillar_id or "Unknown"
                pillar_counts[pillar] = pillar_counts.get(pillar, 0) + 1

                horizon = card.horizon or "Unknown"
                horizon_counts[horizon] = horizon_counts.get(horizon, 0) + 1

            if pillar_counts:
                pillar_summary = ", ".join(
                    f"{k}: {v}" for k, v in pillar_counts.items()
                )
                summary_items.append(("Pillars", pillar_summary))

            if horizon_counts:
                horizon_summary = ", ".join(
                    f"{k}: {v}" for k, v in horizon_counts.items()
                )
                summary_items.append(("Horizons", horizon_summary))

            self._add_content_slide(
                prs, title="Workstream Summary", content_items=summary_items
            )

            # 3. Distribution charts slide
            if include_charts and cards:
                # Generate pillar distribution chart
                pillar_chart_path = None
                if pillar_counts:
                    pillar_chart_path = self.generate_pillar_distribution_chart(
                        pillar_counts
                    )
                    if pillar_chart_path:
                        temp_files_to_cleanup.append(pillar_chart_path)

                # Generate horizon distribution chart
                horizon_chart_path = None
                if horizon_counts:
                    horizon_chart_path = self.generate_horizon_distribution_chart(
                        horizon_counts
                    )
                    if horizon_chart_path:
                        temp_files_to_cleanup.append(horizon_chart_path)

                # Add distribution slide with both charts
                if pillar_chart_path or horizon_chart_path:
                    slide_layout = prs.slide_layouts[6]
                    slide = prs.slides.add_slide(slide_layout)

                    # Add professional header and footer
                    self._add_pptx_header(slide)
                    self._add_pptx_footer(slide)

                    # Slide title - below header
                    title_box = slide.shapes.add_textbox(
                        PPTX_MARGIN,
                        Inches(1.25),
                        PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN),
                        Inches(0.6),
                    )
                    title_frame = title_box.text_frame
                    title_para = title_frame.paragraphs[0]
                    title_para.text = "Distribution Analysis"
                    title_para.font.size = Pt(28)
                    title_para.font.bold = True
                    title_para.font.color.rgb = self._hex_to_rgb(
                        GRANTSCOPE_COLORS["primary"]
                    )

                # Add pillar chart on left - adjusted for header/footer
                if pillar_chart_path and Path(pillar_chart_path).exists():
                    try:
                        slide.shapes.add_picture(
                            pillar_chart_path,
                            Inches(0.3),
                            Inches(2.0),
                            width=Inches(5.5),
                            height=Inches(4.0),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to add pillar chart: {e}")

                # Add horizon chart on right - adjusted for header/footer
                if horizon_chart_path and Path(horizon_chart_path).exists():
                    try:
                        slide.shapes.add_picture(
                            horizon_chart_path,
                            Inches(6.5),
                            Inches(2.0),
                            width=Inches(5.5),
                            height=Inches(4.0),
                        )
                    except Exception as e:
                        logger.warning(f"Failed to add horizon chart: {e}")

            if include_card_details:
                if cards:
                    # Add a slide for each card (up to 50)
                    for card in cards[:50]:
                        card_items = [
                            ("Summary", card.summary),
                            ("Pillar", card.pillar_name or card.pillar_id),
                            ("Horizon", card.horizon),
                            ("Stage", card.stage_name or card.stage_id),
                        ]
                        # Add scores
                        scores = card.get_all_scores()
                        if valid_scores := {
                            k: v for k, v in scores.items() if v is not None
                        }:
                            scores_text = ", ".join(
                                f"{k}: {v}" for k, v in valid_scores.items()
                            )
                            card_items.append(("Scores", scores_text))

                        # Filter out empty items
                        card_items = [(k, v) for k, v in card_items if v]

                        self._add_content_slide(
                            prs, title=card.name[:50], content_items=card_items
                        )

                else:
                    slide_layout = prs.slide_layouts[6]
                    slide = prs.slides.add_slide(slide_layout)

                    # Add professional header and footer
                    self._add_pptx_header(slide)
                    self._add_pptx_footer(slide)

                    msg_box = slide.shapes.add_textbox(
                        Inches(2), Inches(3.5), Inches(9), Inches(2)
                    )
                    msg_frame = msg_box.text_frame
                    msg_para = msg_frame.paragraphs[0]
                    msg_para.text = "No cards currently match this workstream criteria"
                    msg_para.font.size = PPTX_SUBTITLE_FONT_SIZE
                    msg_para.font.color.rgb = self._hex_to_rgb(
                        GRANTSCOPE_COLORS["dark"]
                    )
                    msg_para.alignment = PP_ALIGN.CENTER
            # Save presentation to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".pptx", delete=False, prefix="grantscope_workstream_"
            )
            prs.save(temp_file.name)

            logger.info(f"Workstream PowerPoint generated: {temp_file.name}")
            return temp_file.name

        except Exception as e:
            logger.error(f"Error generating workstream PowerPoint: {e}")
            raise

        finally:
            # Clean up chart temp files
            self.cleanup_temp_files(temp_files_to_cleanup)

    # ========================================================================
    # Executive Brief Export Methods
    # ========================================================================

    async def generate_brief_pdf(
        self,
        brief_title: str,
        card_name: str,
        executive_summary: str,
        content_markdown: str,
        generated_at: Optional[datetime] = None,
        version: Optional[int] = None,
    ) -> str:
        """
        Generate a PDF export for an executive brief.

        Args:
            brief_title: Title for the brief (usually card name)
            card_name: Name of the card this brief is for
            executive_summary: Executive summary text
            content_markdown: Full brief content in markdown format
            generated_at: When the brief was generated
            version: Version number of the brief

        Returns:
            Path to the generated PDF file

        Raises:
            Exception: If PDF generation fails
        """
        try:
            # Create temp file for PDF
            pdf_file = tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False, prefix="grantscope_brief_"
            )
            pdf_path = pdf_file.name
            pdf_file.close()

            # Create PDF document
            doc = SimpleDocTemplate(
                pdf_path,
                pagesize=PDF_PAGE_SIZE,
                rightMargin=PDF_MARGIN,
                leftMargin=PDF_MARGIN,
                topMargin=PDF_MARGIN,
                bottomMargin=PDF_MARGIN,
            )

            # Get styles
            styles = self._get_pdf_styles()

            # Build document elements
            elements = []

            # Title
            title_text = f"Executive Brief: {brief_title}"
            if version and version > 1:
                title_text += f" (v{version})"
            elements.extend(
                (
                    Paragraph(title_text, styles["Title"]),
                    Spacer(1, 6),
                    HRFlowable(
                        width="100%",
                        thickness=2,
                        color=PDF_COLORS["primary"],
                        spaceBefore=6,
                        spaceAfter=12,
                    ),
                )
            )
            # Metadata
            meta_parts = [f"Card: {card_name}"]
            if generated_at:
                meta_parts.append(
                    f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}"
                )
            if version:
                meta_parts.append(f"Version: {version}")
            elements.extend(
                (
                    Paragraph(" | ".join(meta_parts), styles["Small"]),
                    Spacer(1, 12),
                    Paragraph("Executive Summary", styles["Heading1"]),
                    Paragraph(
                        executive_summary or "No summary available.",
                        styles["Body"],
                    ),
                    Spacer(1, 18),
                    Paragraph("Full Brief", styles["Heading1"]),
                    Spacer(1, 6),
                )
            )
            # Parse markdown content into paragraphs
            # Simple markdown parsing - split by double newlines for paragraphs
            if content_markdown:
                paragraphs = content_markdown.split("\n\n")
                for para_text in paragraphs:
                    para_text = para_text.strip()
                    if not para_text:
                        continue

                    # Handle headers
                    if para_text.startswith("# "):
                        elements.append(Paragraph(para_text[2:], styles["Heading1"]))
                    elif para_text.startswith("## "):
                        elements.append(Paragraph(para_text[3:], styles["Heading2"]))
                    elif para_text.startswith("### "):
                        # Create a heading3 style on the fly
                        heading3_style = ParagraphStyle(
                            "Heading3",
                            parent=styles["Body"],
                            fontSize=PDF_BODY_FONT_SIZE,
                            fontName="Helvetica-Bold",
                            spaceBefore=10,
                            spaceAfter=4,
                        )
                        elements.append(Paragraph(para_text[4:], heading3_style))
                    elif para_text.startswith("- ") or para_text.startswith("* "):
                        # Bullet list items
                        bullet_style = ParagraphStyle(
                            "Bullet",
                            parent=styles["Body"],
                            leftIndent=20,
                            firstLineIndent=-10,
                            spaceBefore=2,
                            spaceAfter=2,
                        )
                        # Handle multi-line bullets
                        lines = para_text.split("\n")
                        for line in lines:
                            line = line.strip()
                            if line.startswith("- ") or line.startswith("* "):
                                elements.append(
                                    Paragraph(f"• {line[2:]}", bullet_style)
                                )
                            elif line:
                                elements.append(Paragraph(line, styles["Body"]))
                    else:
                        # Regular paragraph - handle inline markdown
                        # Convert **bold** to <b>bold</b>
                        import re

                        formatted = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", para_text)
                        # Convert *italic* to <i>italic</i>
                        formatted = re.sub(r"\*(.+?)\*", r"<i>\1</i>", formatted)
                        # Handle line breaks within paragraph
                        formatted = formatted.replace("\n", "<br/>")
                        elements.append(Paragraph(formatted, styles["Body"]))

                    elements.append(Spacer(1, 4))
            else:
                elements.append(Paragraph("No content available.", styles["Body"]))

            elements.extend(
                (
                    Spacer(1, 24),
                    HRFlowable(
                        width="100%",
                        thickness=1,
                        color=PDF_COLORS["light"],
                        spaceBefore=6,
                        spaceAfter=6,
                    ),
                )
            )
            footer_text = (
                f"Export Date: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            )
            elements.extend(
                (
                    Paragraph(footer_text, styles["Small"]),
                    Paragraph(
                        "Generated by GrantScope2 Intelligence Platform",
                        styles["Small"],
                    ),
                )
            )
            # Build PDF
            doc.build(elements)

            logger.info(f"Generated brief PDF export: {brief_title}")
            return pdf_path

        except Exception as e:
            logger.error(f"Error generating brief PDF: {e}")
            raise

    async def generate_professional_brief_pdf(
        self,
        brief_title: str,
        card_name: str,
        executive_summary: str,
        content_markdown: str,
        generated_at: Optional[datetime] = None,
        version: Optional[int] = None,
        classification: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Generate a professional PDF export for an executive brief.

        This version includes:
        - City of Austin logo in header
        - GrantScope2 Strategic Intelligence Platform branding
        - Professional header/footer on every page
        - Full AI technology disclosure
        - Colored classification badges with appendix reference
        - Robust markdown parsing for AI-generated content

        Designed for senior city leadership distribution.

        Args:
            brief_title: Title for the brief
            card_name: Name of the card this brief is for
            executive_summary: Executive summary text
            content_markdown: Full brief content in markdown format
            generated_at: When the brief was generated
            version: Version number of the brief
            classification: Optional dict with pillar, horizon, stage info

        Returns:
            Path to the generated PDF file

        Raises:
            Exception: If PDF generation fails
        """
        try:
            # Create temp file for PDF
            pdf_file = tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False, prefix="grantscope_executive_brief_"
            )
            pdf_path = pdf_file.name
            pdf_file.close()

            # Get professional styles
            styles = get_professional_pdf_styles()

            # Initialize markdown parser
            md_parser = MarkdownToPDFParser(styles)

            # Build document elements
            elements = [Paragraph(brief_title, styles["DocTitle"])]

            # Classification badges (colored, with appendix reference)
            if classification:
                badge_elements = create_classification_badges(classification, styles)
                elements.extend(badge_elements)

            elements.append(Spacer(1, 8))

            # Decorative line
            elements.append(
                HRFlowable(
                    width="100%",
                    thickness=2,
                    color=PDF_COLORS["secondary"],
                    spaceBefore=4,
                    spaceAfter=16,
                )
            )

            # Executive Summary Section
            elements.append(Paragraph("Executive Summary", styles["SectionHeading"]))

            if executive_summary:
                # Parse executive summary through the robust parser too
                summary_clean = md_parser.clean_text(executive_summary)
                summary_formatted = md_parser.convert_inline_formatting(summary_clean)
                # Replace newlines with line breaks for the summary
                summary_formatted = summary_formatted.replace("\n", "<br/>")
                elements.append(
                    Paragraph(summary_formatted, styles["ExecutiveSummary"])
                )
            else:
                elements.append(Paragraph("No summary available.", styles["BodyText"]))

            elements.append(Spacer(1, 16))

            # Main Content Section
            elements.append(
                Paragraph("Strategic Intelligence Report", styles["SectionHeading"])
            )
            elements.append(Spacer(1, 8))

            # Parse and render markdown content using robust parser
            if content_markdown:
                content_elements = md_parser.parse_to_elements(content_markdown)
                elements.extend(content_elements)
            else:
                elements.append(Paragraph("No content available.", styles["BodyText"]))

            # Add metadata section at end
            elements.append(Spacer(1, 20))
            elements.append(
                HRFlowable(
                    width="100%",
                    thickness=1,
                    color=PDF_COLORS["light"],
                    spaceBefore=8,
                    spaceAfter=8,
                )
            )

            # Document metadata
            meta_items = []
            if generated_at:
                meta_items.append(
                    f"Generated: {generated_at.strftime('%B %d, %Y at %I:%M %p UTC')}"
                )
            if version:
                meta_items.append(f"Version: {version}")
            meta_items.append(f"Card: {card_name}")

            elements.extend(Paragraph(item, styles["SmallText"]) for item in meta_items)
            # Add classification appendix if we have classification data
            if classification:
                appendix_elements = create_classification_appendix(styles)
                elements.extend(appendix_elements)

            # Build PDF using professional builder with header/footer
            builder = ProfessionalPDFBuilder(
                filename=pdf_path,
                title=brief_title,
                include_logo=True,
                include_ai_disclosure=True,
            )
            builder.build(elements)

            logger.info(f"Generated professional brief PDF: {brief_title}")
            return pdf_path

        except Exception as e:
            logger.error(f"Error generating professional brief PDF: {e}")
            raise

    async def generate_chat_response_pdf(
        self,
        title: str,
        question: str,
        response_content: str,
        citations: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        scope: Optional[str] = None,
        scope_context: Optional[str] = None,
    ) -> str:
        """
        Generate a professional PDF export for a chat response.

        Produces a mayor-ready document matching the executive brief style,
        using the existing ProfessionalPDFBuilder for header/footer and
        MarkdownToPDFParser for the response content.

        Args:
            title: Document title (conversation title or fallback)
            question: The user's question
            response_content: The assistant's markdown response
            citations: Optional list of citation dicts with title, url, excerpt
            metadata: Optional metadata dict (source_count, etc.)
            scope: Optional scope type ("signal", "workstream", or "global")
            scope_context: Optional name of the signal/workstream if scoped

        Returns:
            Path to the generated PDF file

        Raises:
            Exception: If PDF generation fails
        """
        try:
            # Create temp file for PDF
            pdf_file = tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False, prefix="grantscope_chat_"
            )
            pdf_path = pdf_file.name
            pdf_file.close()

            # Get professional styles
            styles = get_professional_pdf_styles()

            # Initialize markdown parser
            md_parser = MarkdownToPDFParser(styles)

            # Build document elements
            elements = []

            # --- Title area (top of first page, no separate title page) ---
            elements.append(Paragraph(title, styles["DocTitle"]))
            elements.append(Paragraph("Intelligence Response", styles["DocSubtitle"]))

            # Current date
            date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
            elements.append(Paragraph(date_str, styles["MetadataText"]))

            # Scope context if scoped
            if scope and scope_context:
                scope_label = (
                    "Signal"
                    if scope == "signal"
                    else ("Workstream" if scope == "workstream" else "Scope")
                )
                elements.append(
                    Paragraph(
                        f"<b>{scope_label}:</b> {md_parser.escape_xml(scope_context)}",
                        styles["MetadataText"],
                    )
                )

            elements.append(Spacer(1, 8))

            # --- Horizontal rule separator ---
            elements.append(
                HRFlowable(
                    width="100%",
                    thickness=2,
                    color=PDF_COLORS["secondary"],
                    spaceBefore=4,
                    spaceAfter=16,
                )
            )

            # --- Question box (light blue callout) ---
            light_blue_bg = hex_to_rl_color(COA_BRAND_COLORS["light_blue"])
            question_box_style = ParagraphStyle(
                "QuestionBody",
                parent=styles["BodyText"],
                backColor=light_blue_bg,
                borderPadding=(10, 10, 10, 10),
                spaceBefore=4,
                spaceAfter=4,
            )
            question_label_style = ParagraphStyle(
                "QuestionLabel",
                parent=styles["BodyText"],
                fontSize=12,
                fontName="Helvetica-Bold",
                textColor=PDF_COLORS["primary"],
                backColor=light_blue_bg,
                borderPadding=(10, 10, 2, 10),
                spaceBefore=0,
                spaceAfter=0,
            )

            question_escaped = (
                md_parser.escape_xml(question) if question else "No question recorded."
            )
            elements.append(
                KeepTogether(
                    [
                        Paragraph("Question", question_label_style),
                        Paragraph(question_escaped, question_box_style),
                    ]
                )
            )

            elements.append(Spacer(1, 16))

            # --- Response / Analysis section ---
            elements.append(Paragraph("Analysis", styles["SectionHeading"]))
            elements.append(Spacer(1, 8))

            if response_content:
                content_elements = md_parser.parse_to_elements(response_content)
                elements.extend(content_elements)
            else:
                elements.append(
                    Paragraph("No response content available.", styles["BodyText"])
                )

            # --- Sources / Citations section ---
            if citations:
                elements.append(Spacer(1, 16))
                elements.append(
                    Paragraph("Sources &amp; References", styles["SectionHeading"])
                )
                elements.append(Spacer(1, 6))

                for idx, cite in enumerate(citations, 1):
                    cite_title = md_parser.escape_xml(
                        cite.get("title", "Untitled Source")
                    )
                    cite_url = md_parser.escape_xml(cite.get("url", ""))
                    cite_excerpt = md_parser.escape_xml(cite.get("excerpt", ""))

                    # Numbered citation entry
                    citation_parts = [f"<b>{idx}.</b> <b>{cite_title}</b>"]
                    if cite_url:
                        citation_parts.append(
                            f'<font size="9" color="gray">{cite_url}</font>'
                        )
                    elements.append(
                        Paragraph("<br/>".join(citation_parts), styles["NumberedItem"])
                    )

                    if cite_excerpt:
                        excerpt_style = ParagraphStyle(
                            f"Excerpt_{idx}",
                            parent=styles["SmallText"],
                            leftIndent=25,
                            spaceBefore=1,
                            spaceAfter=6,
                            textColor=PDF_COLORS["dark"],
                            fontSize=9,
                            leading=12,
                        )
                        # Truncate long excerpts
                        if len(cite_excerpt) > 300:
                            cite_excerpt = cite_excerpt[:297] + "..."
                        elements.append(
                            Paragraph(f"<i>{cite_excerpt}</i>", excerpt_style)
                        )

            # --- Metadata footer ---
            if metadata:
                elements.append(Spacer(1, 20))
                elements.append(
                    HRFlowable(
                        width="100%",
                        thickness=1,
                        color=PDF_COLORS["light"],
                        spaceBefore=8,
                        spaceAfter=8,
                    )
                )

                meta_parts = []
                if metadata.get("source_count"):
                    meta_parts.append(f"{metadata['source_count']} sources")
                if metadata.get("signal_count"):
                    meta_parts.append(f"{metadata['signal_count']} signals")
                if metadata.get("model"):
                    meta_parts.append(f"Model: {metadata['model']}")

                if meta_parts:
                    meta_text = "Based on " + " across ".join(meta_parts)
                    elements.append(Paragraph(meta_text, styles["SmallText"]))

            # Build PDF using professional builder (header/footer/logo/disclosure)
            builder = ProfessionalPDFBuilder(
                filename=pdf_path,
                title=title,
                include_logo=True,
                include_ai_disclosure=True,
            )
            builder.build(elements)

            logger.info(f"Generated chat response PDF: {title}")
            return pdf_path

        except Exception as e:
            logger.error(f"Error generating chat response PDF: {e}")
            raise

    async def generate_proposal_pdf(
        self,
        proposal_data: Dict[str, Any],
        grant_context: Optional[Dict[str, Any]] = None,
        plan_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a professional PDF export for a grant proposal.

        Produces a complete grant application readiness package including
        all six proposal sections, optional grant overview, budget table,
        and requirements checklist.

        Args:
            proposal_data: Proposal dict with title, sections, etc.
            grant_context: Optional grant context dict (name, grantor, deadline, etc.)
            plan_data: Optional plan dict with budget, timeline, etc.

        Returns:
            Path to the generated PDF file

        Raises:
            Exception: If PDF generation fails
        """
        try:
            # Create temp file for PDF
            pdf_file = tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False, prefix="grantscope_proposal_"
            )
            pdf_path = pdf_file.name
            pdf_file.close()

            # Get professional styles
            styles = get_professional_pdf_styles()

            # Initialize markdown parser
            md_parser = MarkdownToPDFParser(styles)

            # Build document elements
            elements = []

            # --- Cover area ---
            title = proposal_data.get("title", "Grant Application Package")
            elements.append(Paragraph(md_parser.escape_xml(title), styles["DocTitle"]))
            elements.append(
                Paragraph("Grant Application Readiness Package", styles["DocSubtitle"])
            )

            # Current date
            date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
            elements.append(Paragraph(date_str, styles["MetadataText"]))

            elements.append(Spacer(1, 8))

            # --- Horizontal rule separator ---
            elements.append(
                HRFlowable(
                    width="100%",
                    thickness=2,
                    color=PDF_COLORS["secondary"],
                    spaceBefore=4,
                    spaceAfter=16,
                )
            )

            # --- Grant Overview section (if grant_context provided) ---
            if grant_context:
                elements.append(Paragraph("Grant Overview", styles["SectionHeading"]))
                elements.append(Spacer(1, 6))

                overview_items = []

                grant_name = grant_context.get("grant_name")
                if grant_name:
                    overview_items.append(
                        f"<b>Grant Name:</b> {md_parser.escape_xml(str(grant_name))}"
                    )

                grantor = grant_context.get("grantor")
                if grantor:
                    overview_items.append(
                        f"<b>Grantor:</b> {md_parser.escape_xml(str(grantor))}"
                    )

                deadline = grant_context.get("deadline")
                if deadline:
                    overview_items.append(
                        f"<b>Deadline:</b> {md_parser.escape_xml(str(deadline))}"
                    )

                # Funding range
                funding_min = grant_context.get("funding_amount_min")
                funding_max = grant_context.get("funding_amount_max")
                if funding_min and funding_max:
                    overview_items.append(
                        f"<b>Funding Range:</b> ${funding_min:,.0f} - ${funding_max:,.0f}"
                    )
                elif funding_max:
                    overview_items.append(
                        f"<b>Funding Amount:</b> Up to ${funding_max:,.0f}"
                    )
                elif funding_min:
                    overview_items.append(
                        f"<b>Funding Amount:</b> From ${funding_min:,.0f}"
                    )

                cfda_number = grant_context.get("cfda_number")
                if cfda_number:
                    overview_items.append(
                        f"<b>CFDA Number:</b> {md_parser.escape_xml(str(cfda_number))}"
                    )

                for item in overview_items:
                    elements.append(Paragraph(item, styles["BodyText"]))

                elements.append(Spacer(1, 12))

            # --- Proposal sections ---
            section_order = [
                ("executive_summary", "Executive Summary"),
                ("needs_statement", "Needs Statement"),
                ("project_description", "Project Description"),
                ("budget_narrative", "Budget Narrative"),
                ("timeline", "Timeline"),
                ("evaluation_plan", "Evaluation Plan"),
            ]

            sections = proposal_data.get("sections", {})
            for section_key, section_label in section_order:
                section_data = sections.get(section_key, {})
                if not section_data:
                    continue

                # Get content: prefer user content, fall back to ai_draft
                content = ""
                if isinstance(section_data, dict):
                    content = section_data.get("content", "") or section_data.get(
                        "ai_draft", ""
                    )
                elif isinstance(section_data, str):
                    content = section_data

                if not content:
                    continue

                elements.append(
                    Paragraph(
                        md_parser.escape_xml(section_label), styles["SectionHeading"]
                    )
                )
                elements.append(Spacer(1, 6))

                # Parse markdown content into PDF elements
                content_elements = md_parser.parse_to_elements(content)
                elements.extend(content_elements)

                elements.append(Spacer(1, 8))

            # --- Budget table (if plan_data has budget) ---
            if plan_data:
                budget = plan_data.get("budget")
                if budget and isinstance(budget, list) and len(budget) > 0:
                    elements.append(
                        Paragraph("Budget Summary", styles["SectionHeading"])
                    )
                    elements.append(Spacer(1, 6))

                    # Build table data
                    table_data = [["Category", "Amount", "Justification"]]
                    total_amount = 0

                    for entry in budget:
                        if not isinstance(entry, dict):
                            continue
                        category = md_parser.escape_xml(str(entry.get("category", "")))
                        amount = entry.get("amount", 0)
                        justification = md_parser.escape_xml(
                            str(entry.get("justification", ""))
                        )

                        # Truncate long justifications for table readability
                        if len(justification) > 80:
                            justification = justification[:77] + "..."

                        amount_val = float(amount) if amount else 0
                        total_amount += amount_val

                        table_data.append(
                            [
                                Paragraph(category, styles["SmallText"]),
                                Paragraph(f"${amount_val:,.0f}", styles["SmallText"]),
                                Paragraph(justification, styles["SmallText"]),
                            ]
                        )

                    # Add total row
                    table_data.append(
                        [
                            Paragraph("<b>Total</b>", styles["SmallText"]),
                            Paragraph(
                                f"<b>${total_amount:,.0f}</b>", styles["SmallText"]
                            ),
                            Paragraph("", styles["SmallText"]),
                        ]
                    )

                    # Create table
                    col_widths = [1.8 * inch, 1.2 * inch, 4.0 * inch]
                    budget_table = Table(table_data, colWidths=col_widths)
                    budget_table.setStyle(
                        TableStyle(
                            [
                                # Header row styling
                                (
                                    "BACKGROUND",
                                    (0, 0),
                                    (-1, 0),
                                    PDF_COLORS["primary"],
                                ),
                                ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
                                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                ("FONTSIZE", (0, 0), (-1, 0), 9),
                                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                                # Body styling
                                ("FONTSIZE", (0, 1), (-1, -1), 9),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                # Grid
                                (
                                    "GRID",
                                    (0, 0),
                                    (-1, -1),
                                    0.5,
                                    PDF_COLORS["light"],
                                ),
                                # Alternating row colors
                                *[
                                    (
                                        "BACKGROUND",
                                        (0, i),
                                        (-1, i),
                                        hex_to_rl_color("#F8F9FA"),
                                    )
                                    for i in range(2, len(table_data), 2)
                                ],
                                # Total row styling
                                (
                                    "BACKGROUND",
                                    (0, -1),
                                    (-1, -1),
                                    hex_to_rl_color("#E8EEF4"),
                                ),
                                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                                # Padding
                                ("TOPPADDING", (0, 0), (-1, -1), 6),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                            ]
                        )
                    )
                    elements.append(budget_table)
                    elements.append(Spacer(1, 12))

            # --- Requirements checklist (if grant_context has requirements) ---
            if grant_context:
                requirements = grant_context.get("requirements")
                if (
                    requirements
                    and isinstance(requirements, list)
                    and len(requirements) > 0
                ):
                    elements.append(
                        Paragraph(
                            "Grant Requirements Checklist", styles["SectionHeading"]
                        )
                    )
                    elements.append(Spacer(1, 6))

                    for req in requirements:
                        if isinstance(req, dict):
                            desc = md_parser.escape_xml(str(req.get("description", "")))
                            category = md_parser.escape_xml(
                                str(req.get("category", ""))
                            )
                            is_mandatory = req.get("is_mandatory", False)
                            mandatory_tag = " <b>[Required]</b>" if is_mandatory else ""
                            bullet_text = desc
                            if category:
                                bullet_text = f"<b>{category}:</b> {desc}"
                            bullet_text += mandatory_tag
                        elif isinstance(req, str):
                            bullet_text = md_parser.escape_xml(req)
                        else:
                            continue

                        elements.append(
                            Paragraph(f"\u2022 {bullet_text}", styles["BulletText"])
                        )

                    elements.append(Spacer(1, 12))

            # Build PDF using professional builder (header/footer/logo/disclosure)
            builder = ProfessionalPDFBuilder(
                filename=pdf_path,
                title=title,
                include_logo=True,
                include_ai_disclosure=True,
            )
            builder.build(elements)

            logger.info(f"Generated proposal PDF: {title}")
            return pdf_path

        except Exception as e:
            logger.error(f"Error generating proposal PDF: {e}")
            raise

    # ====================================================================
    # Shared PDF helpers (program summary / project plan)
    # ====================================================================

    def _build_cover_elements(
        self,
        title: str,
        subtitle: Optional[str],
        profile_data: Optional[Dict[str, Any]],
        styles: Dict[str, ParagraphStyle],
        md_parser: "MarkdownToPDFParser",
    ) -> List[Any]:
        """Build a standard cover block: title, optional subtitle, author, date, and HR.

        Args:
            title: Document title (rendered with DocTitle style).
            subtitle: Optional subtitle (rendered with DocSubtitle style).
            profile_data: Optional user profile dict; if it contains
                ``display_name`` an author line is emitted.
            styles: Professional PDF styles dictionary.
            md_parser: MarkdownToPDFParser instance (used for XML escaping).

        Returns:
            List of ReportLab flowable elements for the cover block.
        """
        cover: List[Any] = [Paragraph(title, styles["DocTitle"])]

        if subtitle:
            cover.append(
                Paragraph(md_parser.escape_xml(subtitle), styles["DocSubtitle"])
            )

        if profile_data:
            display_name = md_parser.escape_xml(profile_data.get("display_name", ""))
            prof_dept = md_parser.escape_xml(profile_data.get("department", ""))
            if display_name:
                author_parts = [display_name]
                if prof_dept:
                    author_parts.append(prof_dept)
                cover.append(
                    Paragraph(
                        f"Prepared by {', '.join(author_parts)}",
                        styles["MetadataText"],
                    )
                )

        date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
        cover.append(Paragraph(date_str, styles["MetadataText"]))
        cover.append(Spacer(1, 8))

        cover.append(
            HRFlowable(
                width="100%",
                thickness=2,
                color=PDF_COLORS["secondary"],
                spaceBefore=4,
                spaceAfter=16,
            )
        )

        return cover

    def _add_bullet_section(
        self,
        elements: List[Any],
        heading: str,
        items: List[Any],
        styles: Dict[str, ParagraphStyle],
        md_parser: "MarkdownToPDFParser",
    ) -> None:
        """Add a heading followed by a bulleted list of items.

        Args:
            elements: List of ReportLab flowable elements to append to.
            heading: Section heading text.
            items: List of items to render as bullets.
            styles: Professional PDF styles dictionary.
            md_parser: MarkdownToPDFParser instance (used for XML escaping).
        """
        cleaned = [str(i).strip() for i in items if str(i).strip()]
        if not cleaned:
            return

        elements.append(
            Paragraph(md_parser.escape_xml(heading), styles["SectionHeading"])
        )
        elements.append(Spacer(1, 6))

        for item_text in cleaned:
            elements.append(
                Paragraph(
                    f"\u2022 {md_parser.escape_xml(item_text)}",
                    styles["BulletText"],
                )
            )

        elements.append(Spacer(1, 8))

    def _add_markdown_section(
        self,
        elements: List[Any],
        heading: str,
        text: str,
        styles: Dict[str, ParagraphStyle],
        md_parser: "MarkdownToPDFParser",
    ) -> None:
        """Add a heading followed by markdown-parsed body text.

        Args:
            elements: List of ReportLab flowable elements to append to.
            heading: Section heading text.
            text: Body text (may contain markdown).
            styles: Professional PDF styles dictionary.
            md_parser: MarkdownToPDFParser instance (used for XML escaping).
        """
        text = str(text).strip()
        if not text:
            return

        elements.append(
            Paragraph(md_parser.escape_xml(heading), styles["SectionHeading"])
        )
        elements.append(Spacer(1, 6))

        content_elements = md_parser.parse_to_elements(text)
        elements.extend(content_elements)
        elements.append(Spacer(1, 8))

    def _build_zebra_table(
        self,
        table_data: List[List[Any]],
        col_widths: List[float],
        highlight_last_row: bool = False,
    ) -> Table:
        """Build a Table with zebra-striped rows and branded header.

        Args:
            table_data: 2-D list where the first row is the header.
            col_widths: Column widths (ReportLab units, e.g. ``1.5 * inch``).
            highlight_last_row: If *True*, the last row gets a bold font and
                a distinct background (useful for totals rows).

        Returns:
            A styled ``Table`` object ready to be appended to elements.
        """
        tbl = Table(table_data, colWidths=col_widths)

        style_commands: List[Tuple] = [
            ("BACKGROUND", (0, 0), (-1, 0), PDF_COLORS["primary"]),
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, PDF_COLORS["light"]),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]

        # Alternating row colors (skip header row 0)
        for i in range(2, len(table_data), 2):
            style_commands.append(
                ("BACKGROUND", (0, i), (-1, i), hex_to_rl_color("#F8F9FA"))
            )

        if highlight_last_row:
            style_commands.append(
                ("BACKGROUND", (0, -1), (-1, -1), hex_to_rl_color("#E8EEF4"))
            )
            style_commands.append(("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"))

        tbl.setStyle(TableStyle(style_commands))
        return tbl

    # ====================================================================
    # Program Summary PDF
    # ====================================================================

    def generate_program_summary_pdf(
        self,
        summary_data: Dict[str, Any],
        profile_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a PDF program summary.

        Args:
            summary_data: ProgramSummary fields (program_name, department,
                problem_statement, program_description, target_population,
                key_needs, estimated_budget, team_overview, timeline_overview,
                strategic_alignment)
            profile_data: Optional user profile context for author info

        Returns:
            Path to the generated temporary PDF file.
        """
        try:
            pdf_file = tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False, prefix="grantscope_program_summary_"
            )
            pdf_path = pdf_file.name
            pdf_file.close()

            styles = get_professional_pdf_styles()
            md_parser = MarkdownToPDFParser(styles)

            elements: List[Any] = []

            # --- Cover area ---
            program_name = summary_data.get("program_name", "Program Summary")
            elements.extend(
                self._build_cover_elements(
                    title="Program Summary",
                    subtitle=program_name,
                    profile_data=profile_data,
                    styles=styles,
                    md_parser=md_parser,
                )
            )

            # --- Sections ---
            _summary_sections = [
                ("Problem Statement", "problem_statement"),
                ("Program Description", "program_description"),
                ("Target Population", "target_population"),
                ("Key Needs", "key_needs"),
                ("Budget Overview", "estimated_budget"),
                ("Team Overview", "team_overview"),
                ("Timeline", "timeline_overview"),
                ("Strategic Alignment", "strategic_alignment"),
            ]

            for heading, key in _summary_sections:
                value = summary_data.get(key)
                if not value:
                    continue

                # Key Needs rendered as bullet list
                if key == "key_needs":
                    if isinstance(value, list) and len(value) > 0:
                        self._add_bullet_section(
                            elements, heading, value, styles, md_parser
                        )
                        continue
                    # Fall through to render as paragraph if it's a string

                text = str(value).strip()
                if not text:
                    continue

                self._add_markdown_section(elements, heading, text, styles, md_parser)

            # Build with professional header/footer
            title_display = program_name if program_name else "Program Summary"
            builder = ProfessionalPDFBuilder(
                filename=pdf_path,
                title=title_display,
                include_logo=True,
                include_ai_disclosure=True,
            )
            builder.build(elements)

            logger.info(f"Generated program summary PDF: {title_display}")
            return pdf_path

        except Exception as e:
            logger.exception("Error generating program summary PDF")
            raise

    # ====================================================================
    # Project Plan PDF
    # ====================================================================

    def generate_project_plan_pdf(
        self,
        plan_data: Dict[str, Any],
        grant_context: Optional[Dict[str, Any]] = None,
        profile_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a PDF project plan.

        Args:
            plan_data: PlanData fields (program_overview, staffing_plan, budget,
                timeline, deliverables, metrics, partnerships)
            grant_context: Optional grant context for header info
            profile_data: Optional user profile context

        Returns:
            Path to the generated temporary PDF file.
        """
        try:
            pdf_file = tempfile.NamedTemporaryFile(
                suffix=".pdf", delete=False, prefix="grantscope_project_plan_"
            )
            pdf_path = pdf_file.name
            pdf_file.close()

            styles = get_professional_pdf_styles()
            md_parser = MarkdownToPDFParser(styles)

            elements: List[Any] = []

            # --- Cover area ---
            subtitle_text = ""
            overview = plan_data.get("program_overview", "")
            if overview:
                subtitle_text = str(overview).split("\n")[0].strip()
            if not subtitle_text and profile_data:
                subtitle_text = profile_data.get("program_name", "")

            if subtitle_text and len(subtitle_text) > 120:
                subtitle_text = subtitle_text[:117] + "..."

            elements.extend(
                self._build_cover_elements(
                    title="Project Plan",
                    subtitle=subtitle_text or None,
                    profile_data=profile_data,
                    styles=styles,
                    md_parser=md_parser,
                )
            )

            # --- Grant Overview (if grant_context provided) ---
            if grant_context:
                elements.append(Paragraph("Grant Overview", styles["SectionHeading"]))
                elements.append(Spacer(1, 6))

                gc_items = []

                grant_name = grant_context.get("grant_name") or grant_context.get(
                    "name"
                )
                if grant_name:
                    gc_items.append(
                        f"<b>Grant Name:</b> {md_parser.escape_xml(str(grant_name))}"
                    )

                grantor = grant_context.get("grantor")
                if grantor:
                    gc_items.append(
                        f"<b>Grantor:</b> {md_parser.escape_xml(str(grantor))}"
                    )

                deadline = grant_context.get("deadline")
                if deadline:
                    gc_items.append(
                        f"<b>Deadline:</b> {md_parser.escape_xml(str(deadline))}"
                    )

                funding_min = grant_context.get("funding_amount_min")
                funding_max = grant_context.get("funding_amount_max")
                funding_min_val = (
                    _parse_float_safe(funding_min) if funding_min is not None else None
                )
                funding_max_val = (
                    _parse_float_safe(funding_max) if funding_max is not None else None
                )
                if funding_min_val is not None and funding_max_val is not None:
                    gc_items.append(
                        f"<b>Funding Range:</b> ${funding_min_val:,.0f} - ${funding_max_val:,.0f}"
                    )
                elif funding_max_val is not None:
                    gc_items.append(
                        f"<b>Funding Amount:</b> Up to ${funding_max_val:,.0f}"
                    )
                elif funding_min_val is not None:
                    gc_items.append(
                        f"<b>Funding Amount:</b> From ${funding_min_val:,.0f}"
                    )

                for item in gc_items:
                    elements.append(Paragraph(item, styles["BodyText"]))

                elements.append(Spacer(1, 12))

            # --- Program Narrative ---
            narrative = plan_data.get("program_overview", "")
            self._add_markdown_section(
                elements, "Program Narrative", narrative, styles, md_parser
            )

            # --- Staffing Plan Table ---
            staffing = plan_data.get("staffing_plan")
            if staffing and isinstance(staffing, list) and len(staffing) > 0:
                elements.append(Paragraph("Staffing Plan", styles["SectionHeading"]))
                elements.append(Spacer(1, 6))

                table_data = [["Role", "FTE", "Salary Estimate", "Responsibilities"]]

                for entry in staffing:
                    if not isinstance(entry, dict):
                        continue
                    role = md_parser.escape_xml(str(entry.get("role", "")))
                    fte = str(entry.get("fte", ""))
                    salary = entry.get("salary") or entry.get("salary_estimate")
                    salary_str = f"${_parse_float_safe(salary):,.0f}" if salary else ""
                    responsibilities = md_parser.escape_xml(
                        str(entry.get("responsibilities", ""))
                    )
                    if len(responsibilities) > 80:
                        responsibilities = responsibilities[:77] + "..."

                    table_data.append(
                        [
                            Paragraph(role, styles["SmallText"]),
                            Paragraph(fte, styles["SmallText"]),
                            Paragraph(salary_str, styles["SmallText"]),
                            Paragraph(responsibilities, styles["SmallText"]),
                        ]
                    )

                col_widths = [1.5 * inch, 0.6 * inch, 1.2 * inch, 3.7 * inch]
                staffing_table = self._build_zebra_table(table_data, col_widths)
                elements.append(staffing_table)
                elements.append(Spacer(1, 12))

            # --- Budget Table ---
            budget = plan_data.get("budget")
            if budget and isinstance(budget, list) and len(budget) > 0:
                elements.append(Paragraph("Budget Breakdown", styles["SectionHeading"]))
                elements.append(Spacer(1, 6))

                table_data = [["Category", "Amount", "Justification"]]
                total_amount = 0.0

                for entry in budget:
                    if not isinstance(entry, dict):
                        continue
                    category = md_parser.escape_xml(str(entry.get("category", "")))
                    amount = entry.get("amount", 0)
                    amount_val = _parse_float_safe(amount)
                    total_amount += amount_val
                    justification = md_parser.escape_xml(
                        str(entry.get("justification", ""))
                    )
                    if len(justification) > 80:
                        justification = justification[:77] + "..."

                    table_data.append(
                        [
                            Paragraph(category, styles["SmallText"]),
                            Paragraph(f"${amount_val:,.0f}", styles["SmallText"]),
                            Paragraph(justification, styles["SmallText"]),
                        ]
                    )

                # Total row
                table_data.append(
                    [
                        Paragraph("<b>Total</b>", styles["SmallText"]),
                        Paragraph(f"<b>${total_amount:,.0f}</b>", styles["SmallText"]),
                        Paragraph("", styles["SmallText"]),
                    ]
                )

                col_widths = [1.8 * inch, 1.2 * inch, 4.0 * inch]
                budget_table = self._build_zebra_table(
                    table_data, col_widths, highlight_last_row=True
                )
                # Right-align the Amount column
                budget_table.setStyle(TableStyle([("ALIGN", (1, 0), (1, -1), "RIGHT")]))
                elements.append(budget_table)
                elements.append(Spacer(1, 12))

            # --- Timeline ---
            timeline = plan_data.get("timeline")
            if timeline and isinstance(timeline, list) and len(timeline) > 0:
                elements.append(Paragraph("Timeline", styles["SectionHeading"]))
                elements.append(Spacer(1, 6))

                for phase in timeline:
                    if not isinstance(phase, dict):
                        continue

                    phase_name = phase.get("phase") or phase.get("name", "Phase")
                    start = phase.get("start", "")
                    end = phase.get("end", "")
                    date_range = ""
                    if start and end:
                        date_range = f" ({start} \u2013 {end})"
                    elif start:
                        date_range = f" (from {start})"
                    elif end:
                        date_range = f" (until {end})"

                    elements.append(
                        Paragraph(
                            md_parser.escape_xml(f"{phase_name}{date_range}"),
                            styles["SubsectionHeading"],
                        )
                    )

                    milestones = phase.get("milestones", [])
                    if isinstance(milestones, list):
                        for ms in milestones:
                            ms_text = str(ms).strip()
                            if ms_text:
                                elements.append(
                                    Paragraph(
                                        f"\u2022 {md_parser.escape_xml(ms_text)}",
                                        styles["BulletText"],
                                    )
                                )

                    desc = phase.get("description", "")
                    if desc and str(desc).strip():
                        elements.append(
                            Paragraph(
                                md_parser.escape_xml(str(desc).strip()),
                                styles["BodyText"],
                            )
                        )

                elements.append(Spacer(1, 8))

            # --- Deliverables ---
            deliverables = plan_data.get("deliverables")
            if (
                deliverables
                and isinstance(deliverables, list)
                and len(deliverables) > 0
            ):
                self._add_bullet_section(
                    elements, "Deliverables", deliverables, styles, md_parser
                )

            # --- Success Metrics Table ---
            metrics = plan_data.get("metrics")
            if metrics and isinstance(metrics, list) and len(metrics) > 0:
                elements.append(Paragraph("Success Metrics", styles["SectionHeading"]))
                elements.append(Spacer(1, 6))

                table_data = [["Metric", "Target", "How Measured"]]

                for entry in metrics:
                    if not isinstance(entry, dict):
                        continue
                    metric = md_parser.escape_xml(str(entry.get("metric", "")))
                    target = md_parser.escape_xml(str(entry.get("target", "")))
                    how = md_parser.escape_xml(
                        str(entry.get("how_measured") or entry.get("measurement", ""))
                    )
                    if len(how) > 80:
                        how = how[:77] + "..."

                    table_data.append(
                        [
                            Paragraph(metric, styles["SmallText"]),
                            Paragraph(target, styles["SmallText"]),
                            Paragraph(how, styles["SmallText"]),
                        ]
                    )

                col_widths = [2.2 * inch, 1.5 * inch, 3.3 * inch]
                metrics_table = self._build_zebra_table(table_data, col_widths)
                elements.append(metrics_table)
                elements.append(Spacer(1, 12))

            # --- Partnerships ---
            partnerships = plan_data.get("partnerships")
            if partnerships:
                if isinstance(partnerships, list) and len(partnerships) > 0:
                    self._add_bullet_section(
                        elements, "Partnerships", partnerships, styles, md_parser
                    )
                elif isinstance(partnerships, str) and partnerships.strip():
                    self._add_markdown_section(
                        elements, "Partnerships", partnerships, styles, md_parser
                    )

            # Build with professional header/footer
            title_display = subtitle_text if subtitle_text else "Project Plan"
            builder = ProfessionalPDFBuilder(
                filename=pdf_path,
                title=title_display,
                include_logo=True,
                include_ai_disclosure=True,
            )
            builder.build(elements)

            logger.info(f"Generated project plan PDF: {title_display}")
            return pdf_path

        except Exception as e:
            logger.exception("Error generating project plan PDF")
            raise

    async def generate_brief_pptx(
        self,
        brief_title: str,
        card_name: str,
        executive_summary: str,
        content_markdown: str,
        generated_at: Optional[datetime] = None,
        version: Optional[int] = None,
        classification: Optional[Dict[str, str]] = None,
        use_gamma: bool = True,
    ) -> str:
        """
        Generate a PowerPoint presentation for an executive brief.

        Attempts to use Gamma.app for AI-powered presentation generation.
        Falls back to local python-pptx generation if Gamma is unavailable.

        Args:
            brief_title: Title for the brief (usually card name)
            card_name: Name of the card this brief is for
            executive_summary: Executive summary text
            content_markdown: Full brief content in markdown format
            generated_at: When the brief was generated
            version: Version number of the brief
            classification: Optional dict with pillar, horizon, stage info
            use_gamma: Whether to attempt Gamma API (default True)

        Returns:
            Path to the generated PowerPoint file

        Raises:
            Exception: If PowerPoint generation fails
        """
        # Try Gamma.app first if enabled
        if use_gamma:
            try:
                from .gamma_service import GammaService

                gamma = GammaService()
                if gamma.is_available():
                    logger.info(
                        f"Attempting Gamma.app presentation generation for: {brief_title}"
                    )

                    result = await gamma.generate_presentation(
                        title=brief_title,
                        executive_summary=executive_summary,
                        content_markdown=content_markdown,
                        classification=classification,
                        num_slides=8,
                        include_images=True,
                        export_format="pptx",
                    )

                    if result.success and result.pptx_url:
                        # Download the PPTX file
                        pptx_bytes = await gamma.download_export(result.pptx_url)

                        if pptx_bytes:
                            # Save to temp file
                            temp_file = tempfile.NamedTemporaryFile(
                                suffix=".pptx",
                                delete=False,
                                prefix="grantscope_gamma_brief_",
                            )
                            temp_file.write(pptx_bytes)
                            temp_file.close()

                            logger.info(
                                f"Gamma presentation generated successfully: {temp_file.name}"
                            )
                            if result.credits_used:
                                logger.info(
                                    f"Gamma credits used: {result.credits_used}, remaining: {result.credits_remaining}"
                                )

                            return temp_file.name

                    # Log why Gamma failed
                    if result.error_message:
                        logger.warning(
                            f"Gamma generation failed: {result.error_message}"
                        )
                    else:
                        logger.warning(
                            "Gamma generation completed but no PPTX URL returned"
                        )

            except ImportError:
                logger.warning("Gamma service not available, using fallback")
            except Exception as e:
                logger.warning(f"Gamma generation error, falling back to local: {e}")

        # Fallback to local generation with improved markdown handling
        return await self._generate_brief_pptx_local(
            brief_title=brief_title,
            card_name=card_name,
            executive_summary=executive_summary,
            content_markdown=content_markdown,
            generated_at=generated_at,
            version=version,
            classification=classification,
        )

    async def _generate_brief_pptx_local(
        self,
        brief_title: str,
        card_name: str,
        executive_summary: str,
        content_markdown: str,
        generated_at: Optional[datetime] = None,
        version: Optional[int] = None,
        classification: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Local PowerPoint generation with improved markdown handling.

        Used as fallback when Gamma.app is unavailable.
        Includes:
        - Title slide with visual classification tag badges
        - Content slides
        - AI disclosure slide
        - Backup/appendix slides explaining each classification tag
        """
        import re

        try:
            logger.info(f"Generating local brief PowerPoint: {brief_title}")

            # Create presentation
            prs = Presentation()
            prs.slide_width = PPTX_SLIDE_WIDTH
            prs.slide_height = PPTX_SLIDE_HEIGHT

            # Track which tags are used for backup slides
            used_pillar = None
            used_horizon = None
            used_stage = None

            # 1. Title slide with classification tags (with icons)
            subtitle = "Strategic Intelligence Brief"
            if classification:
                tag_parts = []
                if classification.get("pillar"):
                    pillar = classification["pillar"].upper()
                    pillar_def = PILLAR_DEFINITIONS.get(pillar, {})
                    pillar_name = pillar_def.get(
                        "name", PILLAR_NAMES.get(pillar, pillar)
                    )
                    pillar_icon = pillar_def.get("icon", "")
                    tag_parts.append(f"{pillar_icon} {pillar_name}")
                    used_pillar = pillar
                if classification.get("horizon"):
                    horizon = classification["horizon"].upper()
                    horizon_def = HORIZON_DEFINITIONS.get(horizon, {})
                    horizon_name = horizon_def.get(
                        "name", HORIZON_NAMES.get(horizon, horizon)
                    )
                    horizon_icon = horizon_def.get("icon", "")
                    tag_parts.append(f"{horizon_icon} {horizon_name}")
                    used_horizon = horizon
                if classification.get("stage"):
                    stage_raw = classification["stage"]
                    if stage_match := re.search(r"(\d+)", str(stage_raw)):
                        stage_num = int(stage_match.group(1))
                        stage_def = STAGE_DEFINITIONS.get(stage_num, {})
                        stage_name = stage_def.get(
                            "name", STAGE_NAMES.get(stage_num, f"Stage {stage_num}")
                        )
                        stage_icon = stage_def.get("icon", "")
                        tag_parts.append(
                            f"{stage_icon} Stage {stage_num}: {stage_name}"
                        )
                        used_stage = stage_num
                if tag_parts:
                    subtitle = "  |  ".join(tag_parts)

            if generated_at:
                subtitle += f"\n{generated_at.strftime('%B %d, %Y')}"

            self._add_title_slide(prs, title=brief_title, subtitle=subtitle)

            # 2. Executive Summary slide
            if executive_summary:
                clean_summary = self._clean_markdown_for_pptx(executive_summary)
                self._add_smart_content_slide(
                    prs,
                    title="Executive Summary",
                    content=clean_summary,
                    max_chars=1200,
                )

            # 3. Content slides - parse with improved markdown handling
            if content_markdown:
                sections = self._parse_markdown_sections_improved(content_markdown)

                for section_title, section_content in sections[
                    :8
                ]:  # Max 8 content slides
                    clean_content = self._clean_markdown_for_pptx(section_content)
                    self._add_smart_content_slide(
                        prs, title=section_title, content=clean_content, max_chars=1000
                    )

            # 4. AI Disclosure slide
            self._add_ai_disclosure_slide(prs)

            # 5. Backup/Appendix slides - explain each classification tag
            # Appendix header
            appendix_content = """The following slides provide context for the strategic classification tags used in this brief.

These definitions help ensure consistent understanding across City departments and leadership."""
            self._add_smart_content_slide(
                prs,
                title="Appendix: Classification Reference",
                content=appendix_content,
                max_chars=1000,
            )

            # Pillar backup slide
            if used_pillar and used_pillar in PILLAR_DEFINITIONS:
                pillar_def = PILLAR_DEFINITIONS[used_pillar]
                pillar_content = f"""Definition: {pillar_def['description']}

Focus Areas:
"""
                for area in pillar_def.get("focus_areas", []):
                    pillar_content += f"- {area}\n"
                pillar_content += """
This pillar is one of six strategic focus areas guiding City of Austin planning and investment decisions."""

                self._add_smart_content_slide(
                    prs,
                    title=f"{pillar_def.get('icon', '')} Strategic Pillar: {pillar_def['name']}",
                    content=pillar_content,
                    max_chars=1500,
                )

            # Horizon backup slide
            if used_horizon and used_horizon in HORIZON_DEFINITIONS:
                horizon_def = HORIZON_DEFINITIONS[used_horizon]
                horizon_content = f"""Timeframe: {horizon_def['timeframe']}

Definition: {horizon_def['description']}

Characteristics:
"""
                for char in horizon_def.get("characteristics", []):
                    horizon_content += f"- {char}\n"
                horizon_content += """
The planning horizon indicates when this trend is expected to require significant City attention or action."""

                self._add_smart_content_slide(
                    prs,
                    title=f"{horizon_def.get('icon', '')} Planning Horizon: {horizon_def['name']}",
                    content=horizon_content,
                    max_chars=1500,
                )

            # Stage backup slide
            if used_stage and used_stage in STAGE_DEFINITIONS:
                stage_def = STAGE_DEFINITIONS[used_stage]
                stage_content = f"""Definition: {stage_def['description']}

Key Indicators:
"""
                for indicator in stage_def.get("indicators", []):
                    stage_content += f"- {indicator}\n"
                stage_content += """
The maturity stage reflects the current development status of this trend and helps inform appropriate City response strategies."""

                self._add_smart_content_slide(
                    prs,
                    title=f"{stage_def.get('icon', '')} Maturity Stage {used_stage}: {stage_def['name']}",
                    content=stage_content,
                    max_chars=1500,
                )

            # Save presentation
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".pptx", delete=False, prefix="grantscope_brief_"
            )
            prs.save(temp_file.name)

            logger.info(f"Local brief PowerPoint generated: {temp_file.name}")
            return temp_file.name

        except Exception as e:
            logger.error(f"Error generating local brief PowerPoint: {e}")
            raise

    def _clean_markdown_for_pptx(self, text: str) -> str:
        """
        Clean markdown text for PowerPoint display.

        Removes markdown artifacts that don't render well in PPTX.
        """
        import re

        if not text:
            return ""

        # Remove code blocks
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)

        # Convert bold/italic to plain text (PPTX doesn't support inline markdown)
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
        text = re.sub(r"__(.+?)__", r"\1", text)
        text = re.sub(r"\*(.+?)\*", r"\1", text)
        text = re.sub(r"_(.+?)_", r"\1", text)

        # Remove links, keep text
        text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

        # Standardize bullet points
        text = re.sub(r"^[\-\*•]\s+", "• ", text, flags=re.MULTILINE)

        # Remove horizontal rules
        text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

        # Remove headers markers (keep text)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

        # Clean up excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"  +", " ", text)

        return text.strip()

    def _parse_markdown_sections_improved(
        self, content_markdown: str, max_sections: int = 10
    ) -> List[Tuple[str, str]]:
        """
        Improved markdown section parser.

        Handles:
        - Multiple header formats (#, ##, ###)
        - ALL CAPS section headers
        - Bold section headers (**Section**)
        - Reasonable content length per section
        """
        import re

        sections = []
        current_title = "Overview"
        current_content = []

        lines = content_markdown.split("\n")

        for line in lines:
            line_stripped = line.strip()

            if header_match := re.match(r"^(#{1,3})\s+(.+)$", line_stripped):
                if current_content:
                    content_text = "\n".join(current_content).strip()
                    if content_text and len(content_text) > 30:
                        sections.append((current_title, content_text))
                current_title = header_match.group(2).strip()
                # Remove any trailing # or **
                current_title = re.sub(r"\s*#+\s*$", "", current_title)
                current_title = re.sub(r"^\*\*|\*\*$", "", current_title)
                current_content = []
                continue

            # Check for ALL CAPS headers (common AI pattern)
            if re.match(
                r"^[A-Z][A-Z\s&\-]{5,}$", line_stripped
            ) and not line_stripped.startswith("•"):
                if current_content:
                    content_text = "\n".join(current_content).strip()
                    if content_text and len(content_text) > 30:
                        sections.append((current_title, content_text))
                current_title = line_stripped.title()
                current_content = []
                continue

            if bold_match := re.match(r"^\*\*([^*]+)\*\*:?\s*$", line_stripped):
                if current_content:
                    content_text = "\n".join(current_content).strip()
                    if content_text and len(content_text) > 30:
                        sections.append((current_title, content_text))
                current_title = bold_match.group(1).strip()
                current_content = []
                continue

            current_content.append(line)

        # Don't forget the last section
        if current_content:
            content_text = "\n".join(current_content).strip()
            if content_text and len(content_text) > 30:
                sections.append((current_title, content_text))

        # If no sections found, create one from all content
        if not sections and content_markdown.strip():
            sections = [("Key Findings", content_markdown.strip())]

        return sections[:max_sections]

    def _add_smart_content_slide(
        self, prs: Presentation, title: str, content: str, max_chars: int = 1000
    ) -> None:
        """
        Add a content slide with smart text handling.

        Handles bullet points, truncation, and proper formatting.
        """
        slide_layout = prs.slide_layouts[6]  # Blank layout
        slide = prs.slides.add_slide(slide_layout)

        # Add professional header and footer
        self._add_pptx_header(slide)
        self._add_pptx_footer(slide)

        # Slide title
        title_box = slide.shapes.add_textbox(
            PPTX_MARGIN, Inches(1.25), PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_para = title_frame.paragraphs[0]
        title_para.text = title[:60] if len(title) > 60 else title
        title_para.font.size = Pt(28)
        title_para.font.bold = True
        title_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["primary"])

        # Truncate content if needed
        if len(content) > max_chars:
            content = f"{content[:max_chars - 3]}..."

        # Content area
        content_box = slide.shapes.add_textbox(
            PPTX_MARGIN, Inches(1.95), PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN), Inches(4.5)
        )
        content_frame = content_box.text_frame
        content_frame.word_wrap = True

        # Parse content into paragraphs/bullets
        lines = content.split("\n")
        first_para = True

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if first_para:
                para = content_frame.paragraphs[0]
                first_para = False
            else:
                para = content_frame.add_paragraph()

            if (
                is_bullet := line.startswith("•")
                or line.startswith("-")
                or line.startswith("*")
            ):
                # Clean bullet marker and add proper bullet
                line = line.lstrip("•-* ")
                para.text = f"• {line}"
                para.level = 0
            else:
                para.text = line

            para.font.size = Pt(16)
            para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["dark"])
            para.space_before = Pt(6)
            para.space_after = Pt(4)

    def _add_ai_disclosure_slide(self, prs: Presentation) -> None:
        """Add an AI technology disclosure slide."""
        slide_layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(slide_layout)

        self._add_pptx_header(slide)
        self._add_pptx_footer(slide)

        # Title
        title_box = slide.shapes.add_textbox(
            PPTX_MARGIN, Inches(1.25), PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_para = title_frame.paragraphs[0]
        title_para.text = "About This Report"
        title_para.font.size = Pt(28)
        title_para.font.bold = True
        title_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["primary"])

        # Disclosure content
        disclosure_text = """This strategic intelligence brief was generated using the FORESIGHT platform, powered by advanced AI technologies:

• Anthropic Claude - Strategic analysis and synthesis
• OpenAI GPT-4o - Classification and scoring
• GPT Researcher - Autonomous deep research
• Exa AI - Source discovery and retrieval
• Firecrawl - Web content extraction
• Tavily - Real-time research aggregation

The City of Austin is committed to transparent and responsible use of AI technology in public service. All AI-generated content is reviewed for accuracy and relevance."""

        content_box = slide.shapes.add_textbox(
            PPTX_MARGIN, Inches(1.95), PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN), Inches(4.5)
        )
        content_frame = content_box.text_frame
        content_frame.word_wrap = True

        lines = disclosure_text.split("\n")
        first_para = True

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if first_para:
                para = content_frame.paragraphs[0]
                first_para = False
            else:
                para = content_frame.add_paragraph()

            para.text = line
            para.font.size = Pt(14)
            para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["dark"])
            para.space_before = Pt(4)
            para.space_after = Pt(4)

    # =========================================================================
    # Portfolio Export (Bulk Brief Export)
    # =========================================================================

    def _extract_key_takeaways(self, brief_markdown: str) -> List[str]:
        """
        Extract key takeaways from brief markdown content.

        Looks for sections like "Key Takeaways", "Key Findings", "Key Implications",
        "What This Means", bullet points, or numbered lists.
        """
        import re

        takeaways = []

        # Try to find key sections
        key_section_patterns = [
            r"(?:##?\s*)?(?:Key\s+)?(?:Takeaways?|Findings?|Implications?|Insights?)[\s:]*\n((?:[-•*]\s*.+\n?)+)",
            r"(?:##?\s*)?What\s+This\s+Means[^:]*:?\s*\n((?:[-•*]\s*.+\n?)+)",
            r"(?:##?\s*)?Strategic\s+(?:Implications?|Considerations?)[\s:]*\n((?:[-•*]\s*.+\n?)+)",
        ]

        for pattern in key_section_patterns:
            matches = re.findall(pattern, brief_markdown, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                bullets = re.findall(r"[-•*]\s*(.+?)(?:\n|$)", match)
                takeaways.extend([b.strip() for b in bullets if len(b.strip()) > 20])

        # If no structured takeaways found, extract from summary section
        if not takeaways:
            if summary_match := re.search(
                r"(?:##?\s*)?(?:Executive\s+)?Summary[\s:]*\n(.+?)(?:\n##|\n\n\n|$)",
                brief_markdown,
                re.IGNORECASE | re.DOTALL,
            ):
                summary = summary_match.group(1)
                sentences = re.split(r"(?<=[.!?])\s+", summary)
                takeaways = [s.strip() for s in sentences[:3] if len(s.strip()) > 30]

        return takeaways[:5]  # Limit to 5 takeaways

    def _extract_city_examples(self, brief_markdown: str) -> List[Dict[str, str]]:
        """
        Extract examples of other cities, projects, or implementations from brief content.

        Returns list of dicts with 'city', 'project', and 'detail' keys.
        """
        import re

        examples = []

        # Common city/organization patterns
        city_patterns = [
            # "City of X has implemented/launched/deployed..."
            r"(?:City\s+of\s+|The\s+)?([\w\s]+?)(?:\s+has|\s+is|\s+launched|\s+implemented|\s+deployed|\s+piloted|\s+tested)\s+(.+?)(?:\.|,\s+(?:which|resulting|leading))",
            # "In X, they have..."
            r"In\s+([\w\s,]+?),\s+(?:they|the\s+city|officials|government)\s+(?:have|has)\s+(.+?)(?:\.|,)",
            # "X's program/initiative/project..."
            r"([\w\s]+?)'s\s+([\w\s]+?(?:program|initiative|project|pilot|system))\s+(.+?)(?:\.|,)",
            # "programs like X in Y"
            r"(?:programs?|initiatives?|projects?)\s+(?:like|such\s+as)\s+(.+?)\s+in\s+([\w\s]+?)(?:\.|,|$)",
        ]

        for pattern in city_patterns:
            matches = re.findall(pattern, brief_markdown, re.IGNORECASE)
            for match in matches:
                if len(match) >= 2:
                    city = match[0].strip() if match[0] else ""
                    detail = match[1].strip() if len(match) > 1 else ""
                    project = match[2].strip() if len(match) > 2 else ""

                    # Filter out generic terms
                    skip_terms = [
                        "the",
                        "this",
                        "that",
                        "these",
                        "those",
                        "austin",
                        "texas",
                    ]
                    if city.lower() not in skip_terms and len(city) > 2:
                        examples.append(
                            {
                                "city": city,
                                "project": project,
                                "detail": detail[:150] if detail else "",
                            }
                        )

        # Deduplicate by city name
        seen_cities = set()
        unique_examples = []
        for ex in examples:
            city_lower = ex["city"].lower()
            if city_lower not in seen_cities:
                seen_cities.add(city_lower)
                unique_examples.append(ex)

        return unique_examples[:4]  # Limit to 4 examples

    def _generate_portfolio_comparison_chart(
        self, briefs: List, dpi: int = CHART_DPI  # List of PortfolioBrief
    ) -> Optional[str]:
        """
        Generate a comparison chart showing all cards' scores.

        Creates a grouped bar chart comparing impact/relevance/velocity
        across all portfolio cards.
        """
        try:
            # Filter briefs with valid scores
            valid_briefs = [
                b
                for b in briefs
                if b.impact_score is not None or b.relevance_score is not None
            ]

            if not valid_briefs:
                return None

            fig, ax = plt.subplots(figsize=(10, 6))

            # Prepare data
            names = [
                f"{b.card_name[:25]}..." if len(b.card_name) > 25 else b.card_name
                for b in valid_briefs
            ]
            impacts = [b.impact_score or 0 for b in valid_briefs]
            relevances = [b.relevance_score or 0 for b in valid_briefs]
            velocities = [b.velocity_score or 0 for b in valid_briefs]

            x = np.arange(len(names))
            width = 0.25

            # Create bars
            bars1 = ax.bar(
                x - width,
                impacts,
                width,
                label="Impact",
                color=COA_BRAND_COLORS["logo_blue"],
            )
            bars2 = ax.bar(
                x,
                relevances,
                width,
                label="Relevance",
                color=COA_BRAND_COLORS["logo_green"],
            )
            bars3 = ax.bar(
                x + width,
                velocities,
                width,
                label="Velocity",
                color=COA_BRAND_COLORS["dark_blue"],
            )

            # Customize chart
            ax.set_ylabel("Score (0-100)", fontsize=11)
            ax.set_title(
                "Portfolio Score Comparison",
                fontsize=14,
                fontweight="bold",
                color=COA_BRAND_COLORS["dark_blue"],
            )
            ax.set_xticks(x)
            ax.set_xticklabels(names, rotation=45, ha="right", fontsize=9)
            ax.legend(loc="upper right")
            ax.set_ylim(0, 110)

            # Style
            ax.spines["top"].set_visible(False)
            ax.spines["right"].set_visible(False)
            ax.yaxis.grid(True, linestyle="--", alpha=0.3)

            plt.tight_layout()

            # Save
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, prefix="grantscope_portfolio_comparison_"
            )
            plt.savefig(temp_file.name, dpi=dpi, bbox_inches="tight", facecolor="white")

            return temp_file.name

        except Exception as e:
            logger.error(f"Error generating portfolio comparison chart: {e}")
            return None
        finally:
            plt.close("all")

    def _generate_priority_matrix_chart(
        self,
        briefs: List,  # List of PortfolioBrief
        synthesis,  # PortfolioSynthesisData
        dpi: int = CHART_DPI,
    ) -> Optional[str]:
        """
        Generate a visual 2x2 priority matrix chart.

        Places cards in quadrants based on synthesis priority_matrix data.
        """
        try:
            matrix = synthesis.priority_matrix or {}
            urgent = set(matrix.get("high_impact_urgent", []))
            strategic = set(matrix.get("high_impact_strategic", []))
            monitor = set(matrix.get("monitor", []))

            fig, ax = plt.subplots(figsize=(10, 8))

            # Draw quadrant backgrounds
            ax.fill(
                [0, 50, 50, 0], [50, 50, 100, 100], color="#FEE2E2", alpha=0.5
            )  # Urgent - top left
            ax.fill(
                [50, 100, 100, 50], [50, 50, 100, 100], color="#FEF3C7", alpha=0.5
            )  # Strategic - top right
            ax.fill(
                [0, 50, 50, 0], [0, 0, 50, 50], color="#DBEAFE", alpha=0.5
            )  # Monitor - bottom left
            ax.fill(
                [50, 100, 100, 50], [0, 0, 50, 50], color="#D1FAE5", alpha=0.5
            )  # Low priority - bottom right

            # Quadrant labels
            ax.text(
                25,
                95,
                "🔴 URGENT ACTION",
                ha="center",
                va="top",
                fontsize=12,
                fontweight="bold",
                color="#DC2626",
            )
            ax.text(
                75,
                95,
                "🟡 STRATEGIC PLANNING",
                ha="center",
                va="top",
                fontsize=12,
                fontweight="bold",
                color="#D97706",
            )
            ax.text(
                25,
                5,
                "🔵 MONITOR",
                ha="center",
                va="bottom",
                fontsize=12,
                fontweight="bold",
                color="#2563EB",
            )
            ax.text(
                75,
                5,
                "🟢 EVALUATE",
                ha="center",
                va="bottom",
                fontsize=12,
                fontweight="bold",
                color="#059669",
            )

            # Place cards
            for i, brief in enumerate(briefs):
                name = brief.card_name
                # Determine quadrant based on synthesis
                if name in urgent:
                    x = 10 + (i % 3) * 12
                    y = 70 + (i // 3) * 8
                elif name in strategic:
                    x = 60 + (i % 3) * 12
                    y = 70 + (i // 3) * 8
                elif name in monitor:
                    x = 10 + (i % 3) * 12
                    y = 25 + (i // 3) * 8
                else:
                    x = 60 + (i % 3) * 12
                    y = 25 + (i // 3) * 8

                # Get pillar color
                pillar_def = PILLAR_DEFINITIONS.get(
                    brief.pillar_id.upper() if brief.pillar_id else "", {}
                )
                pillar_color = pillar_def.get("color", COA_BRAND_COLORS["logo_blue"])

                # Draw card marker
                ax.scatter(
                    x,
                    y,
                    s=200,
                    c=pillar_color,
                    edgecolors="white",
                    linewidth=2,
                    zorder=5,
                )

                # Truncate name
                short_name = f"{name[:18]}.." if len(name) > 18 else name
                ax.annotate(
                    short_name,
                    (x, y),
                    xytext=(0, -15),
                    textcoords="offset points",
                    ha="center",
                    fontsize=8,
                    color=COA_BRAND_COLORS["dark_blue"],
                )

            # Draw quadrant lines
            ax.axhline(y=50, color="gray", linewidth=2, linestyle="-", alpha=0.5)
            ax.axvline(x=50, color="gray", linewidth=2, linestyle="-", alpha=0.5)

            # Axis labels
            ax.set_xlabel(
                "← Lower Urgency          Higher Urgency →", fontsize=11, color="gray"
            )
            ax.set_ylabel(
                "← Lower Impact          Higher Impact →", fontsize=11, color="gray"
            )
            ax.set_title(
                "Strategic Priority Matrix",
                fontsize=14,
                fontweight="bold",
                color=COA_BRAND_COLORS["dark_blue"],
                pad=20,
            )

            ax.set_xlim(0, 100)
            ax.set_ylim(0, 100)
            ax.set_xticks([])
            ax.set_yticks([])

            for spine in ax.spines.values():
                spine.set_visible(False)

            plt.tight_layout()

            temp_file = tempfile.NamedTemporaryFile(
                suffix=".png", delete=False, prefix="grantscope_priority_matrix_"
            )
            plt.savefig(temp_file.name, dpi=dpi, bbox_inches="tight", facecolor="white")

            return temp_file.name

        except Exception as e:
            logger.error(f"Error generating priority matrix chart: {e}")
            return None
        finally:
            plt.close("all")

    def _add_portfolio_dashboard_slide(
        self,
        prs: Presentation,
        briefs: List,  # List of PortfolioBrief
        comparison_chart_path: Optional[str],
        pillar_chart_path: Optional[str],
    ) -> None:
        """Add a visual dashboard slide with charts and key metrics."""
        slide_layout = prs.slide_layouts[6]
        slide = prs.slides.add_slide(slide_layout)

        self._add_pptx_header(slide)
        self._add_pptx_footer(slide)

        # Title
        title_box = slide.shapes.add_textbox(
            PPTX_MARGIN, Inches(1.25), PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN), Inches(0.5)
        )
        title_frame = title_box.text_frame
        title_para = title_frame.paragraphs[0]
        title_para.text = "Portfolio Dashboard"
        title_para.font.size = Pt(28)
        title_para.font.bold = True
        title_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["primary"])

        # Key metrics row
        metrics_y = Inches(1.85)
        metric_width = Inches(2.2)
        metric_height = Inches(0.9)

        # Calculate metrics
        total_cards = len(briefs)
        avg_impact = sum(b.impact_score or 0 for b in briefs) // max(total_cards, 1)
        pillars_covered = len({b.pillar_id for b in briefs if b.pillar_id})
        horizons = {b.horizon for b in briefs if b.horizon}

        metrics = [
            (str(total_cards), "Strategic Trends"),
            (f"{avg_impact}/100", "Avg Impact Score") if avg_impact > 0 else None,
            (str(pillars_covered), "Pillars Covered"),
            (", ".join(sorted(horizons)) if horizons else "Mixed", "Time Horizons"),
        ]
        metrics = [m for m in metrics if m]  # Remove None

        for i, (value, label) in enumerate(metrics):
            x = PPTX_MARGIN + (i * (metric_width + Inches(0.15)))

            # Metric box
            metric_box = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, x, metrics_y, metric_width, metric_height
            )
            metric_box.fill.solid()
            metric_box.fill.fore_color.rgb = self._hex_to_rgb(
                COA_BRAND_COLORS["light_blue"]
            )
            metric_box.line.fill.background()

            # Value
            value_box = slide.shapes.add_textbox(
                x, metrics_y + Inches(0.1), metric_width, Inches(0.45)
            )
            value_frame = value_box.text_frame
            value_para = value_frame.paragraphs[0]
            value_para.text = value
            value_para.font.size = Pt(24)
            value_para.font.bold = True
            value_para.font.color.rgb = self._hex_to_rgb(COA_BRAND_COLORS["logo_blue"])
            value_para.alignment = PP_ALIGN.CENTER

            # Label
            label_box = slide.shapes.add_textbox(
                x, metrics_y + Inches(0.5), metric_width, Inches(0.35)
            )
            label_frame = label_box.text_frame
            label_para = label_frame.paragraphs[0]
            label_para.text = label
            label_para.font.size = Pt(11)
            label_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["dark"])
            label_para.alignment = PP_ALIGN.CENTER

        # Charts row
        chart_y = Inches(3.0)
        chart_height = Inches(3.3)

        if comparison_chart_path:
            try:
                slide.shapes.add_picture(
                    comparison_chart_path,
                    PPTX_MARGIN,
                    chart_y,
                    width=Inches(4.5),
                    height=chart_height,
                )
            except Exception as e:
                logger.warning(f"Failed to add comparison chart: {e}")

        if pillar_chart_path:
            try:
                slide.shapes.add_picture(
                    pillar_chart_path,
                    Inches(5.0),
                    chart_y,
                    width=Inches(4.2),
                    height=chart_height,
                )
            except Exception as e:
                logger.warning(f"Failed to add pillar chart: {e}")

    def _add_card_deep_dive_slides(
        self,
        prs: Presentation,
        brief,  # PortfolioBrief
        index: int,
        chart_path: Optional[str] = None,
    ) -> None:
        """
        Add 2-3 slides for a single card with detailed insights.

        Slide 1: Overview with pillar, horizon, scores (if available)
        Slide 2: Key takeaways and city examples (if found)
        """
        pillar_def = PILLAR_DEFINITIONS.get(
            brief.pillar_id.upper() if brief.pillar_id else "", {}
        )
        pillar_name = pillar_def.get("name", brief.pillar_id or "Unknown")
        pillar_icon = pillar_def.get("icon", "🏛️")
        pillar_color = pillar_def.get("color", COA_BRAND_COLORS["logo_blue"])

        horizon_def = HORIZON_DEFINITIONS.get(
            brief.horizon.upper() if brief.horizon else "", {}
        )
        horizon_name = horizon_def.get("name", brief.horizon or "Unknown")

        stage_def = STAGE_DEFINITIONS.get(
            brief.stage_id.upper() if brief.stage_id else "", {}
        )
        stage_name = stage_def.get("name", brief.stage_id or "Unknown")

        # ===== SLIDE 1: Overview =====
        slide_layout = prs.slide_layouts[6]
        slide1 = prs.slides.add_slide(slide_layout)

        self._add_pptx_header(slide1)
        self._add_pptx_footer(slide1)

        # Title with index
        title_box = slide1.shapes.add_textbox(
            PPTX_MARGIN, Inches(1.25), PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN), Inches(0.6)
        )
        title_frame = title_box.text_frame
        title_para = title_frame.paragraphs[0]
        card_title = f"{index}. {brief.card_name}"
        title_para.text = card_title[:55] if len(card_title) > 55 else card_title
        title_para.font.size = Pt(26)
        title_para.font.bold = True
        title_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["primary"])

        # Classification badges row
        badges_y = Inches(1.9)
        badge_height = Inches(0.4)

        # Pillar badge
        pillar_badge = slide1.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            PPTX_MARGIN,
            badges_y,
            Inches(2.5),
            badge_height,
        )
        pillar_badge.fill.solid()
        pillar_badge.fill.fore_color.rgb = self._hex_to_rgb(pillar_color)
        pillar_badge.line.fill.background()

        pillar_text = slide1.shapes.add_textbox(
            PPTX_MARGIN, badges_y, Inches(2.5), badge_height
        )
        pf = pillar_text.text_frame
        pp = pf.paragraphs[0]
        pp.text = f"{pillar_icon} {pillar_name}"
        pp.font.size = Pt(14)
        pp.font.bold = True
        pp.font.color.rgb = RGBColor(255, 255, 255)
        pp.alignment = PP_ALIGN.CENTER
        pf.paragraphs[0].space_before = Pt(8)

        # Horizon badge
        horizon_badge = slide1.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(3.0),
            badges_y,
            Inches(2.0),
            badge_height,
        )
        horizon_badge.fill.solid()
        horizon_badge.fill.fore_color.rgb = self._hex_to_rgb(
            COA_BRAND_COLORS["dark_blue"]
        )
        horizon_badge.line.fill.background()

        horizon_text = slide1.shapes.add_textbox(
            Inches(3.0), badges_y, Inches(2.0), badge_height
        )
        hf = horizon_text.text_frame
        hp = hf.paragraphs[0]
        hp.text = f"⏱️ {horizon_name}"
        hp.font.size = Pt(14)
        hp.font.bold = True
        hp.font.color.rgb = RGBColor(255, 255, 255)
        hp.alignment = PP_ALIGN.CENTER
        hf.paragraphs[0].space_before = Pt(8)

        # Stage badge
        stage_badge = slide1.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(5.3),
            badges_y,
            Inches(2.2),
            badge_height,
        )
        stage_badge.fill.solid()
        stage_badge.fill.fore_color.rgb = self._hex_to_rgb(
            COA_BRAND_COLORS["logo_green"]
        )
        stage_badge.line.fill.background()

        stage_text = slide1.shapes.add_textbox(
            Inches(5.3), badges_y, Inches(2.2), badge_height
        )
        sf = stage_text.text_frame
        sp = sf.paragraphs[0]
        sp.text = f"📊 {stage_name}"
        sp.font.size = Pt(14)
        sp.font.bold = True
        sp.font.color.rgb = RGBColor(255, 255, 255)
        sp.alignment = PP_ALIGN.CENTER
        sf.paragraphs[0].space_before = Pt(8)

        # Summary content
        summary_y = Inches(2.5)
        summary_height = Inches(2.2)

        # If we have a chart, put it on the right
        if chart_path:
            summary_width = Inches(4.8)
            summary_box = slide1.shapes.add_textbox(
                PPTX_MARGIN, summary_y, summary_width, summary_height
            )

            # Add chart
            try:
                slide1.shapes.add_picture(
                    chart_path,
                    Inches(5.3),
                    summary_y,
                    width=Inches(4.0),
                    height=Inches(2.8),
                )
            except Exception as e:
                logger.warning(f"Failed to add score chart for {brief.card_name}: {e}")
        else:
            summary_width = PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN)
            summary_box = slide1.shapes.add_textbox(
                PPTX_MARGIN, summary_y, summary_width, summary_height
            )

        summary_frame = summary_box.text_frame
        summary_frame.word_wrap = True

        # Add scores if available
        scores_line = []
        if brief.impact_score and brief.impact_score > 0:
            scores_line.append(f"Impact: {brief.impact_score}/100")
        if brief.relevance_score and brief.relevance_score > 0:
            scores_line.append(f"Relevance: {brief.relevance_score}/100")
        if brief.velocity_score and brief.velocity_score > 0:
            scores_line.append(f"Velocity: {brief.velocity_score}/100")

        if scores_line:
            scores_para = summary_frame.paragraphs[0]
            scores_para.text = " | ".join(scores_line)
            scores_para.font.size = Pt(12)
            scores_para.font.bold = True
            scores_para.font.color.rgb = self._hex_to_rgb(COA_BRAND_COLORS["logo_blue"])
            scores_para.space_after = Pt(12)

            summary_para = summary_frame.add_paragraph()
        else:
            summary_para = summary_frame.paragraphs[0]

        summary_text = brief.brief_summary or "Executive summary not available."
        summary_para.text = (
            summary_text[:600] if len(summary_text) > 600 else summary_text
        )
        summary_para.font.size = Pt(14)
        summary_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["dark"])
        summary_para.space_before = Pt(6)

        # ===== SLIDE 2: Key Takeaways & Examples =====
        takeaways = self._extract_key_takeaways(brief.brief_content_markdown)
        city_examples = self._extract_city_examples(brief.brief_content_markdown)

        # Only add this slide if we have content
        if takeaways or city_examples:
            slide2 = prs.slides.add_slide(slide_layout)

            self._add_pptx_header(slide2)
            self._add_pptx_footer(slide2)

            # Title
            title_box2 = slide2.shapes.add_textbox(
                PPTX_MARGIN,
                Inches(1.25),
                PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN),
                Inches(0.5),
            )
            title_frame2 = title_box2.text_frame
            title_para2 = title_frame2.paragraphs[0]
            title_para2.text = f"{brief.card_name[:40]} - Key Insights"
            title_para2.font.size = Pt(24)
            title_para2.font.bold = True
            title_para2.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["primary"])

            content_y = Inches(1.85)

        # Key Takeaways section
        if takeaways:
            takeaways_box = slide2.shapes.add_textbox(
                PPTX_MARGIN, content_y, Inches(4.5), Inches(4.0)
            )
            tf = takeaways_box.text_frame
            tf.word_wrap = True

            # Section header
            header_para = tf.paragraphs[0]
            header_para.text = "📌 Key Takeaways"
            header_para.font.size = Pt(16)
            header_para.font.bold = True
            header_para.font.color.rgb = self._hex_to_rgb(COA_BRAND_COLORS["logo_blue"])
            header_para.space_after = Pt(8)

            for takeaway in takeaways:
                bullet_para = tf.add_paragraph()
                bullet_text = takeaway[:200] if len(takeaway) > 200 else takeaway
                bullet_para.text = f"• {bullet_text}"
                bullet_para.font.size = Pt(12)
                bullet_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["dark"])
                bullet_para.space_before = Pt(6)

        # City Examples section
        if city_examples:
            examples_x = Inches(5.0) if takeaways else PPTX_MARGIN
            examples_width = (
                Inches(4.2) if takeaways else PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN)
            )

            examples_box = slide2.shapes.add_textbox(
                examples_x, content_y, examples_width, Inches(4.0)
            )
            ef = examples_box.text_frame
            ef.word_wrap = True

            # Section header
            ex_header = ef.paragraphs[0]
            ex_header.text = "🌆 Examples from Other Cities"
            ex_header.font.size = Pt(16)
            ex_header.font.bold = True
            ex_header.font.color.rgb = self._hex_to_rgb(COA_BRAND_COLORS["logo_green"])
            ex_header.space_after = Pt(8)

            for example in city_examples:
                city_para = ef.add_paragraph()
                city_text = f"• {example['city']}"
                if example.get("detail"):
                    city_text += f": {example['detail']}"
                city_para.text = city_text[:180] if len(city_text) > 180 else city_text
                city_para.font.size = Pt(12)
                city_para.font.color.rgb = self._hex_to_rgb(GRANTSCOPE_COLORS["dark"])
                city_para.space_before = Pt(6)

    async def generate_portfolio_pptx_local(
        self,
        workstream_name: str,
        briefs: List,  # List of PortfolioBrief
        synthesis,  # PortfolioSynthesisData
    ) -> str:
        """
        Generate a local portfolio PPTX presentation.

        Creates a professional multi-card portfolio deck with:
        - Title slide with branding
        - Portfolio dashboard with metrics and charts
        - Executive overview synthesis
        - Visual priority matrix (2x2)
        - Per-card deep dives (2-3 slides each) with:
          - Classification badges and scores (when available)
          - Key takeaways extracted from brief
          - City/project examples cited in research
        - Cross-cutting themes
        - Recommended actions
        - AI disclosure

        Args:
            workstream_name: Name of the workstream for title
            briefs: List of PortfolioBrief objects
            synthesis: PortfolioSynthesisData with AI-generated overview

        Returns:
            Path to the generated PPTX file
        """
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
        from datetime import datetime, timezone
        import tempfile

        prs = Presentation()
        prs.slide_width = PPTX_SLIDE_WIDTH
        prs.slide_height = PPTX_SLIDE_HEIGHT

        temp_files_to_cleanup = []

        try:
            # Get pillar icons for title
            pillar_icons = []
            pillar_counts = {}
            for brief in briefs:
                pillar_def = PILLAR_DEFINITIONS.get(
                    brief.pillar_id.upper() if brief.pillar_id else "", {}
                )
                icon = pillar_def.get("icon", "🏛️")
                pillar_name = pillar_def.get("name", brief.pillar_id or "Other")
                if icon not in pillar_icons:
                    pillar_icons.append(icon)
                pillar_counts[pillar_name] = pillar_counts.get(pillar_name, 0) + 1

            # ===== 1. TITLE SLIDE =====
            title_subtitle = f"{' '.join(pillar_icons)} | {len(briefs)} Strategic Trends\n{datetime.now(timezone.utc).strftime('%B %Y')}"
            self._add_title_slide(prs, workstream_name, title_subtitle)

            # ===== 2. PORTFOLIO DASHBOARD =====
            # Generate charts
            comparison_chart_path = self._generate_portfolio_comparison_chart(briefs)
            if comparison_chart_path:
                temp_files_to_cleanup.append(comparison_chart_path)

            pillar_chart_path = None
            if pillar_counts:
                pillar_chart_path = self.generate_pillar_distribution_chart(
                    pillar_counts, "Distribution by Pillar"
                )
                if pillar_chart_path:
                    temp_files_to_cleanup.append(pillar_chart_path)

            self._add_portfolio_dashboard_slide(
                prs, briefs, comparison_chart_path, pillar_chart_path
            )

            # ===== 3. WHY THIS MATTERS NOW =====
            urgency = (
                getattr(synthesis, "urgency_statement", "")
                or f"These {len(briefs)} trends represent critical opportunities and challenges. Early action positions Austin as a leader; delay risks falling behind peer cities."
            )
            urgency_content = f"{urgency}\n\n**The Window of Opportunity**\n\nCities that move first on emerging trends gain competitive advantage in talent attraction, federal funding, and citizen satisfaction."
            self._add_smart_content_slide(
                prs,
                title="Why This Matters Now",
                content=urgency_content,
                max_chars=1200,
            )

            # ===== 4. EXECUTIVE OVERVIEW =====
            overview_content = (
                synthesis.executive_overview or "Portfolio synthesis in progress..."
            )
            self._add_smart_content_slide(
                prs,
                title="Executive Overview",
                content=overview_content,
                max_chars=1400,
            )

            if matrix_chart_path := self._generate_priority_matrix_chart(
                briefs, synthesis
            ):
                temp_files_to_cleanup.append(matrix_chart_path)

                # Add matrix slide
                slide_layout = prs.slide_layouts[6]
                matrix_slide = prs.slides.add_slide(slide_layout)
                self._add_pptx_header(matrix_slide)
                self._add_pptx_footer(matrix_slide)

                title_box = matrix_slide.shapes.add_textbox(
                    PPTX_MARGIN,
                    Inches(1.25),
                    PPTX_SLIDE_WIDTH - (2 * PPTX_MARGIN),
                    Inches(0.5),
                )
                title_frame = title_box.text_frame
                title_para = title_frame.paragraphs[0]
                title_para.text = "Strategic Priority Matrix"
                title_para.font.size = Pt(28)
                title_para.font.bold = True
                title_para.font.color.rgb = self._hex_to_rgb(
                    GRANTSCOPE_COLORS["primary"]
                )

                try:
                    matrix_slide.shapes.add_picture(
                        matrix_chart_path,
                        Inches(0.8),
                        Inches(1.9),
                        width=Inches(8.4),
                        height=Inches(5.0),
                    )
                except Exception as e:
                    logger.warning(f"Failed to add priority matrix chart: {e}")
            else:
                # Fallback to text-based priority slide
                matrix = synthesis.priority_matrix or {}
                urgent = matrix.get("high_impact_urgent", [])
                strategic = matrix.get("high_impact_strategic", [])
                monitor = matrix.get("monitor", [])

                priority_content = "🔴 **High Impact - Urgent Action**\n" + (
                    "\n".join(f"• {item}" for item in urgent)
                    if urgent
                    else "• None identified"
                )
                priority_content += "\n\n🟡 **High Impact - Strategic Planning**\n"
                priority_content += (
                    "\n".join(f"• {item}" for item in strategic)
                    if strategic
                    else "• None identified"
                )
                priority_content += "\n\n🟢 **Monitor & Evaluate**\n"
                priority_content += (
                    "\n".join(f"• {item}" for item in monitor)
                    if monitor
                    else "• None identified"
                )

                self._add_smart_content_slide(
                    prs,
                    title="Strategic Priorities",
                    content=priority_content,
                    max_chars=1500,
                )

            # ===== 6. IMPLEMENTATION GUIDANCE =====
            impl = getattr(synthesis, "implementation_guidance", {}) or {}
            impl_lines = []
            if impl.get("pilot_now"):
                impl_lines.append(
                    f"🚀 **Ready to Pilot**: {', '.join(impl['pilot_now'])}"
                )
            if impl.get("investigate_further"):
                impl_lines.append(
                    f"🔍 **Investigate Further**: {', '.join(impl['investigate_further'])}"
                )
            if impl.get("meet_with_vendors"):
                impl_lines.append(
                    f"🤝 **Meet with Vendors**: {', '.join(impl['meet_with_vendors'])}"
                )
            if impl.get("policy_review"):
                impl_lines.append(
                    f"📋 **Policy Review Needed**: {', '.join(impl['policy_review'])}"
                )
            if impl.get("staff_training"):
                impl_lines.append(
                    f"👥 **Staff Training Focus**: {', '.join(impl['staff_training'])}"
                )
            if impl.get("budget_planning"):
                impl_lines.append(
                    f"💰 **Budget Planning**: {', '.join(impl['budget_planning'])}"
                )

            if impl_lines:
                impl_content = "What should Austin DO with each trend?\n\n" + "\n".join(
                    impl_lines
                )
                self._add_smart_content_slide(
                    prs,
                    title="Implementation Guidance",
                    content=impl_content,
                    max_chars=1400,
                )

            # ===== 7. PER-CARD DEEP DIVES =====
            for i, brief in enumerate(briefs, 1):
                # Generate score chart for this card if scores exist
                card_chart_path = None
                if has_scores := (
                    (brief.impact_score and brief.impact_score > 0)
                    or (brief.relevance_score and brief.relevance_score > 0)
                    or (brief.velocity_score and brief.velocity_score > 0)
                ):
                    # Create a simple CardExportData-like object for chart generation
                    scores = {
                        "Impact": brief.impact_score or 0,
                        "Relevance": brief.relevance_score or 0,
                        "Velocity": brief.velocity_score or 0,
                    }
                    if valid_scores := {k: v for k, v in scores.items() if v > 0}:
                        card_chart_path = self._generate_radar_chart(
                            valid_scores, brief.card_name, CHART_DPI
                        )
                        if card_chart_path:
                            temp_files_to_cleanup.append(card_chart_path)

                self._add_card_deep_dive_slides(prs, brief, i, card_chart_path)

            # ===== 8. CROSS-CUTTING THEMES =====
            themes_content = "**Common Patterns Across Trends**\n"
            themes_content += (
                "\n".join(f"• {theme}" for theme in (synthesis.key_themes or []))
                or "• Analysis in progress"
            )
            themes_content += "\n\n**Strategic Connections**\n"
            themes_content += (
                "\n".join(
                    f"• {insight}"
                    for insight in (synthesis.cross_cutting_insights or [])
                )
                or "• Analysis in progress"
            )

            self._add_smart_content_slide(
                prs,
                title="Cross-Cutting Themes",
                content=themes_content,
                max_chars=1400,
            )

            if ninety_day := getattr(synthesis, "ninety_day_actions", []) or []:
                actions_content = "What Austin should do in the next 90 days:\n\n"
                for action in ninety_day[:5]:
                    action_text = action.get("action", "")
                    owner = action.get("owner", "TBD")
                    by_when = action.get("by_when", "90 days")
                    metric = action.get("success_metric", "")
                    actions_content += f"✓ **{action_text}**\n"
                    actions_content += f"   Owner: {owner} | By: {by_when}"
                    if metric:
                        actions_content += f"\n   Success: {metric}"
                    actions_content += "\n\n"
            else:
                # Fall back to recommended_actions
                actions_content = ""
                for action in (synthesis.recommended_actions or [])[:6]:
                    action_text = action.get("action", "")
                    owner = action.get("owner", "TBD")
                    timeline = action.get("timeline", "TBD")
                    related_cards = action.get("cards", [])

                    actions_content += f"✓ **{action_text}**\n"
                    actions_content += f"   Owner: {owner} | Timeline: {timeline}"
                    if related_cards:
                        actions_content += f" | Related: {', '.join(related_cards[:2])}"
                    actions_content += "\n\n"

                if not actions_content:
                    actions_content = (
                        "Action plan to be developed based on leadership priorities."
                    )

            self._add_smart_content_slide(
                prs, title="90-Day Action Plan", content=actions_content, max_chars=1400
            )

            # ===== 10. RISKS & OPPORTUNITIES =====
            risk_text = (
                getattr(synthesis, "risk_summary", "")
                or "Delayed action on these trends could result in Austin falling behind peer cities, missing federal funding windows, and losing competitive advantage."
            )
            opp_text = (
                getattr(synthesis, "opportunity_summary", "")
                or "Early action positions Austin as a national leader, attracts innovation investment, and delivers improved services to residents."
            )

            risk_opp_content = f"⚠️ **If Austin Doesn't Act**\n{risk_text}\n\n✨ **If Austin Leads**\n{opp_text}"
            self._add_smart_content_slide(
                prs,
                title="Risks & Opportunities",
                content=risk_opp_content,
                max_chars=1400,
            )

            # ===== 11. AI DISCLOSURE =====
            self._add_ai_disclosure_slide(prs)

            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=".pptx", delete=False, prefix="grantscope_portfolio_local_"
            )
            prs.save(temp_file.name)
            temp_file.close()

            logger.info(
                f"Generated enhanced local portfolio PPTX: {len(briefs)} cards, {len(prs.slides)} slides"
            )
            return temp_file.name

        finally:
            # Clean up temp chart files
            self.cleanup_temp_files(temp_files_to_cleanup)

    async def generate_portfolio_pdf(
        self,
        workstream_name: str,
        briefs: List,  # List of PortfolioBrief
        synthesis,  # PortfolioSynthesisData
    ) -> str:
        """
        Generate a detailed portfolio PDF document.

        PDF version includes MORE detail than PPTX since readers can
        absorb more information. Same structure but expanded content.

        Args:
            workstream_name: Name of the workstream for title
            briefs: List of PortfolioBrief objects
            synthesis: PortfolioSynthesisData with AI-generated overview

        Returns:
            Path to the generated PDF file
        """
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            PageBreak,
            Table,
            TableStyle,
        )
        from reportlab.lib.units import inch
        from datetime import datetime, timezone
        import tempfile

        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".pdf", delete=False, prefix="grantscope_portfolio_"
        )

        doc = SimpleDocTemplate(
            temp_file.name,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            "PortfolioTitle",
            parent=styles["Heading1"],
            fontSize=24,
            textColor=HexColor(COA_BRAND_COLORS["logo_blue"]),
            spaceAfter=12,
            alignment=1,  # Center
        )

        subtitle_style = ParagraphStyle(
            "PortfolioSubtitle",
            parent=styles["Normal"],
            fontSize=14,
            textColor=HexColor(COA_BRAND_COLORS["dark_gray"]),
            spaceAfter=24,
            alignment=1,
        )

        section_style = ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontSize=16,
            textColor=HexColor(COA_BRAND_COLORS["logo_blue"]),
            spaceBefore=18,
            spaceAfter=12,
        )

        card_title_style = ParagraphStyle(
            "CardTitle",
            parent=styles["Heading3"],
            fontSize=14,
            textColor=HexColor(COA_BRAND_COLORS["dark_blue"]),
            spaceBefore=12,
            spaceAfter=6,
        )

        body_style = ParagraphStyle(
            "BodyText",
            parent=styles["Normal"],
            fontSize=11,
            textColor=HexColor(COA_BRAND_COLORS["dark_gray"]),
            spaceAfter=8,
            leading=14,
        )

        elements = [Spacer(1, inch * 2)]

        elements.append(Paragraph(workstream_name, title_style))
        elements.append(Paragraph("Strategic Intelligence Portfolio", subtitle_style))
        elements.append(
            Paragraph(
                f"{len(briefs)} Strategic Trends | {datetime.now(timezone.utc).strftime('%B %Y')}",
                subtitle_style,
            )
        )
        elements.append(
            Paragraph("City of Austin | FORESIGHT Platform", subtitle_style)
        )
        elements.append(PageBreak())

        # Executive Overview
        elements.append(Paragraph("Executive Overview", section_style))
        overview_text = (
            synthesis.executive_overview or "Portfolio analysis in progress."
        )
        # Split into paragraphs for better formatting
        for para in overview_text.split("\n\n"):
            if para.strip():
                elements.append(Paragraph(para.strip(), body_style))
        elements.append(Spacer(1, 12))

        # Key Themes
        elements.append(Paragraph("Key Themes", section_style))
        elements.extend(
            Paragraph(f"• {theme}", body_style)
            for theme in (synthesis.key_themes or [])
        )
        elements.append(Spacer(1, 12))

        # Strategic Priorities
        elements.append(Paragraph("Strategic Priorities", section_style))
        matrix = synthesis.priority_matrix or {}

        if urgent := matrix.get("high_impact_urgent", []):
            elements.append(
                Paragraph("<b>High Impact - Urgent Action:</b>", body_style)
            )
            for item in urgent:
                elements.append(Paragraph(f"  • {item}", body_style))

        if strategic := matrix.get("high_impact_strategic", []):
            elements.append(
                Paragraph("<b>High Impact - Strategic Planning:</b>", body_style)
            )
            for item in strategic:
                elements.append(Paragraph(f"  • {item}", body_style))

        if monitor := matrix.get("monitor", []):
            elements.append(Paragraph("<b>Monitor & Evaluate:</b>", body_style))
            for item in monitor:
                elements.append(Paragraph(f"  • {item}", body_style))

        elements.append(PageBreak())

        # Per-card detailed sections (PDF gets FULL content)
        elements.append(Paragraph("Trend Analysis", section_style))

        for i, brief in enumerate(briefs, 1):
            pillar_def = PILLAR_DEFINITIONS.get(
                brief.pillar_id.upper() if brief.pillar_id else "", {}
            )
            pillar_name = pillar_def.get("name", brief.pillar_id or "Unknown")
            horizon_name = brief.horizon or "H2"

            elements.append(Paragraph(f"{i}. {brief.card_name}", card_title_style))
            elements.append(
                Paragraph(
                    f"<b>Pillar:</b> {pillar_name} | <b>Horizon:</b> {horizon_name} | "
                    f"<b>Impact:</b> {brief.impact_score}/100 | <b>Relevance:</b> {brief.relevance_score}/100",
                    body_style,
                )
            )

            # Summary
            if brief.brief_summary:
                elements.append(
                    Paragraph(f"<b>Summary:</b> {brief.brief_summary}", body_style)
                )

            # Full brief content (PDF gets expanded detail)
            if brief.brief_content_markdown:
                # Clean up markdown for PDF
                content = brief.brief_content_markdown
                # Remove markdown headers, keep content
                import re

                content = re.sub(r"^#+\s+", "", content, flags=re.MULTILINE)
                content = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", content)
                content = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", content)

                # Truncate if very long
                if len(content) > 2000:
                    content = f"{content[:2000]}..."

                for para in content.split("\n\n")[:5]:  # First 5 paragraphs
                    if para.strip():
                        elements.append(Paragraph(para.strip(), body_style))

            elements.append(Spacer(1, 12))

        elements.append(PageBreak())

        # Cross-Cutting Insights
        elements.append(Paragraph("Cross-Cutting Insights", section_style))
        for insight in synthesis.cross_cutting_insights or []:
            elements.append(Paragraph(f"• {insight}", body_style))
        elements.append(Spacer(1, 12))

        # Recommended Actions
        elements.append(Paragraph("Recommended Actions", section_style))
        for action in synthesis.recommended_actions or []:
            action_text = action.get("action", "")
            owner = action.get("owner", "TBD")
            timeline = action.get("timeline", "TBD")
            cards = ", ".join(action.get("cards", []))

            elements.append(Paragraph(f"<b>{action_text}</b>", body_style))
            elements.append(
                Paragraph(f"  Owner: {owner} | Timeline: {timeline}", body_style)
            )
            if cards:
                elements.append(Paragraph(f"  Related Trends: {cards}", body_style))
            elements.append(Spacer(1, 6))

        # AI Disclosure
        elements.append(PageBreak())
        elements.append(Paragraph("About This Portfolio", section_style))
        disclosure = """This strategic intelligence portfolio was generated using the FORESIGHT platform, 
        powered by advanced AI technologies including Anthropic Claude, OpenAI GPT-4, GPT Researcher, 
        and Gamma.app. The City of Austin is committed to transparent and responsible use of AI 
        technology in public service. All AI-generated content is reviewed for accuracy and relevance."""
        elements.append(Paragraph(disclosure, body_style))

        # Build PDF
        doc.build(elements)
        temp_file.close()

        logger.info(f"Generated portfolio PDF: {len(briefs)} cards")
        return temp_file.name
