import json
import os

from openai import OpenAI
from src.config import OPENROUTER_API_KEY


# This gathers company information using the LLM's general knowledge.
# Any information that is inferred rather than confidently known is
# explicitly labelled as an assumption.

_FALLBACK_PROFILE_RISKS = [
    {"risk": "Assumption: Employee health expenses", "type": "Assumption"},
    {"risk": "Assumption: Hospitalisation costs", "type": "Assumption"},
    {"risk": "Assumption: Unexpected medical expenses", "type": "Assumption"},
]


def _get_client():
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not configured in .env"
        )

    return OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1"
    )


def _fallback_profile(company_name):
    return {
        "company_name": company_name,
        "industry": "Unknown",
        "employee_count": "Unknown",
        "location": "Unknown",
        "key_risks": _FALLBACK_PROFILE_RISKS,
        "profile_source": "fallback_stub",
    }


def generate_company_profile(company_name):
    """
    Gather a basic company profile using the model's general knowledge.

    The profile includes:
    - Company name
    - Industry
    - Approximate employee count / company size
    - Location
    - Likely key risks

    Information that is inferred rather than confidently known is
    explicitly labelled as an assumption.
    """

    if not company_name or not company_name.strip():
        raise ValueError("Company name is required")

    company_name = company_name.strip()

    try:
        client = _get_client()

        prompt = f"""
You are a research assistant helping an insurance advisor
prepare a client profile.

Company name: {company_name}

Using your general knowledge, provide what you know about
this company.

If you are not confident about a field, do NOT invent a
specific fact. Instead, provide a generic, reasonable
description and mark that field as an assumption.

Return ONLY valid JSON in exactly this structure:

{{
    "company_name": "{company_name}",
    "industry": "",
    "industry_confirmed": true,
    "size": "",
    "size_confirmed": true,
    "location": "",
    "location_confirmed": true,
    "key_risks": [
        {{"risk": "", "type": "Confirmed"}},
        {{"risk": "", "type": "Assumption"}}
    ]
}}

Rules:

- Set industry_confirmed to false if the industry is being
  inferred rather than confidently known.

- Set size_confirmed to false if the company size or workforce
  information is being inferred.

- Set location_confirmed to false if the location is being
  inferred rather than confidently known.

- Do NOT invent a specific employee count.

- If the exact employee count is not reliably known, use a
  broad description such as "Large enterprise workforce"
  rather than inventing a number.

- key_risks should contain 2-4 items.

- Label a key risk as "Confirmed" only if it is clearly
  associated with this specific company.

- Otherwise label the risk as "Assumption".

- Do not invent specific financial figures, employee counts,
  incidents, lawsuits, or other company-specific events.

- Return JSON only.

- Do not include markdown fences or commentary.
"""

        response = client.chat.completions.create(
            model=os.getenv(
                "OPENROUTER_MODEL",
                "openai/gpt-4o-mini"
            ),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a careful research assistant. "
                        "Never present an assumption as a confirmed "
                        "fact. Return valid JSON only."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.1,
            max_completion_tokens=4000
        )

        content = response.choices[0].message.content

        if not content:
            return _fallback_profile(company_name)

        content = content.strip()

        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        result = json.loads(content.strip())

        # -----------------------------
        # Industry
        # -----------------------------
        industry = result.get("industry") or "Unknown"

        if not result.get("industry_confirmed", False):
            industry = f"Assumption: {industry}"

        # -----------------------------
        # Employee count / company size
        # -----------------------------
        size = result.get("size") or "Unknown"

        if not result.get("size_confirmed", False):
            size = f"Assumption: {size}"

        # -----------------------------
        # Location
        # -----------------------------
        location = result.get("location") or "Unknown"

        if not result.get("location_confirmed", False):
            location = f"Assumption: {location}"

        # -----------------------------
        # Key risks
        # -----------------------------
        key_risks = result.get("key_risks") or _FALLBACK_PROFILE_RISKS

        # Ensure assumption risks are visibly labelled.
        cleaned_risks = []

        for risk_item in key_risks:
            if not isinstance(risk_item, dict):
                continue

            risk = risk_item.get("risk", "").strip()
            risk_type = risk_item.get("type", "Assumption")

            if not risk:
                continue

            if risk_type.lower() == "assumption":
                if not risk.lower().startswith("assumption:"):
                    risk = f"Assumption: {risk}"

            cleaned_risks.append({
                "risk": risk,
                "type": risk_type
            })

        if not cleaned_risks:
            cleaned_risks = _FALLBACK_PROFILE_RISKS

        return {
            "company_name": company_name,
            "industry": industry,
            "employee_count": size,
            "location": location,
            "key_risks": cleaned_risks,
            "profile_source": "ai_generated",
        }

    except Exception as e:
        print(f"\nCOMPANY PROFILE ERROR: {e}\n")
        return _fallback_profile(company_name)