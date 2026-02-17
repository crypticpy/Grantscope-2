"""AI-assisted grant proposal generation service."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.deps import openai_client
from app.openai_provider import get_chat_deployment

logger = logging.getLogger(__name__)

# The 6 standard proposal sections
PROPOSAL_SECTIONS = [
    "executive_summary",
    "needs_statement",
    "project_description",
    "budget_narrative",
    "timeline",
    "evaluation_plan",
]


class ProposalService:
    """Service for AI-assisted grant proposal generation."""

    def __init__(self):
        self.client = openai_client
        self.model = get_chat_deployment()

    async def generate_section(
        self,
        section_name: str,
        card: dict,
        workstream: dict,
        existing_sections: Dict[str, Any],
        additional_context: Optional[str] = None,
    ) -> tuple[str, str]:
        """Generate a single proposal section using AI.

        Returns: (generated_text, model_used)
        """
        if section_name not in PROPOSAL_SECTIONS:
            raise ValueError(
                f"Invalid section: {section_name}. Valid: {PROPOSAL_SECTIONS}"
            )

        # Build the prompt
        prompt = self._build_section_prompt(
            section_name, card, workstream, existing_sections, additional_context
        )

        try:
            # Wrap synchronous Azure OpenAI call to avoid blocking the event loop
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": PROPOSAL_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=2000,
            )
            content = response.choices[0].message.content or ""
            model_used = response.model or self.model
            return content.strip(), model_used
        except Exception as e:
            logger.error(f"AI generation failed for section {section_name}: {e}")
            raise

    async def generate_full_proposal(
        self,
        card: dict,
        workstream: dict,
    ) -> Dict[str, Any]:
        """Generate all proposal sections."""
        sections: Dict[str, Any] = {}
        model_used = self.model

        for section_name in PROPOSAL_SECTIONS:
            try:
                content, model_used = await self.generate_section(
                    section_name, card, workstream, sections
                )
                sections[section_name] = {
                    "content": content,
                    "ai_draft": content,
                    "last_edited": datetime.now(timezone.utc).isoformat(),
                }
            except Exception as e:
                logger.warning(f"Failed to generate {section_name}: {e}")
                sections[section_name] = {
                    "content": "",
                    "ai_draft": None,
                    "last_edited": datetime.now(timezone.utc).isoformat(),
                }

        return {"sections": sections, "model_used": model_used}

    def _build_section_prompt(
        self,
        section_name: str,
        card: dict,
        workstream: dict,
        existing_sections: Dict[str, Any],
        additional_context: Optional[str] = None,
    ) -> str:
        """Build the prompt for generating a specific section."""

        # Grant opportunity context
        grant_context = f"""
## Grant Opportunity
- **Title**: {card.get('name', 'Unknown')}
- **Grantor**: {card.get('grantor', 'Unknown')}
- **Grant Type**: {card.get('grant_type', 'Unknown')}
- **Funding Range**: ${card.get('funding_amount_min', 'N/A')} - ${card.get('funding_amount_max', 'N/A')}
- **Deadline**: {card.get('deadline', 'Not specified')}
- **CFDA Number**: {card.get('cfda_number', 'N/A')}
- **Eligibility**: {card.get('eligibility_text', 'See grant guidelines')}
- **Match Requirement**: {card.get('match_requirement', 'Not specified')}
- **Description**: {card.get('description', card.get('summary', 'No description available'))}
"""

        # Program context
        program_context = f"""
## Applicant Program
- **Program**: {workstream.get('name', 'Unknown')}
- **Description**: {workstream.get('description', 'No description')}
- **Department**: {workstream.get('department_id', 'Not specified')}
- **Budget**: ${workstream.get('budget', 'Not specified')}
- **Fiscal Year**: {workstream.get('fiscal_year', 'Current')}
- **Focus Keywords**: {', '.join(workstream.get('keywords', []))}
"""

        # Previously generated sections for coherence
        prior_sections = ""
        if existing_sections:
            prior_sections = "\n## Previously Generated Sections\n"
            for name, data in existing_sections.items():
                if isinstance(data, dict) and data.get("content"):
                    prior_sections += f"\n### {name.replace('_', ' ').title()}\n{data['content'][:500]}...\n"

        # Section-specific instructions
        section_instructions = SECTION_PROMPTS.get(
            section_name, f"Write the {section_name.replace('_', ' ')} section."
        )

        additional_block = ""
        if additional_context:
            additional_block = (
                f"\n## Additional Context from User\n{additional_context}"
            )

        prompt = f"""{grant_context}
{program_context}
{prior_sections}
{additional_block}

## Your Task
{section_instructions}

Write ONLY the content for this section. Do not include headers or section titles.
Be specific to this grant opportunity and program. Use concrete details from the context provided.
Write in a professional grant application tone. Target 300-500 words.
"""
        return prompt


# System prompt for proposal generation
PROPOSAL_SYSTEM_PROMPT = """You are an expert grant writer for the City of Austin, Texas. \
You help city departments write compelling, compliant grant proposals.

Key principles:
- Use concrete, measurable language with specific outcomes and metrics
- Reference Austin's strategic priorities and community needs
- Address all eligibility requirements and evaluation criteria
- Include data points and evidence where possible
- Maintain a professional, persuasive tone
- Ensure consistency across sections
- Follow federal/state grant writing best practices
"""

# Per-section generation instructions
SECTION_PROMPTS = {
    "executive_summary": """Write a compelling Executive Summary (300-500 words) that:
- Clearly states the funding request and program name
- Describes the problem/need being addressed in Austin
- Summarizes the proposed approach and expected outcomes
- Highlights the applicant's qualifications and capacity
- Includes the total budget request and project timeline
- Creates urgency and demonstrates community impact""",
    "needs_statement": """Write a Needs Statement (400-600 words) that:
- Documents the specific community need or problem in Austin
- Uses data and statistics to quantify the need
- Describes the target population and geographic area
- Explains consequences of not addressing the need
- Connects to broader city/state/national priorities
- Demonstrates why this program is the right response""",
    "project_description": """Write a Project Description (500-800 words) that:
- Describes the proposed activities and methodology
- Outlines specific, measurable goals and objectives
- Details the implementation timeline and milestones
- Identifies key personnel and their qualifications
- Explains how the project addresses the identified need
- Describes partnerships and community engagement
- Addresses sustainability beyond the grant period""",
    "budget_narrative": """Write a Budget Narrative (300-500 words) that:
- Justifies each major budget category (personnel, equipment, supplies, etc.)
- Explains cost reasonableness for each line item
- Addresses any matching funds or in-kind contributions
- Aligns costs directly to project activities
- Addresses any indirect cost rate if applicable
- Demonstrates fiscal responsibility and efficiency""",
    "timeline": """Write a Project Timeline (200-400 words) that:
- Breaks the project into phases or quarters
- Lists key milestones and deliverables for each phase
- Identifies responsible parties for each milestone
- Includes a realistic start date and end date
- Accounts for hiring, procurement, and startup time
- Shows logical sequencing of activities""",
    "evaluation_plan": """Write an Evaluation Plan (300-500 words) that:
- Identifies specific performance measures and indicators
- Describes data collection methods and frequency
- Outlines both process and outcome evaluation approaches
- Specifies how results will be reported to the grantor
- Includes baseline measurements where possible
- Addresses how findings will inform program improvement
- Aligns with the grantor's reporting requirements""",
}
