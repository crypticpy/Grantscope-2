"""
Gamma.app API Integration Service

Provides AI-powered presentation generation using Gamma's Generate API.
Creates polished, executive-quality presentations with AI-generated images
and professional layouts.

Usage:
    gamma_service = GammaService()
    result = await gamma_service.generate_presentation(
        title="Perovskite Solar Cells",
        executive_summary="...",
        content_markdown="...",
        classification={"pillar": "ES", "horizon": "H2", "stage": "4"}
    )

    if result.success:
        pptx_bytes = await gamma_service.download_export(result.generation_id, "pptx")
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


# ============================================================================
# Configuration
# ============================================================================

GAMMA_API_BASE_URL = "https://public-api.gamma.app/v1.0"
GAMMA_API_KEY = os.getenv("GAMMA_API_KEY")
GAMMA_API_ENABLED = os.getenv("GAMMA_API_ENABLED", "true").lower() == "true"

# Optional: Gamma theme and folder IDs (configure in Railway env vars)
# To find these: use GET /themes and GET /folders endpoints, or copy from Gamma app URL
GAMMA_THEME_ID = os.getenv("GAMMA_THEME_ID")  # e.g., "abc123def456"
GAMMA_FOLDER_ID = os.getenv("GAMMA_FOLDER_ID")  # e.g., "xyz789folder"

# Polling configuration
GAMMA_POLL_INTERVAL_SECONDS = 3
GAMMA_POLL_MAX_ATTEMPTS = 60  # 3 minutes max wait time
GAMMA_REQUEST_TIMEOUT = 30

# Slide count configuration - enough for comprehensive briefs
GAMMA_MIN_SLIDES = 10  # Minimum slides for brief structure
GAMMA_MAX_SLIDES = 15  # Maximum for detailed briefs
GAMMA_DEFAULT_SLIDES = 12  # Default - covers all sections well

# Default branding - City of Austin logos hosted on Dropbox
FORESIGHT_BRANDING = "FORESIGHT Strategic Intelligence Platform"
COA_LOGO_HORIZONTAL = os.getenv(
    "COA_LOGO_HORIZONTAL",
    "https://dl.dropboxusercontent.com/scl/fi/vtmgwhrila35a9gcthuh0/COA-Logo-Horizontal-Official-RGB.png?rlkey=xj2s6muc7r4dkjb3lrn72dywt",
)
COA_LOGO_CIRCLE = os.getenv(
    "COA_LOGO_CIRCLE",
    "https://dl.dropboxusercontent.com/scl/fi/s23pczc5japf6w2l5lj7c/COA-Official-Circle.png?rlkey=zijpoik2f5qesjasgr7ii6afy",
)
# Backwards compatibility
COA_LOGO_URL = COA_LOGO_HORIZONTAL

# Official City of Austin Brand Colors
COA_COLORS = {
    # Official Palette
    "logo_blue": "#44499C",  # Primary - headers, titles, accents
    "logo_green": "#009F4D",  # Secondary - highlights, positive indicators
    "faded_white": "#f7f6f5",  # Backgrounds
    # Supporting Palette
    "compliant_green": "#008743",
    "dark_blue": "#22254E",  # Emphasis text
    "dark_green": "#005027",
    "light_blue": "#dcf2fd",  # Subtle backgrounds
    "light_green": "#dff0e3",  # Callout boxes
    # Extended Palette
    "red": "#F83125",  # Risks, concerns
    "orange": "#FF8F00",
    "yellow": "#FFC600",
    "cyan": "#009CDE",
    "purple": "#9F3CC9",
    "light_gray": "#C6C5C4",
    "brown": "#8F5201",
    "dark_gray": "#636262",  # Body text
    "black": "#000000",
}

# Classification data for slide context (matches database pillars table)
PILLAR_NAMES = {
    "CH": "Community Health & Sustainability",
    "EW": "Economic & Workforce Development",
    "HG": "High-Performing Government",
    "HH": "Homelessness & Housing",
    "MC": "Mobility & Critical Infrastructure",
    "PS": "Public Safety",
}

# Extended pillar definitions for backup slides
# Uses the 6 canonical AI pillar codes (CH, EW, HG, HH, MC, PS)
PILLAR_DEFINITIONS = {
    "CH": {
        "name": "Community Health & Sustainability",
        "icon": "🏥",
        "description": "Promoting physical, mental, and social well-being for all Austinites",
        "focus_areas": [
            "Health equity and access to services",
            "Preventive health and early intervention",
            "Mental health resources and support",
            "Healthy environments for physical activity",
            "Public health emergency preparedness",
        ],
    },
    "EW": {
        "name": "Economic & Workforce Development",
        "icon": "📈",
        "description": "Economic mobility, small business support, and creative economy",
        "focus_areas": [
            "Workforce development and job training",
            "Small business support platforms",
            "Creative economy initiatives",
            "Economic resilience planning",
            "Entrepreneurship ecosystems",
        ],
    },
    "HG": {
        "name": "High-Performing Government",
        "icon": "🏛️",
        "description": "Fiscal integrity, technology modernization, and community engagement",
        "focus_areas": [
            "Government technology modernization",
            "Civic engagement platforms",
            "Municipal process automation",
            "Data-driven decision making",
            "Government workforce development",
        ],
    },
    "HH": {
        "name": "Homelessness & Housing",
        "icon": "🏠",
        "description": "Complete communities, affordable housing, and homelessness reduction",
        "focus_areas": [
            "Affordable housing supply",
            "Homelessness prevention and solutions",
            "Housing quality and safety",
            "Supportive housing models",
            "Community development",
        ],
    },
    "MC": {
        "name": "Mobility & Critical Infrastructure",
        "icon": "🚇",
        "description": "Ensuring accessible, sustainable, and efficient transportation options",
        "focus_areas": [
            "Public transit accessibility",
            "Bike lanes and pedestrian infrastructure",
            "Traffic management and congestion reduction",
            "Smart transportation technology",
            "Regional connectivity",
        ],
    },
    "PS": {
        "name": "Public Safety",
        "icon": "🛡️",
        "description": "Community relationships, fair service delivery, and disaster preparedness",
        "focus_areas": [
            "Community policing and trust building",
            "Emergency response innovation",
            "Disaster preparedness systems",
            "Violence prevention programs",
            "Fair service delivery",
        ],
    },
}

HORIZON_NAMES = {
    "H1": "Mainstream (0-3 years)",
    "H2": "Transitional (3-7 years)",
    "H3": "Transformative (7-15+ years)",
}

# Extended horizon definitions for backup slides
HORIZON_DEFINITIONS = {
    "H1": {
        "name": "Mainstream",
        "timeframe": "0-3 years",
        "icon": "🎯",
        "description": "Technologies and trends ready for near-term implementation",
        "characteristics": [
            "Proven technology with established vendors",
            "Clear implementation pathways",
            "Measurable ROI within budget cycles",
            "Low technical risk",
            "Existing municipal precedents",
        ],
    },
    "H2": {
        "name": "Transitional",
        "timeframe": "3-7 years",
        "icon": "🔄",
        "description": "Emerging opportunities requiring strategic positioning and pilots",
        "characteristics": [
            "Technology maturing but not yet mainstream",
            "Pilot programs proving viability",
            "Requires strategic investment decisions",
            "Moderate technical risk",
            "Early adopter municipalities seeing results",
        ],
    },
    "H3": {
        "name": "Transformative",
        "timeframe": "7-15+ years",
        "icon": "🚀",
        "description": "Long-term trends requiring monitoring and scenario planning",
        "characteristics": [
            "Early-stage or experimental technology",
            "Significant uncertainty in timeline",
            "Potential for major disruption",
            "High technical risk",
            "Requires ongoing monitoring",
        ],
    },
}

STAGE_NAMES = {
    1: "Concept",
    2: "Exploring",
    3: "Pilot",
    4: "Proof of Concept",
    5: "Implementing",
    6: "Scaling",
    7: "Mature",
    8: "Declining",
}

# Extended stage definitions for backup slides
STAGE_DEFINITIONS = {
    1: {
        "name": "Concept",
        "icon": "💡",
        "description": "Early idea or observation with minimal evidence",
        "indicators": [
            "Academic research or theoretical papers",
            "Initial proof of concept in labs",
            "No commercial products available",
            "High uncertainty about viability",
        ],
    },
    2: {
        "name": "Exploring",
        "icon": "🔍",
        "description": "Initial research and experimentation phase",
        "indicators": [
            "Startups and research institutions active",
            "Early patents being filed",
            "Venture capital showing interest",
            "Small-scale experiments underway",
        ],
    },
    3: {
        "name": "Pilot",
        "icon": "🧪",
        "description": "Small-scale testing and validation",
        "indicators": [
            "Pilot programs in limited settings",
            "Early performance data available",
            "Technical feasibility demonstrated",
            "Identifying implementation challenges",
        ],
    },
    4: {
        "name": "Proof of Concept",
        "icon": "✅",
        "description": "Demonstrated viability with supporting evidence",
        "indicators": [
            "Successful pilots with measurable outcomes",
            "Multiple municipalities testing",
            "Vendor ecosystem developing",
            "Business case becoming clear",
        ],
    },
    5: {
        "name": "Implementing",
        "icon": "🏗️",
        "description": "Full-scale deployment underway",
        "indicators": [
            "Active implementation projects",
            "Established vendor relationships",
            "Documented best practices emerging",
            "Budget allocations secured",
        ],
    },
    6: {
        "name": "Scaling",
        "icon": "📊",
        "description": "Expanding reach and impact",
        "indicators": [
            "Widespread adoption beginning",
            "Economies of scale realized",
            "Integration with existing systems",
            "Proven return on investment",
        ],
    },
    7: {
        "name": "Mature",
        "icon": "🏆",
        "description": "Established and widely adopted",
        "indicators": [
            "Industry standard practice",
            "Commodity pricing available",
            "Well-understood implementation",
            "Focus shifts to optimization",
        ],
    },
    8: {
        "name": "Declining",
        "icon": "📉",
        "description": "Losing relevance or being replaced",
        "indicators": [
            "Newer alternatives emerging",
            "Decreasing vendor support",
            "Migration planning needed",
            "Legacy system considerations",
        ],
    },
}


# ============================================================================
# Data Models
# ============================================================================


class GammaStatus(Enum):
    """Status of a Gamma generation request."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class GammaGenerationResult:
    """Result of a Gamma presentation generation."""

    success: bool
    generation_id: Optional[str] = None
    gamma_url: Optional[str] = None
    pptx_url: Optional[str] = None
    pdf_url: Optional[str] = None
    credits_used: Optional[int] = None
    credits_remaining: Optional[int] = None
    error_message: Optional[str] = None
    status: GammaStatus = GammaStatus.PENDING


