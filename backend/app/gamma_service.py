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

# Default branding
FORESIGHT_BRANDING = "FORESIGHT Strategic Intelligence Platform"
COA_LOGO_URL = os.getenv(
    "COA_LOGO_URL",
    "https://www.austintexas.gov/sites/default/files/files/Branding/COA_Logo_Horizontal_Official_RGB.png"
)

# Classification data for slide context
PILLAR_NAMES = {
    "CH": "Community Health & Sustainability",
    "EW": "Economic & Workforce Development",
    "HG": "High-Performing Government",
    "HH": "Homelessness & Housing",
    "MC": "Mobility & Critical Infrastructure",
    "PS": "Public Safety",
    "ES": "Environmental Sustainability",
}

HORIZON_NAMES = {
    "H1": "Mainstream (0-3 years)",
    "H2": "Transitional (3-7 years)",
    "H3": "Transformative (7-15+ years)",
}

STAGE_NAMES = {
    1: "Concept",
    2: "Emerging",
    3: "Prototype",
    4: "Pilot",
    5: "Municipal Pilot",
    6: "Early Adoption",
    7: "Mainstream",
    8: "Mature",
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
        optimal slide generation.
        
        Args:
            title: Presentation title
            executive_summary: Executive summary
            content_markdown: Full brief content
            classification: Classification metadata
            
        Returns:
            Transformed content string for Gamma API
        """
        sections = []
        
        # Slide 1: Title slide
        title_section = f"# {title}\n"
        if classification:
            tags = []
            if classification.get("pillar"):
                pillar = classification["pillar"].upper()
                pillar_name = PILLAR_NAMES.get(pillar, pillar)
                tags.append(f"Strategic Pillar: {pillar_name}")
            if classification.get("horizon"):
                horizon = classification["horizon"].upper()
                horizon_name = HORIZON_NAMES.get(horizon, horizon)
                tags.append(f"Planning Horizon: {horizon_name}")
            if classification.get("stage"):
                stage_raw = classification["stage"]
                stage_match = re.search(r'(\d+)', str(stage_raw))
                if stage_match:
                    stage_num = int(stage_match.group(1))
                    stage_name = STAGE_NAMES.get(stage_num, f"Stage {stage_num}")
                    tags.append(f"Maturity Stage: {stage_num} - {stage_name}")
            if tags:
                title_section += "\n".join(tags)
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
        
        # Final slide: AI Disclosure
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
        # Build additional instructions based on content
        instructions = """
Create an executive-quality strategic intelligence presentation for senior city government leadership.

Design requirements:
- Professional, clean, government-appropriate visual style
- Use a blue color scheme (#1E3A5F primary, #2E86AB secondary)
- Include relevant imagery that supports the strategic content
- Charts and data visualizations where metrics are mentioned
- Clear hierarchy with concise bullet points
- Each slide should make one key point clearly

Content guidelines:
- This is strategic foresight content about emerging trends and technologies
- Focus on implications for municipal government
- Highlight actionable insights and decision points
- Include timeline and urgency information where relevant
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
                "tone": "professional, authoritative, strategic",
                "audience": "senior government executives, city leadership, municipal decision-makers",
                "language": "en"
            },
            "cardOptions": {
                "dimensions": "16x9",
                "headerFooter": {
                    "bottomLeft": {
                        "type": "text",
                        "value": FORESIGHT_BRANDING
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
        
        # Configure image options
        if include_images:
            request["imageOptions"] = {
                "source": "aiGenerated",
                "model": "imagen-4-pro",
                "style": "professional, clean, photorealistic, corporate, modern"
            }
        else:
            request["imageOptions"] = {
                "source": "noImages"
            }
        
        # Add logo if URL is configured
        if COA_LOGO_URL:
            request["cardOptions"]["headerFooter"]["topRight"] = {
                "type": "image",
                "source": "custom",
                "src": COA_LOGO_URL,
                "size": "sm"
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
