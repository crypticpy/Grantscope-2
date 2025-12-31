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
from datetime import datetime
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

# Polling configuration
GAMMA_POLL_INTERVAL_SECONDS = 3
GAMMA_POLL_MAX_ATTEMPTS = 60  # 3 minutes max wait time
GAMMA_REQUEST_TIMEOUT = 30

# Default branding - City of Austin logos hosted on Dropbox
FORESIGHT_BRANDING = "FORESIGHT Strategic Intelligence Platform"
COA_LOGO_HORIZONTAL = os.getenv(
    "COA_LOGO_HORIZONTAL",
    "https://dl.dropboxusercontent.com/scl/fi/vtmgwhrila35a9gcthuh0/COA-Logo-Horizontal-Official-RGB.png?rlkey=xj2s6muc7r4dkjb3lrn72dywt"
)
COA_LOGO_CIRCLE = os.getenv(
    "COA_LOGO_CIRCLE", 
    "https://dl.dropboxusercontent.com/scl/fi/s23pczc5japf6w2l5lj7c/COA-Official-Circle.png?rlkey=zijpoik2f5qesjasgr7ii6afy"
)
# Backwards compatibility
COA_LOGO_URL = COA_LOGO_HORIZONTAL

# Official City of Austin Brand Colors
COA_COLORS = {
    # Official Palette
    "logo_blue": "#44499C",      # Primary - headers, titles, accents
    "logo_green": "#009F4D",     # Secondary - highlights, positive indicators
    "faded_white": "#f7f6f5",    # Backgrounds
    # Supporting Palette
    "compliant_green": "#008743",
    "dark_blue": "#22254E",      # Emphasis text
    "dark_green": "#005027",
    "light_blue": "#dcf2fd",     # Subtle backgrounds
    "light_green": "#dff0e3",    # Callout boxes
    # Extended Palette
    "red": "#F83125",            # Risks, concerns
    "orange": "#FF8F00",
    "yellow": "#FFC600",
    "cyan": "#009CDE",
    "purple": "#9F3CC9",
    "light_gray": "#C6C5C4",
    "brown": "#8F5201",
    "dark_gray": "#636262",      # Body text
    "black": "#000000",
}

# Classification data for slide context (matches database pillars table)
PILLAR_NAMES = {
    "CH": "Community Health",
    "MC": "Mobility & Connectivity",
    "HS": "Housing & Economic Stability",
    "EC": "Economic Development",
    "ES": "Environmental Sustainability",
    "CE": "Cultural & Entertainment",
}