# ============================================================================
# Gamma Service
# ============================================================================


class GammaService:
    """
    Gamma.app API client for AI-powered presentation generation.

    This service transforms executive briefs into polished presentations
    using Gamma's AI capabilities including:
    - Intelligent content structuring
    - AI-generated images
    - Professional themes and layouts
    - Direct PPTX export
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Gamma service.

        Args:
            api_key: Gamma API key (defaults to GAMMA_API_KEY env var)
        """
        self.api_key = api_key or GAMMA_API_KEY
        self.enabled = GAMMA_API_ENABLED and bool(self.api_key)

        if self.enabled:
            logger.info("GammaService initialized with API key")
        else:
            logger.warning("GammaService disabled - no API key configured")

    def is_available(self) -> bool:
        """Check if Gamma API is available for use."""
        return self.enabled

    async def generate_presentation(
        self,
        title: str,
        executive_summary: str,
        content_markdown: str,
        classification: Optional[Dict[str, str]] = None,
        num_slides: int = 8,
        include_images: bool = True,
        export_format: str = "pptx",
    ) -> GammaGenerationResult:
        """
        Generate an AI-powered presentation from brief content.

        Args:
            title: Presentation title
            executive_summary: Executive summary text
            content_markdown: Full brief content in markdown
            classification: Dict with pillar, horizon, stage
            num_slides: Target number of slides (8-12 recommended)
            include_images: Whether to generate AI images
            export_format: Export format ("pptx" or "pdf")

        Returns:
            GammaGenerationResult with generation status and URLs
        """
        if not self.enabled:
            return GammaGenerationResult(
                success=False,
                error_message="Gamma API not configured",
                status=GammaStatus.FAILED,
            )

        try:
            # Transform content for Gamma
            gamma_input = self._transform_brief_to_gamma_input(
                title=title,
                executive_summary=executive_summary,
                content_markdown=content_markdown,
                classification=classification,
            )

            # Build API request
            request_body = self._build_generation_request(
                input_text=gamma_input,
                num_cards=num_slides,
                include_images=include_images,
                export_format=export_format,
                classification=classification,
            )

            logger.info(f"Sending Gamma generation request for: {title}")

            # Submit generation request
            async with httpx.AsyncClient(timeout=GAMMA_REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{GAMMA_API_BASE_URL}/generations",
                    json=request_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-KEY": self.api_key,
                    },
                )

                if response.status_code == 401:
                    return GammaGenerationResult(
                        success=False,
                        error_message="Invalid Gamma API key",
                        status=GammaStatus.FAILED,
                    )

                if response.status_code == 403:
                    return GammaGenerationResult(
                        success=False,
                        error_message="Gamma API credits exhausted",
                        status=GammaStatus.FAILED,
                    )

                # Gamma returns 201 Created for successful generation start
                if response.status_code not in (200, 201):
                    error_data = response.json() if response.text else {}
                    return GammaGenerationResult(
                        success=False,
                        error_message=f"Gamma API error: {error_data.get('message', response.status_code)}",
                        status=GammaStatus.FAILED,
                    )

                data = response.json()
                generation_id = data.get("generationId")

                if not generation_id:
                    return GammaGenerationResult(
                        success=False,
                        error_message="No generation ID returned",
                        status=GammaStatus.FAILED,
                    )

                logger.info(f"Gamma generation started: {generation_id}")

            return await self._poll_generation_status(generation_id)
        except httpx.TimeoutException:
            logger.error("Gamma API request timed out")
            return GammaGenerationResult(
                success=False,
                error_message="Gamma API request timed out",
                status=GammaStatus.TIMEOUT,
            )
        except Exception as e:
            logger.error(f"Gamma generation failed: {e}")
            return GammaGenerationResult(
                success=False, error_message=str(e), status=GammaStatus.FAILED
            )

    async def _poll_generation_status(
        self, generation_id: str
    ) -> GammaGenerationResult:
        """
        Poll Gamma API until generation is complete.

        Args:
            generation_id: The generation ID to poll

        Returns:
            Final GammaGenerationResult
        """
        async with httpx.AsyncClient(timeout=GAMMA_REQUEST_TIMEOUT) as client:
            for attempt in range(GAMMA_POLL_MAX_ATTEMPTS):
                try:
                    response = await client.get(
                        f"{GAMMA_API_BASE_URL}/generations/{generation_id}",
                        headers={
                            "X-API-KEY": self.api_key,
                            "accept": "application/json",
                        },
                    )

                    if response.status_code != 200:
                        logger.warning(f"Gamma poll returned {response.status_code}")
                        await asyncio.sleep(GAMMA_POLL_INTERVAL_SECONDS)
                        continue

                    data = response.json()
                    status = data.get("status", "pending")

                    if status == "completed":
                        logger.info(f"Gamma generation completed: {generation_id}")

                        # Extract file URLs if available
                        # Gamma returns exportUrl for the PPTX file
                        pptx_url = data.get("exportUrl") or data.get("pptxUrl")
                        pdf_url = data.get("pdfUrl")

                        credits_info = data.get("credits", {})

                        return GammaGenerationResult(
                            success=True,
                            generation_id=generation_id,
                            gamma_url=data.get("gammaUrl"),
                            pptx_url=pptx_url,
                            pdf_url=pdf_url,
                            credits_used=credits_info.get("deducted"),
                            credits_remaining=credits_info.get("remaining"),
                            status=GammaStatus.COMPLETED,
                        )

                    elif status == "failed":
                        return GammaGenerationResult(
                            success=False,
                            generation_id=generation_id,
                            error_message=data.get("error", "Generation failed"),
                            status=GammaStatus.FAILED,
                        )

                    # Still pending, wait and retry
                    await asyncio.sleep(GAMMA_POLL_INTERVAL_SECONDS)

                except Exception as e:
                    logger.warning(f"Gamma poll error (attempt {attempt + 1}): {e}")
                    await asyncio.sleep(GAMMA_POLL_INTERVAL_SECONDS)

            # Timeout
            logger.error(f"Gamma generation timed out: {generation_id}")
            return GammaGenerationResult(
                success=False,
                generation_id=generation_id,
                error_message="Generation timed out",
                status=GammaStatus.TIMEOUT,
            )

    async def download_export(self, url: str, timeout: int = 60) -> Optional[bytes]:
        """
        Download an exported file from Gamma.

        Args:
            url: The export URL (pptx or pdf)
            timeout: Download timeout in seconds

        Returns:
            File bytes or None if download fails
        """
        if not url:
            return None

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    return response.content
                logger.error(f"Failed to download Gamma export: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error downloading Gamma export: {e}")
            return None

    async def get_file_urls(self, generation_id: str) -> Dict[str, Optional[str]]:
        """
        Get export file URLs for a completed generation.

        Args:
            generation_id: The generation ID

        Returns:
            Dict with pptx_url and pdf_url
        """
        try:
            async with httpx.AsyncClient(timeout=GAMMA_REQUEST_TIMEOUT) as client:
                response = await client.get(
                    f"{GAMMA_API_BASE_URL}/generations/{generation_id}/files",
                    headers={"X-API-KEY": self.api_key, "accept": "application/json"},
                )

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "pptx_url": data.get("pptxUrl"),
                        "pdf_url": data.get("pdfUrl"),
                    }

        except Exception as e:
            logger.error(f"Error getting Gamma file URLs: {e}")

        return {"pptx_url": None, "pdf_url": None}

    def _transform_brief_to_gamma_input(
        self,
        title: str,
        executive_summary: str,
        content_markdown: str,
        classification: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Transform executive brief content into Gamma-optimized input.

        Creates structured content with section breaks (\n---\n) for
        optimal slide generation. Includes:
        - Title slide with visual tag badges
        - Content slides
        - AI disclosure slide
        - Backup/appendix slides explaining each classification tag

        Args:
            title: Presentation title
            executive_summary: Executive summary
            content_markdown: Full brief content
            classification: Classification metadata

        Returns:
            Transformed content string for Gamma API
        """
        # Track which tags are used for backup slides
        used_pillar = None
        used_horizon = None
        used_stage = None

        # Slide 1: Title slide with visual tag badges
        title_section = f"# {title}\n"
        if classification:
            tag_lines = []
            if classification.get("pillar"):
                pillar = classification["pillar"].upper()
                pillar_def = PILLAR_DEFINITIONS.get(pillar, {})
                pillar_name = pillar_def.get("name", PILLAR_NAMES.get(pillar, pillar))
                pillar_icon = pillar_def.get("icon", "🏛️")
                tag_lines.append(f"{pillar_icon} **{pillar_name}**")
                used_pillar = pillar
            if classification.get("horizon"):
                horizon = classification["horizon"].upper()
                horizon_def = HORIZON_DEFINITIONS.get(horizon, {})
                horizon_name = horizon_def.get("name", horizon)
                horizon_icon = horizon_def.get("icon", "📅")
                tag_lines.append(f"{horizon_icon} **{horizon_name}**")
                used_horizon = horizon
            if classification.get("stage"):
                stage_raw = classification["stage"]
                if stage_match := re.search(r"(\d+)", str(stage_raw)):
                    stage_num = int(stage_match[1])
                    stage_def = STAGE_DEFINITIONS.get(stage_num, {})
                    stage_name = stage_def.get(
                        "name", STAGE_NAMES.get(stage_num, f"Stage {stage_num}")
                    )
                    stage_icon = stage_def.get("icon", "📊")
                    tag_lines.append(
                        f"{stage_icon} **Maturity Stage {stage_num}: {stage_name}**"
                    )
                    used_stage = stage_num
            if tag_lines:
                # Format tags as a visual row with separators
                title_section += "\n\n" + "  |  ".join(tag_lines)
        title_section += f"\n\nCity of Austin Strategic Intelligence Brief"
        title_section += f"\n{datetime.now(timezone.utc).strftime('%B %Y')}"
        sections = [title_section]
        # Slide 2: Executive Summary
        if executive_summary:
            summary_clean = self._clean_markdown(executive_summary)
            # Truncate if too long for a single slide
            if len(summary_clean) > 800:
                summary_clean = f"{summary_clean[:797]}..."
            sections.append(f"# Executive Summary\n\n{summary_clean}")

        # Parse main content into logical sections
        content_sections = self._parse_content_sections(content_markdown)

        for section_title, section_content in content_sections[
            :6
        ]:  # Max 6 content slides
            clean_content = self._clean_markdown(section_content)
            # Truncate long sections
            if len(clean_content) > 1000:
                clean_content = f"{clean_content[:997]}..."
            sections.append(f"# {section_title}\n\n{clean_content}")

        # AI Disclosure slide
        ai_disclosure = """# About This Report

This strategic intelligence brief was generated using the FORESIGHT platform, 
powered by advanced AI technologies:

- Anthropic Claude for strategic analysis and synthesis
- OpenAI GPT-4o for classification and scoring
- GPT Researcher for autonomous deep research
- Exa AI and Firecrawl for source discovery

The City of Austin is committed to transparent and responsible use of AI 
technology in public service."""
        sections.append(ai_disclosure)

        # =========================================================================
        # BACKUP/APPENDIX SLIDES - Explain each classification tag
        # =========================================================================

        # Appendix header slide
        appendix_header = """# Appendix: Classification Reference

The following slides provide context for the strategic classification tags 
used in this brief. These definitions help ensure consistent understanding 
across City departments and leadership."""
        sections.append(appendix_header)

        # Pillar backup slide
        if used_pillar and used_pillar in PILLAR_DEFINITIONS:
            pillar_def = PILLAR_DEFINITIONS[used_pillar]
            pillar_slide = f"""# {pillar_def['icon']} Strategic Pillar: {pillar_def['name']}

**Definition:** {pillar_def['description']}

**Focus Areas:**
"""
            for area in pillar_def.get("focus_areas", []):
                pillar_slide += f"- {area}\n"

            pillar_slide += """
This pillar is one of six strategic focus areas guiding City of Austin 
planning and investment decisions."""
            sections.append(pillar_slide)

        # Horizon backup slide
        if used_horizon and used_horizon in HORIZON_DEFINITIONS:
            horizon_def = HORIZON_DEFINITIONS[used_horizon]
            horizon_slide = f"""# {horizon_def['icon']} Planning Horizon: {horizon_def['name']}

**Timeframe:** {horizon_def['timeframe']}

**Definition:** {horizon_def['description']}

**Characteristics:**
"""
            for char in horizon_def.get("characteristics", []):
                horizon_slide += f"- {char}\n"

            horizon_slide += """
The planning horizon indicates when this trend is expected to require 
significant City attention or action."""
            sections.append(horizon_slide)

        # Stage backup slide
        if used_stage and used_stage in STAGE_DEFINITIONS:
            stage_def = STAGE_DEFINITIONS[used_stage]
            stage_slide = f"""# {stage_def['icon']} Maturity Stage {used_stage}: {stage_def['name']}

**Definition:** {stage_def['description']}

**Key Indicators:**
"""
            for indicator in stage_def.get("indicators", []):
                stage_slide += f"- {indicator}\n"

            stage_slide += """
The maturity stage reflects the current development status of this trend 
and helps inform appropriate City response strategies."""
            sections.append(stage_slide)

        # Join with Gamma's section break marker
        return "\n---\n".join(sections)

    def _parse_content_sections(self, content_markdown: str) -> List[Tuple[str, str]]:
        """
        Parse markdown content into sections based on headers.

        Args:
            content_markdown: Raw markdown content

        Returns:
            List of (title, content) tuples
        """
        sections = []
        current_title = "Overview"
        current_content = []

        lines = content_markdown.split("\n")

        for line in lines:
            if header_match := re.match(r"^(#{1,3})\s+(.+)$", line):
                # Save previous section
                if current_content:
                    content_text = "\n".join(current_content).strip()
                    if content_text and len(content_text) > 50:  # Skip tiny sections
                        sections.append((current_title, content_text))

                current_title = header_match[2].strip()
                current_content = []
            else:
                current_content.append(line)

        # Don't forget the last section
        if current_content:
            content_text = "\n".join(current_content).strip()
            if content_text and len(content_text) > 50:
                sections.append((current_title, content_text))

        # If no sections found, create one from all content
        if not sections and content_markdown.strip():
            sections = [("Key Findings", content_markdown.strip())]

        return sections

    def _clean_markdown(self, text: str) -> str:
        """
        Clean markdown for Gamma input.

        Gamma handles markdown well, but we clean up some artifacts
        that might cause issues.

        Args:
            text: Raw markdown text

        Returns:
            Cleaned text
        """
        if not text:
            return ""

        # Remove excessive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)

        # Remove code blocks (Gamma doesn't render these well in presentations)
        text = re.sub(r"```[\s\S]*?```", "", text)

        # Clean up bullet points to standard format
        text = re.sub(r"^[•●○]\s+", "- ", text, flags=re.MULTILINE)

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        return text.strip()

    def _build_generation_request(
        self,
        input_text: str,
        num_cards: int = 8,
        include_images: bool = True,
        export_format: str = "pptx",
        classification: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Build the Gamma API request body.

        Args:
            input_text: Transformed content for Gamma
            num_cards: Number of slides
            include_images: Whether to generate AI images
            export_format: Export format
            classification: Classification for additional context

        Returns:
            Request body dict
        """
        # Build comprehensive instructions (max 2000 chars for Gamma API)
        # Using full character budget for detailed styling guidance
        instructions = """
Executive strategic intelligence briefing for City of Austin senior leadership.

OFFICIAL CITY OF AUSTIN BRAND COLORS (MUST USE):
- Primary headers/titles: Logo Blue #44499C
- Highlights/callouts/positive: Logo Green #009F4D
- Backgrounds: Faded White #f7f6f5 or pure white
- Emphasis text: Dark Blue #22254E
- Body text: Dark Gray #636262
- Subtle backgrounds: Light Blue #dcf2fd, Light Green #dff0e3
- Risk/negative indicators: Red #F83125
- Opportunity indicators: Logo Green #009F4D

VISUAL DESIGN REQUIREMENTS:
- Clean, modern, professional government aesthetic
- Generous white space - avoid cluttered slides
- Large readable fonts: 28pt+ for headers, 24pt+ for body
- Classification tags as polished pill-shaped badges on title slide
- Consistent visual hierarchy throughout

DATA VISUALIZATION:
- Charts use Logo Blue #44499C and Logo Green #009F4D as primary colors
- ALL charts MUST have clearly labeled axes with descriptive titles and units
- Include data labels on key points
- Use Red #F83125 for risks/concerns, Green #009F4D for opportunities

PRESENTATION STRUCTURE:
1. Title slide with bold title and classification badge pills
2. Executive Summary: 3-5 key strategic takeaways
3. Background/Context slide
4. Key Findings (2-3 slides, one main idea per slide)
5. Strategic Implications for Austin
6. Opportunities & Risks analysis
7. Recommended Actions / Next Steps
8. Appendix: Classification definitions

CONTENT APPROACH:
- "So What?" framing - connect everything to municipal impact
- Authoritative but accessible language
- Action-oriented recommendations
- Avoid jargon - explain technical concepts simply
"""

        # Determine optimal slide count based on content length
        content_length = len(input_text)
        if content_length > 8000:
            optimal_slides = GAMMA_MAX_SLIDES
        elif content_length > 4000:
            optimal_slides = GAMMA_DEFAULT_SLIDES
        else:
            optimal_slides = GAMMA_MIN_SLIDES

        # Use provided num_cards or calculated optimal
        final_num_cards = max(num_cards, optimal_slides)

        request = {
            "inputText": input_text,
            "textMode": "condense",
            "format": "presentation",
            "numCards": final_num_cards,
            "cardSplit": "auto",  # Let Gamma intelligently split based on numCards
            "additionalInstructions": instructions.strip(),
            "exportAs": export_format,
            "textOptions": {
                "amount": "detailed",  # More detailed content for executive briefs
                # tone: max 500 chars - using full budget for precise guidance
                "tone": "professional, authoritative, strategic, confident, clear, action-oriented, forward-looking, executive-level, decisive, informed",
                # audience: max 500 chars - detailed audience description
                "audience": "City Manager, Assistant City Managers, Department Directors, Division Managers, and senior municipal executives responsible for strategic planning, policy decisions, budget allocation, and long-term city initiatives. Decision-makers who need actionable intelligence.",
                "language": "en",
            },
            "cardOptions": {
                "dimensions": "16x9",
                "headerFooter": {
                    "topRight": {
                        "type": "image",
                        "source": "custom",
                        "src": COA_LOGO_HORIZONTAL,
                        "size": "md",
                    },
                    "bottomLeft": {
                        "type": "text",
                        "value": "City of Austin | FORESIGHT Strategic Intelligence",
                    },
                    "bottomRight": {"type": "cardNumber"},
                    "hideFromFirstCard": True,
                    "hideFromLastCard": False,
                },
            },
            "sharingOptions": {"workspaceAccess": "view", "externalAccess": "noAccess"},
        }

        # Add theme if configured (for consistent branding across all presentations)
        if GAMMA_THEME_ID:
            request["themeId"] = GAMMA_THEME_ID

        # Add folder if configured (organize all FORESIGHT briefs together)
        if GAMMA_FOLDER_ID:
            request["folderIds"] = [GAMMA_FOLDER_ID]

        # Configure image options for high-quality visuals
        # imageOptions.style: max 500 chars - detailed visual style guidance
        if include_images:
            request["imageOptions"] = {
                "source": "aiGenerated",
                "model": "imagen-4-pro",
                # style: max 500 chars - using full budget for precise visual direction
                "style": "professional photography, clean modern corporate design, sophisticated minimalist aesthetic, high-quality editorial imagery, suitable for government executive presentations, contemporary urban planning visuals, technology and innovation themes, civic infrastructure, blue and green color accents matching City of Austin brand",
            }
        else:
            request["imageOptions"] = {"source": "noImages"}

        return request


# ============================================================================
# Convenience Functions
# ============================================================================


def is_gamma_available() -> bool:
    """Check if Gamma API is configured and available."""
    return GAMMA_API_ENABLED and bool(GAMMA_API_KEY)


async def generate_gamma_presentation(
    title: str,
    executive_summary: str,
    content_markdown: str,
    classification: Optional[Dict[str, str]] = None,
    num_slides: int = 8,
    include_images: bool = True,
) -> GammaGenerationResult:
    """
    Convenience function to generate a presentation via Gamma.

    Args:
        title: Presentation title
        executive_summary: Executive summary
        content_markdown: Full brief content
        classification: Classification metadata
        num_slides: Target slide count
        include_images: Whether to include AI images

    Returns:
        GammaGenerationResult
    """
    service = GammaService()
    return await service.generate_presentation(
        title=title,
        executive_summary=executive_summary,
        content_markdown=content_markdown,
        classification=classification,
        num_slides=num_slides,
        include_images=include_images,
    )


# =============================================================================
# Portfolio/Bulk Export Support
# =============================================================================


@dataclass
class PortfolioCard:
    """Card data for portfolio presentation."""

    card_id: str
    card_name: str
    pillar_id: str
    horizon: str
    stage_id: str
    brief_summary: str
    brief_content: str  # Truncated for slides
    impact_score: int
    relevance_score: int


@dataclass
class PortfolioSynthesisData:
    """Pre-computed synthesis data for portfolio."""

    executive_overview: str
    key_themes: List[str]
    priority_matrix: Dict[str, Any]
    cross_cutting_insights: List[str]
    recommended_actions: List[Dict[str, str]]
    # Enhanced fields for executive presentations
    urgency_statement: str = ""
    implementation_guidance: Dict[str, List[str]] = None
    ninety_day_actions: List[Dict[str, str]] = None
    risk_summary: str = ""
    opportunity_summary: str = ""

    def __post_init__(self):
        if self.implementation_guidance is None:
            self.implementation_guidance = {}
        if self.ninety_day_actions is None:
            self.ninety_day_actions = []


def calculate_slides_per_card(card_count: int) -> int:
    """
    Calculate optimal slides per card based on total card count.

    Keeps total under 55 slides (buffer for Gamma's 60 limit).

    Args:
        card_count: Number of cards in portfolio

    Returns:
        Slides to allocate per card (2-4)
    """
    # Fixed slides: title(1) + overview(1) + priority(1) + themes(1) + actions(1) + disclosure(1) = 6
    fixed_slides = 6
    max_total = 55
    available_for_cards = max_total - fixed_slides

    if card_count <= 3:
        return 4  # Detailed treatment
    elif card_count <= 7:
        return 3  # Standard portfolio
    else:
        return 2  # Condensed


class GammaPortfolioService:
    """
    Generates portfolio presentations via Gamma API.

    Different from single-brief generation - uses portfolio-specific
    prompts and multi-card structure.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GAMMA_API_KEY
        self.enabled = GAMMA_API_ENABLED and bool(self.api_key)

    def is_available(self) -> bool:
        return self.enabled

    async def generate_portfolio_presentation(
        self,
        workstream_name: str,
        cards: List[PortfolioCard],
        synthesis: PortfolioSynthesisData,
        include_images: bool = True,
        export_format: str = "pptx",
    ) -> GammaGenerationResult:
        """
        Generate a portfolio presentation from multiple briefs.

        Args:
            workstream_name: Name of the workstream
            cards: List of PortfolioCard objects in display order
            synthesis: Pre-computed portfolio synthesis from AI
            include_images: Whether to generate AI images
            export_format: Export format ("pptx" or "pdf")

        Returns:
            GammaGenerationResult with presentation URL
        """
        if not self.enabled:
            return GammaGenerationResult(
                success=False,
                error_message="Gamma API not configured",
                status=GammaStatus.FAILED,
            )

        if not cards:
            return GammaGenerationResult(
                success=False,
                error_message="No cards provided for portfolio",
                status=GammaStatus.FAILED,
            )

        try:
            # Build portfolio content
            portfolio_content = self._build_portfolio_content(
                workstream_name=workstream_name, cards=cards, synthesis=synthesis
            )

            # Calculate slide count: 10 fixed slides + 3 per card
            fixed_slides = 10  # Title, Dashboard, Urgency, Overview, Priority, Implementation, Themes, 90-day, Risks, Disclosure
            slides_per_card = 3  # Overview, What's Happening, Austin Implications
            total_slides = fixed_slides + (len(cards) * slides_per_card)

            # Build request
            request_body = self._build_portfolio_request(
                input_text=portfolio_content,
                num_cards=min(total_slides, 60),  # Gamma supports up to 60 for Pro
                include_images=include_images,
                export_format=export_format,
                card_count=len(cards),
                workstream_name=workstream_name,
            )

            logger.info(
                f"Generating portfolio presentation: {workstream_name} ({len(cards)} cards, ~{total_slides} slides)"
            )

            # Submit to Gamma
            async with httpx.AsyncClient(timeout=GAMMA_REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{GAMMA_API_BASE_URL}/generations",
                    json=request_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-KEY": self.api_key,
                    },
                )

                if response.status_code == 401:
                    return GammaGenerationResult(
                        success=False,
                        error_message="Invalid Gamma API key",
                        status=GammaStatus.FAILED,
                    )

                if response.status_code == 403:
                    return GammaGenerationResult(
                        success=False,
                        error_message="Gamma API credits exhausted",
                        status=GammaStatus.FAILED,
                    )

                if response.status_code not in (200, 201):
                    error_data = response.json() if response.text else {}
                    return GammaGenerationResult(
                        success=False,
                        error_message=f"Gamma API error: {error_data.get('message', response.status_code)}",
                        status=GammaStatus.FAILED,
                    )

                data = response.json()
                generation_id = data.get("generationId")

                if not generation_id:
                    return GammaGenerationResult(
                        success=False,
                        error_message="No generation ID returned",
                        status=GammaStatus.FAILED,
                    )

                logger.info(f"Gamma portfolio generation started: {generation_id}")

            # Poll for completion (reuse existing polling logic)
            gamma_service = GammaService(self.api_key)
            return await gamma_service._poll_generation_status(generation_id)
        except Exception as e:
            logger.error(f"Portfolio generation error: {e}")
            return GammaGenerationResult(
                success=False, error_message=str(e), status=GammaStatus.FAILED
            )

    def _build_portfolio_content(
        self,
        workstream_name: str,
        cards: List[PortfolioCard],
        synthesis: PortfolioSynthesisData,
    ) -> str:
        """
        Build Gamma-optimized content for portfolio presentation.

        Enhanced structure (~10 fixed slides + 3 per card):
        1. Title slide
        2. Portfolio at a Glance (dashboard metrics)
        3. Why This Matters Now (urgency hook)
        4. Executive Overview
        5. Priority Matrix
        6. Implementation Guidance
        7-N. Per-card deep dives (3 slides each)
        N+1. Cross-cutting themes
        N+2. 90-Day Action Plan
        N+3. Risks & Opportunities
        N+4. AI Disclosure
        """
        # Collect pillar info
        pillar_icons = []
        pillar_names_used = []
        for card in cards:
            pillar_def = PILLAR_DEFINITIONS.get(
                card.pillar_id.upper() if card.pillar_id else "", {}
            )
            icon = pillar_def.get("icon", "🏛️")
            name = pillar_def.get("name", card.pillar_id or "Strategic")
            if icon not in pillar_icons:
                pillar_icons.append(icon)
                pillar_names_used.append(name)

        # Calculate metrics for dashboard
        avg_impact = sum(c.impact_score for c in cards if c.impact_score) // max(
            len(cards), 1
        )
        avg_relevance = sum(
            c.relevance_score for c in cards if c.relevance_score
        ) // max(len(cards), 1)
        horizons_covered = sorted({c.horizon for c in cards if c.horizon})

        # ===== SLIDE 1: Title =====
        title_section = f"""# {workstream_name}

**Strategic Intelligence Portfolio**

{' '.join(pillar_icons)} | {len(cards)} Strategic Trends | {', '.join(pillar_names_used)}

City of Austin | FORESIGHT Platform
{datetime.now(timezone.utc).strftime('%B %Y')}"""
        sections = [title_section]
        # ===== SLIDE 2: Portfolio at a Glance =====
        dashboard_section = f"""# Portfolio at a Glance

**{len(cards)}** Strategic Trends Analyzed

**{len(pillar_names_used)}** Strategic Pillars: {', '.join(pillar_names_used)}

**{', '.join(horizons_covered) if horizons_covered else 'Mixed'}** Time Horizons

**{avg_impact}/100** Average Impact Score | **{avg_relevance}/100** Average Relevance

This portfolio synthesizes deep research across multiple emerging trends to provide actionable strategic guidance."""
        sections.append(dashboard_section)

        # ===== SLIDE 3: Why This Matters Now =====
        urgency = (
            synthesis.urgency_statement
            or f"These {len(cards)} trends represent critical opportunities and challenges that will shape Austin's future. Early action positions the city as a leader; delay risks falling behind peer cities."
        )

        urgency_section = f"""# Why This Matters Now

{urgency}

**The Window of Opportunity**

Cities that move first on emerging trends gain competitive advantage in talent attraction, federal funding, and citizen satisfaction. This portfolio identifies where Austin should act decisively."""
        sections.append(urgency_section)

        # ===== SLIDE 4: Executive Overview =====
        overview_section = f"""# Executive Overview

{synthesis.executive_overview}"""
        sections.append(overview_section)

        # ===== SLIDE 5: Priority Matrix =====
        matrix = synthesis.priority_matrix or {}
        urgent = matrix.get("high_impact_urgent", [])
        strategic = matrix.get("high_impact_strategic", [])
        monitor = matrix.get("monitor", [])

        priority_section = f"""# Strategic Priority Matrix

**🔴 HIGH IMPACT - ACT NOW**
{chr(10).join(f'• {item}' for item in urgent) if urgent else '• Assessment in progress'}

**🟡 HIGH IMPACT - PLAN STRATEGICALLY**
{chr(10).join(f'• {item}' for item in strategic) if strategic else '• Assessment in progress'}

**🟢 MONITOR & EVALUATE**
{chr(10).join(f'• {item}' for item in monitor) if monitor else '• Assessment in progress'}

*{matrix.get('rationale', 'Prioritization based on impact potential, implementation readiness, and resource requirements.')}*"""
        sections.append(priority_section)

        # ===== SLIDE 6: Implementation Guidance =====
        impl = synthesis.implementation_guidance or {}
        pilot_now = impl.get("pilot_now", [])
        investigate = impl.get("investigate_further", [])
        vendors = impl.get("meet_with_vendors", [])
        policy = impl.get("policy_review", [])
        training = impl.get("staff_training", [])
        budget = impl.get("budget_planning", [])

        impl_lines = []
        if pilot_now:
            impl_lines.append(f"**🚀 Ready to Pilot**: {', '.join(pilot_now)}")
        if investigate:
            impl_lines.append(f"**🔍 Investigate Further**: {', '.join(investigate)}")
        if vendors:
            impl_lines.append(f"**🤝 Meet with Vendors**: {', '.join(vendors)}")
        if policy:
            impl_lines.append(f"**📋 Policy Review Needed**: {', '.join(policy)}")
        if training:
            impl_lines.append(f"**👥 Staff Training Focus**: {', '.join(training)}")
        if budget:
            impl_lines.append(f"**💰 Budget Planning**: {', '.join(budget)}")

        impl_content = (
            chr(10).join(impl_lines)
            if impl_lines
            else "Implementation guidance will be refined based on leadership priorities."
        )

        impl_section = f"""# Implementation Guidance

What should Austin DO with each trend?

{impl_content}

*Each recommendation reflects the trend's maturity, Austin's readiness, and resource requirements.*"""
        sections.append(impl_section)

        # ===== SLIDES 7+: Per-card deep dives (3 slides each) =====
        for i, card in enumerate(cards, 1):
            pillar_def = PILLAR_DEFINITIONS.get(
                card.pillar_id.upper() if card.pillar_id else "", {}
            )
            pillar_name = pillar_def.get("name", card.pillar_id or "Strategic")
            pillar_icon = pillar_def.get("icon", "🏛️")

            horizon_def = HORIZON_DEFINITIONS.get(
                card.horizon.upper() if card.horizon else "H2", {}
            )
            horizon_name = horizon_def.get("name", card.horizon or "Medium-term")
            horizon_icon = horizon_def.get("icon", "📅")

            stage_match = (
                re.search(r"(\d+)", str(card.stage_id)) if card.stage_id else None
            )
            stage_num = int(stage_match.group(1)) if stage_match else None
            stage_def = STAGE_DEFINITIONS.get(stage_num, {}) if stage_num else {}
            stage_name = stage_def.get("name", "Emerging")

            # Build score line only if we have scores
            score_parts = []
            if card.impact_score and card.impact_score > 0:
                score_parts.append(f"Impact: {card.impact_score}/100")
            if card.relevance_score and card.relevance_score > 0:
                score_parts.append(f"Relevance: {card.relevance_score}/100")
            score_line = " | ".join(score_parts) if score_parts else ""

            # CARD SLIDE 1: Overview
            card_overview = f"""# {i}. {card.card_name}

{pillar_icon} **{pillar_name}** | {horizon_icon} **{horizon_name}** | 📊 **{stage_name}**

{f'**{score_line}**' if score_line else ''}

{card.brief_summary}"""
            sections.append(card_overview)

            # CARD SLIDE 2: What's Happening
            # Extract key developments from brief content
            content_preview = (
                card.brief_content[:800] if card.brief_content else card.brief_summary
            )

            developments_section = f"""# {card.card_name}: What's Happening

{content_preview}

**Key Developments**: This trend is gaining momentum across multiple sectors, with implications for city services, infrastructure, and resident experience."""
            sections.append(developments_section)

            # CARD SLIDE 3: Austin Implications
            austin_section = f"""# {card.card_name}: Austin Implications

**Strategic Considerations for Austin**

• How does this trend align with Austin's strategic priorities?
• What peer cities are already moving on this?
• What resources would Austin need to act?
• What are the risks of inaction?

*Detailed analysis and recommendations available in the full executive brief.*"""
            sections.append(austin_section)

        # ===== SLIDE N+1: Cross-cutting Themes =====
        themes_content = (
            chr(10).join(f"• {theme}" for theme in synthesis.key_themes)
            if synthesis.key_themes
            else "• Themes being analyzed"
        )
        insights_content = (
            chr(10).join(f"• {insight}" for insight in synthesis.cross_cutting_insights)
            if synthesis.cross_cutting_insights
            else "• Connections being identified"
        )

        themes_section = f"""# Cross-Cutting Themes

**Common Patterns Across Trends**
{themes_content}

**Strategic Connections**
{insights_content}

*These themes suggest opportunities for coordinated initiatives across multiple trends.*"""
        sections.append(themes_section)

        actions_list = []
        if ninety_day := synthesis.ninety_day_actions or []:
            for action in ninety_day[:5]:
                action_text = action.get("action", "")
                owner = action.get("owner", "TBD")
                by_when = action.get("by_when", "90 days")
                metric = action.get("success_metric", "")
                actions_list.append(
                    f"**{action_text}**\n  • Owner: {owner} | By: {by_when}\n  • Success: {metric}"
                )
            ninety_day_content = chr(10).join(actions_list)
        else:
            for action in synthesis.recommended_actions[:5]:
                action_text = action.get("action", "")
                owner = action.get("owner", "TBD")
                timeline = action.get("timeline", "TBD")
                actions_list.append(
                    f"**{action_text}**\n  • Owner: {owner} | Timeline: {timeline}"
                )
            ninety_day_content = (
                chr(10).join(actions_list)
                if actions_list
                else "Action plan to be developed based on leadership priorities."
            )

        actions_section = f"""# 90-Day Action Plan

What Austin should do in the next 90 days:

{ninety_day_content}

*Actions sequenced by quick wins, dependencies, and resource availability.*"""
        sections.append(actions_section)

        # ===== SLIDE N+3: Risks & Opportunities =====
        risk_text = (
            synthesis.risk_summary
            or "Delayed action on these trends could result in Austin falling behind peer cities, missing federal funding windows, and losing competitive advantage in talent and business attraction."
        )
        opp_text = (
            synthesis.opportunity_summary
            or "Early action positions Austin as a national leader, attracts innovation investment, and delivers improved services to residents ahead of demand curves."
        )

        risk_opp_section = f"""# Risks & Opportunities

**⚠️ If Austin Doesn't Act**
{risk_text}

**✨ If Austin Leads**
{opp_text}

*The strategic choice is clear: proactive investment in emerging trends yields compounding returns.*"""
        sections.append(risk_opp_section)

        # ===== SLIDE N+4: AI Disclosure =====
        disclosure_section = """# About This Portfolio

This strategic intelligence portfolio was generated using the FORESIGHT platform:

• **AI Analysis**: Anthropic Claude & OpenAI GPT-4
• **Presentation**: Gamma.app AI
• **Deep Research**: GPT Researcher with Exa AI & Tavily
• **Source Discovery**: Firecrawl web extraction

The City of Austin is committed to transparent and responsible use of AI in public service. All AI-generated content is reviewed for accuracy and relevance.

*Full executive briefs and source materials available in the FORESIGHT platform.*"""
        sections.append(disclosure_section)

        return "\n---\n".join(sections)

    def _build_portfolio_request(
        self,
        input_text: str,
        num_cards: int,
        include_images: bool,
        export_format: str,
        card_count: int,
        workstream_name: str = "Strategic Portfolio",
    ) -> Dict[str, Any]:
        """Build Gamma API request for portfolio presentation."""

        # Portfolio-specific instructions - enhanced for executive quality
        instructions = f"""
EXECUTIVE PORTFOLIO DECK for City of Austin senior leadership.
This is a {card_count}-trend strategic intelligence portfolio requiring PREMIUM quality.

SLIDE STRUCTURE (follow the section breaks exactly):
1. Title: Bold, impactful, professional
2. Portfolio at a Glance: Dashboard-style metrics display
3. Why This Matters Now: Urgency hook - make leadership pay attention
4. Executive Overview: Synthesized insights across all trends
5. Priority Matrix: Visual 2x2 categorization (use colored quadrants if possible)
6. Implementation Guidance: Clear action categories with icons
7-N. Per-Trend Deep Dives (3 slides each):
   - Overview with classification badges
   - What's Happening with key developments
   - Austin Implications with strategic questions
N+1. Cross-Cutting Themes: Pattern recognition
N+2. 90-Day Action Plan: Concrete near-term steps
N+3. Risks & Opportunities: Dual framing
N+4. AI Disclosure: Transparency

VISUAL DESIGN (City of Austin Official Brand):
- Primary headers: #44499C (Logo Blue)
- Positive highlights: #009F4D (Logo Green)  
- Backgrounds: White or #f7f6f5 (Faded White)
- Urgent/Risk items: #F83125 (Red)
- Strategic/Planning: #FFC600 (Yellow/Amber)
- Monitor items: #009CDE (Cyan)
- Text: #636262 (Dark Gray) or #22254E (Dark Blue)

EXECUTIVE PRESENTATION STANDARDS:
- One key message per slide maximum
- Bullet points: 4-5 max per section
- Headlines should be actionable ("Act Now on X" not "About X")
- Use icons and visual hierarchy
- Classification badges should be color-coded pills/tags
- Score metrics should be visual (gauges or progress indicators)
- Action items need clear ownership and timelines

CONTENT TONE:
- Authoritative but accessible
- Data-driven with clear implications
- Action-oriented: "What should Austin DO?"
- Comparative: How does Austin compare to peer cities?
- Forward-looking: Window of opportunity framing

Create a presentation that a City Manager would proudly share with Council."""

        request = {
            "inputText": input_text,
            "textMode": "condense",  # Let Gamma optimize content for slides
            "format": "presentation",
            "numCards": num_cards,
            "cardSplit": "inputTextBreaks",  # Respect our section breaks
            "additionalInstructions": instructions.strip(),
            "exportAs": export_format,
            "textOptions": {
                "amount": "detailed",  # More content per slide
                "tone": "authoritative, executive, strategic, data-driven, action-oriented",
                "audience": "City Manager, Mayor, City Council Members, Department Directors - senior government executives making multi-million dollar strategic decisions about emerging technologies and municipal innovation",
                "language": "en",
            },
            "cardOptions": {
                "dimensions": "16x9",
                "headerFooter": {
                    "topLeft": {"type": "text", "value": workstream_name[:35]},
                    "topRight": {
                        "type": "image",
                        "source": "custom",
                        "src": COA_LOGO_HORIZONTAL,
                        "size": "md",
                    },
                    "bottomLeft": {
                        "type": "text",
                        "value": "FORESIGHT Strategic Intelligence",
                    },
                    "bottomRight": {"type": "cardNumber"},
                    "hideFromFirstCard": True,
                    "hideFromLastCard": False,
                },
            },
            "sharingOptions": {"workspaceAccess": "view", "externalAccess": "noAccess"},
        }

        # Add theme if configured (theme IDs are UUIDs from Gamma workspace)
        if GAMMA_THEME_ID:
            request["themeId"] = GAMMA_THEME_ID
        # If no theme configured, Gamma will use its default theme

        # Add folder if configured
        if GAMMA_FOLDER_ID:
            request["folderIds"] = [GAMMA_FOLDER_ID]

        # Enhanced image options for executive quality
        if include_images:
            request["imageOptions"] = {
                "source": "aiGenerated",
                "model": "imagen-4-pro",  # Highest quality model
                "style": "premium executive photography, clean minimalist corporate design, municipal government imagery, smart city technology, urban innovation, professional blue and green color palette, editorial quality, strategic planning visuals, data visualization aesthetics, modern Austin Texas cityscape",
            }
        else:
            request["imageOptions"] = {"source": "noImages"}

        return request


async def generate_portfolio_presentation(
    workstream_name: str,
    cards: List[PortfolioCard],
    synthesis: PortfolioSynthesisData,
    include_images: bool = True,
) -> GammaGenerationResult:
    """
    Convenience function to generate a portfolio presentation.

    Args:
        workstream_name: Workstream name for title
        cards: List of PortfolioCard objects
        synthesis: Pre-computed synthesis data
        include_images: Whether to include AI images

    Returns:
        GammaGenerationResult
    """
    service = GammaPortfolioService()
    return await service.generate_portfolio_presentation(
        workstream_name=workstream_name,
        cards=cards,
        synthesis=synthesis,
        include_images=include_images,
    )