# Extended pillar definitions for backup slides
PILLAR_DEFINITIONS = {
    "CH": {
        "name": "Community Health",
        "icon": "🏥",
        "description": "Promoting physical, mental, and social well-being for all Austinites",
        "focus_areas": [
            "Health equity and access to services",
            "Preventive health and early intervention",
            "Mental health resources and support",
            "Healthy environments for physical activity",
            "Public health emergency preparedness"
        ]
    },
    "MC": {
        "name": "Mobility & Connectivity",
        "icon": "🚇",
        "description": "Ensuring accessible, sustainable, and efficient transportation options",
        "focus_areas": [
            "Public transit accessibility",
            "Bike lanes and pedestrian infrastructure",
            "Traffic management and congestion reduction",
            "Smart transportation technology",
            "Regional connectivity"
        ]
    },
    "HS": {
        "name": "Housing & Economic Stability",
        "icon": "🏠",
        "description": "Creating affordable housing and economic opportunities for residents",
        "focus_areas": [
            "Affordable housing supply",
            "Housing quality and safety",
            "Economic mobility pathways",
            "Homelessness prevention and solutions",
            "Workforce housing"
        ]
    },
    "EC": {
        "name": "Economic Development",
        "icon": "📈",
        "description": "Fostering innovation, entrepreneurship, and business growth",
        "focus_areas": [
            "Local business development and retention",
            "Technology innovation ecosystem",
            "Workforce development programs",
            "Economic resilience planning",
            "Small business support"
        ]
    },
    "ES": {
        "name": "Environmental Sustainability",
        "icon": "🌱",
        "description": "Protecting and enhancing Austin's natural environment",
        "focus_areas": [
            "Climate action and emissions reduction",
            "Water and energy conservation",
            "Green infrastructure development",
            "Natural resource protection",
            "Sustainable development practices"
        ]
    },
    "CE": {
        "name": "Cultural & Entertainment",
        "icon": "🎭",
        "description": "Preserving Austin's unique culture and creative economy",
        "focus_areas": [
            "Arts and cultural programming",
            "Creative industry support",
            "Historic preservation",
            "Live music and entertainment venues",
            "Cultural diversity celebration"
        ]
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
            "Existing municipal precedents"
        ]
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
            "Early adopter municipalities seeing results"
        ]
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
            "Requires ongoing monitoring"
        ]
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
            "High uncertainty about viability"
        ]
    },
    2: {
        "name": "Exploring",
        "icon": "🔍",
        "description": "Initial research and experimentation phase",
        "indicators": [
            "Startups and research institutions active",
            "Early patents being filed",
            "Venture capital showing interest",
            "Small-scale experiments underway"
        ]
    },
    3: {
        "name": "Pilot",
        "icon": "🧪",
        "description": "Small-scale testing and validation",
        "indicators": [
            "Pilot programs in limited settings",
            "Early performance data available",
            "Technical feasibility demonstrated",
            "Identifying implementation challenges"
        ]
    },
    4: {
        "name": "Proof of Concept",
        "icon": "✅",
        "description": "Demonstrated viability with supporting evidence",
        "indicators": [
            "Successful pilots with measurable outcomes",
            "Multiple municipalities testing",
            "Vendor ecosystem developing",
            "Business case becoming clear"
        ]
    },
    5: {
        "name": "Implementing",
        "icon": "🏗️",
        "description": "Full-scale deployment underway",
        "indicators": [
            "Active implementation projects",
            "Established vendor relationships",
            "Documented best practices emerging",
            "Budget allocations secured"
        ]
    },
    6: {
        "name": "Scaling",
        "icon": "📊",
        "description": "Expanding reach and impact",
        "indicators": [
            "Widespread adoption beginning",
            "Economies of scale realized",
            "Integration with existing systems",
            "Proven return on investment"
        ]
    },
    7: {
        "name": "Mature",
        "icon": "🏆",
        "description": "Established and widely adopted",
        "indicators": [
            "Industry standard practice",
            "Commodity pricing available",
            "Well-understood implementation",
            "Focus shifts to optimization"
        ]
    },
    8: {
        "name": "Declining",
        "icon": "📉",
        "description": "Losing relevance or being replaced",
        "indicators": [
            "Newer alternatives emerging",
            "Decreasing vendor support",
            "Migration planning needed",
            "Legacy system considerations"
        ]
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
        export_format: str = "pptx"
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
                status=GammaStatus.FAILED
            )
        
        try:
            # Transform content for Gamma
            gamma_input = self._transform_brief_to_gamma_input(
                title=title,
                executive_summary=executive_summary,
                content_markdown=content_markdown,
                classification=classification
            )
            
            # Build API request
            request_body = self._build_generation_request(
                input_text=gamma_input,
                num_cards=num_slides,
                include_images=include_images,
                export_format=export_format,
                classification=classification
            )
            
            logger.info(f"Sending Gamma generation request for: {title}")
            
            # Submit generation request
            async with httpx.AsyncClient(timeout=GAMMA_REQUEST_TIMEOUT) as client:
                response = await client.post(
                    f"{GAMMA_API_BASE_URL}/generations",
                    json=request_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-API-KEY": self.api_key
                    }
                )
                
                if response.status_code == 401:
                    return GammaGenerationResult(
                        success=False,
                        error_message="Invalid Gamma API key",
                        status=GammaStatus.FAILED
                    )
                
                if response.status_code == 403:
                    return GammaGenerationResult(
                        success=False,
                        error_message="Gamma API credits exhausted",
                        status=GammaStatus.FAILED
                    )
                
                # Gamma returns 201 Created for successful generation start
                if response.status_code not in (200, 201):
                    error_data = response.json() if response.text else {}
                    return GammaGenerationResult(
                        success=False,
                        error_message=f"Gamma API error: {error_data.get('message', response.status_code)}",
                        status=GammaStatus.FAILED
                    )
                
                data = response.json()
                generation_id = data.get("generationId")
                
                if not generation_id:
                    return GammaGenerationResult(
                        success=False,
                        error_message="No generation ID returned",
                        status=GammaStatus.FAILED
                    )
                
                logger.info(f"Gamma generation started: {generation_id}")
            
            # Poll for completion
            result = await self._poll_generation_status(generation_id)
            return result
            
        except httpx.TimeoutException:
            logger.error("Gamma API request timed out")
            return GammaGenerationResult(
                success=False,
                error_message="Gamma API request timed out",
                status=GammaStatus.TIMEOUT
            )
        except Exception as e:
            logger.error(f"Gamma generation failed: {e}")
            return GammaGenerationResult(
                success=False,
                error_message=str(e),
                status=GammaStatus.FAILED
            )
    
    async def _poll_generation_status(self, generation_id: str) -> GammaGenerationResult:
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
                            "accept": "application/json"
                        }
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
                            status=GammaStatus.COMPLETED
                        )
                    
                    elif status == "failed":
                        return GammaGenerationResult(
                            success=False,
                            generation_id=generation_id,
                            error_message=data.get("error", "Generation failed"),
                            status=GammaStatus.FAILED
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
                status=GammaStatus.TIMEOUT
            )
    
    async def download_export(
        self,
        url: str,
        timeout: int = 60
    ) -> Optional[bytes]:
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
                else:
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
                    headers={
                        "X-API-KEY": self.api_key,
                        "accept": "application/json"
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "pptx_url": data.get("pptxUrl"),
                        "pdf_url": data.get("pdfUrl")
                    }
                    
        except Exception as e:
            logger.error(f"Error getting Gamma file URLs: {e}")
        
        return {"pptx_url": None, "pdf_url": None}
    
    def _transform_brief_to_gamma_input(
        self,
        title: str,
        executive_summary: str,
        content_markdown: str,
        classification: Optional[Dict[str, str]] = None
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
        sections = []
        
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
                stage_match = re.search(r'(\d+)', str(stage_raw))
                if stage_match:
                    stage_num = int(stage_match.group(1))
                    stage_def = STAGE_DEFINITIONS.get(stage_num, {})
                    stage_name = stage_def.get("name", STAGE_NAMES.get(stage_num, f"Stage {stage_num}"))
                    stage_icon = stage_def.get("icon", "📊")
                    tag_lines.append(f"{stage_icon} **Maturity Stage {stage_num}: {stage_name}**")
                    used_stage = stage_num
            if tag_lines:
                # Format tags as a visual row with separators
                title_section += "\n\n" + "  |  ".join(tag_lines)
        title_section += f"\n\nCity of Austin Strategic Intelligence Brief"
        title_section += f"\n{datetime.now().strftime('%B %Y')}"
        sections.append(title_section)
        
        # Slide 2: Executive Summary
        if executive_summary:
            summary_clean = self._clean_markdown(executive_summary)
            # Truncate if too long for a single slide
            if len(summary_clean) > 800:
                summary_clean = summary_clean[:797] + "..."
            sections.append(f"# Executive Summary\n\n{summary_clean}")
        
        # Parse main content into logical sections
        content_sections = self._parse_content_sections(content_markdown)
        
        for section_title, section_content in content_sections[:6]:  # Max 6 content slides
            clean_content = self._clean_markdown(section_content)
            # Truncate long sections
            if len(clean_content) > 1000:
                clean_content = clean_content[:997] + "..."
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
            for area in pillar_def.get('focus_areas', []):
                pillar_slide += f"- {area}\n"
            
            pillar_slide += f"""
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
            for char in horizon_def.get('characteristics', []):
                horizon_slide += f"- {char}\n"
            
            horizon_slide += f"""
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
            for indicator in stage_def.get('indicators', []):
                stage_slide += f"- {indicator}\n"
            
            stage_slide += f"""
The maturity stage reflects the current development status of this trend 
and helps inform appropriate City response strategies."""
            sections.append(stage_slide)
        
        # Join with Gamma's section break marker
        return "\n---\n".join(sections)
    
    def _parse_content_sections(
        self,
        content_markdown: str
    ) -> List[Tuple[str, str]]:
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
        
        lines = content_markdown.split('\n')
        
        for line in lines:
            # Check for headers
            header_match = re.match(r'^(#{1,3})\s+(.+)$', line)
            if header_match:
                # Save previous section
                if current_content:
                    content_text = '\n'.join(current_content).strip()
                    if content_text and len(content_text) > 50:  # Skip tiny sections
                        sections.append((current_title, content_text))
                
                current_title = header_match.group(2).strip()
                current_content = []
            else:
                current_content.append(line)
        
        # Don't forget the last section
        if current_content:
            content_text = '\n'.join(current_content).strip()
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
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove code blocks (Gamma doesn't render these well in presentations)
        text = re.sub(r'```[\s\S]*?```', '', text)
        
        # Clean up bullet points to standard format
        text = re.sub(r'^[•●○]\s+', '- ', text, flags=re.MULTILINE)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        return text.strip()
    
    def _build_generation_request(
        self,
        input_text: str,
        num_cards: int = 8,
        include_images: bool = True,
        export_format: str = "pptx",
        classification: Optional[Dict[str, str]] = None
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
        # Build comprehensive instructions for executive-quality output
        # Using official City of Austin brand colors
        instructions = """
Create an executive briefing presentation for City of Austin senior leadership (City Manager, Assistant City Managers, Department Directors).

VISUAL DESIGN - USE OFFICIAL CITY OF AUSTIN BRAND COLORS:
- Primary: Logo Blue (#44499C) for headers, titles, and key accents
- Secondary: Logo Green (#009F4D) for highlights, callouts, and positive indicators
- Background: Faded White (#f7f6f5) or pure white for slide backgrounds
- Dark accents: Dark Blue (#22254E) for emphasis text
- Supporting: Light Blue (#dcf2fd) and Light Green (#dff0e3) for subtle backgrounds or callout boxes
- Text: Dark Gray (#636262) or Black (#000000) for body text
- Clean, modern, professional government aesthetic
- Generous white space - avoid cluttered slides
- Use large, readable fonts (minimum 24pt for body text)

TITLE SLIDE CLASSIFICATION TAGS:
- The title slide includes classification tags (Strategic Pillar, Planning Horizon, Maturity Stage)
- Render these tags as polished visual badges or pill-shaped labels
- Each tag should have its emoji/icon displayed prominently alongside the text
- Use a consistent visual treatment: rounded rectangle backgrounds with subtle shadows
- Tags should appear in a horizontal row, visually balanced
- Use Light Blue (#dcf2fd) or Light Green (#dff0e3) as badge backgrounds
- Tag text should be bold and clearly readable
- These tags visually link to their corresponding backup/appendix slides

IMAGERY & DATA VISUALIZATION:
- Generate relevant, high-quality images that illustrate key concepts
- For statistics or metrics, create clean charts using Logo Blue (#44499C) and Logo Green (#009F4D)
- Use bar charts, line graphs, or infographics with the official color palette
- Use icons to represent key concepts where appropriate
- Images should feel professional, contemporary, and appropriate for government context
- Avoid stock photo clichés - prefer conceptual or abstract visuals for technology topics
- For comparison data, use Logo Green for positive/opportunity and Red (#F83125) for risks/concerns

CHART AXIS LABELING (CRITICAL):
- ALL charts MUST have clearly labeled axes with descriptive titles
- X-axis: Include axis title describing what is measured (e.g., "Time Period", "Category", "Year")
- Y-axis: Include axis title with units (e.g., "Adoption Rate (%)", "Investment ($M)", "Score (0-100)")
- Use readable font sizes (minimum 14pt for axis labels, 12pt for tick labels)
- Include data labels on key data points when helpful
- Ensure axis labels render correctly and are not cut off or overlapping
- For time series, clearly label the time intervals
- For categorical charts, ensure all category names are fully visible

SLIDE STRUCTURE:
- Title slide: Bold, impactful title with classification tag badges
- Executive Summary: 3-5 key takeaways as bullet points
- Content slides: One main idea per slide with supporting points
- Use "So What?" framing - always connect to municipal implications
- Include a "Recommended Actions" or "Next Steps" slide
- Appendix slides: Definition slides for each classification tag used
- Final slides explain the classification framework for unfamiliar readers

CONTENT TONE:
- Authoritative but accessible
- Forward-looking and strategic
- Action-oriented language
- Avoid jargon - explain technical concepts simply
- Focus on decision-relevant information
"""
        
        request = {
            "inputText": input_text,
            "textMode": "condense",
            "format": "presentation",
            "numCards": num_cards,
            "cardSplit": "inputTextBreaks",
            "additionalInstructions": instructions.strip(),
            "exportAs": export_format,
            "textOptions": {
                "amount": "medium",
                "tone": "professional, authoritative, strategic, clear, action-oriented",
                "audience": "City Manager, Assistant City Managers, Department Directors, senior municipal executives making strategic decisions",
                "language": "en"
            },
            "cardOptions": {
                "dimensions": "16x9",
                "headerFooter": {
                    "topRight": {
                        "type": "image",
                        "source": "custom",
                        "src": COA_LOGO_HORIZONTAL,
                        "size": "md"
                    },
                    "bottomLeft": {
                        "type": "text",
                        "value": "City of Austin | FORESIGHT Strategic Intelligence"
                    },
                    "bottomRight": {
                        "type": "cardNumber"
                    },
                    "hideFromFirstCard": True,
                    "hideFromLastCard": False
                }
            },
            "sharingOptions": {
                "workspaceAccess": "view",
                "externalAccess": "noAccess"
            }
        }
        
        # Configure image options for high-quality visuals
        if include_images:
            request["imageOptions"] = {
                "source": "aiGenerated",
                "model": "imagen-4-pro",
                "style": "professional photography, clean modern design, corporate, sophisticated, minimalist, high-quality, suitable for government presentations"
            }
        else:
            request["imageOptions"] = {
                "source": "noImages"
            }
        
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
    include_images: bool = True
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
        include_images=include_images
    )
