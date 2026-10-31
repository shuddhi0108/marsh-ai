import json

from openai import OpenAI
from src.config import OPENROUTER_API_KEY


client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1"
)


def _clean_json_response(content):

    if not content:
        raise ValueError(
            "The AI returned an empty exposure analysis."
        )

    content = content.strip()

    if content.startswith("```json"):
        content = content[len("```json"):]

    elif content.startswith("```"):
        content = content[len("```"):]

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    try:
        return json.loads(content)

    except json.JSONDecodeError as e:
        raise ValueError(
            f"Exposure analysis returned invalid JSON: {e}"
        )


def analyze_exposures(profile, policy_results):

    company_name = profile.get(
        "company_name",
        "Unknown"
    )

    industry = profile.get(
        "industry",
        "Unknown"
    )

    employee_count = profile.get(
        "employee_count",
        profile.get(
            "size",
            "Unknown"
        )
    )

    location = profile.get(
        "location",
        "Unknown"
    )

    requirements = profile.get(
        "requirements",
        "Not specified"
    )

    # ---------------------------------------------------------
    # Prepare retrieved policy evidence
    # ---------------------------------------------------------

    retrieved_evidence = []

    for result in policy_results:

        if isinstance(result, dict):

            retrieved_evidence.append({
                "source": result.get(
                    "source",
                    ""
                ),

                "text": result.get(
                    "text",
                    result.get(
                        "content",
                        ""
                    )
                ),

                "score": result.get(
                    "score",
                    None
                )
            })

        else:

            retrieved_evidence.append({
                "source": "",
                "text": str(result),
                "score": None
            })

    # ---------------------------------------------------------
    # LLM prompt
    # ---------------------------------------------------------

    prompt = f"""
You are an insurance exposure analysis specialist.

Analyse the client's information and the retrieved policy
evidence.

Do NOT invent company-specific facts.

Do NOT assume that an exposure exists simply because it is
common in the client's industry.

Only identify exposures that can reasonably be connected to
the information explicitly provided.

==========================================================
CLIENT INFORMATION
==========================================================

Company:
{company_name}

Industry:
{industry}

Employee Count:
{employee_count}

Location:
{location}

Stated Requirements:
{requirements}

==========================================================
RETRIEVED POLICY EVIDENCE
==========================================================

{json.dumps(retrieved_evidence, indent=2)}

==========================================================
TASK
==========================================================

Identify the most relevant insurance exposures arising from
the client's stated requirement.

For every exposure:

1. Identify the exposure.
2. Explain why it is relevant.
3. Identify the corresponding insurance need.
4. Identify relevant policy evidence.
5. Explain the policy relevance.
6. Assign a priority.
7. Clearly distinguish assumptions from confirmed facts.

Do not produce generic industry risk lists.

If the client requirement concerns employee health insurance,
focus on employee health and medical coverage rather than
inventing unrelated risks.

==========================================================
OUTPUT
==========================================================

Return ONLY a JSON object.

Use exactly this structure:

{{
    "exposures": [
        {{
            "risk": "...",
            "type": "...",
            "why_relevant": "...",
            "insurance_need": "...",
            "priority": "High/Medium/Low",
            "evidence_sources": [],
            "policy_relevance": "..."
        }}
    ],
    "overall_exposure_summary": "...",
    "coverage_priorities": [
        "...",
        "...",
        "..."
    ]
}}

==========================================================
GROUNDING RULES
==========================================================

1. Use client information as the primary basis.

2. Use retrieved policy evidence only for documented
   policy relevance.

3. Never invent policy benefits.

4. Never invent coverage limits.

5. Never invent exclusions.

6. Never invent eligibility conditions.

7. Never claim a company has an employee demographic or
   operational risk unless it was provided.

8. Industry information is contextual and must not
   automatically be treated as a confirmed company fact.

9. Label assumptions explicitly as "Assumption: ...".

10. Do not make unsupported claims about Marsh.

11. Do not rank policies as universally best.

12. Priorities must refer to the client's stated needs.

13. Every policy-related statement must be traceable to
    supplied evidence.

14. Never use evidence from one policy to describe another.

15. Avoid repetitive exposures.

16. Prefer 3–5 meaningful exposures.

17. If evidence is insufficient, explicitly say so.

18. Return valid JSON only.
"""

    # ---------------------------------------------------------
    # OpenRouter request
    # ---------------------------------------------------------

    response = client.chat.completions.create(
       model="openai/gpt-4o-mini",

        messages=[
            {
                "role": "system",
                "content": (
                    "You are a careful insurance exposure "
                    "analyst. Ground every policy-related "
                    "statement in the supplied evidence. "
                    "Return valid JSON only."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0.1,
        max_completion_tokens=4000,

        response_format={
            "type": "json_object"
        }
    )

    # ---------------------------------------------------------
    # Extract model response
    # ---------------------------------------------------------

    if not response.choices:
        raise ValueError(
            "Exposure analysis model returned no choices."
        )

    message = response.choices[0].message

    content = message.content

    # Some OpenRouter responses can contain no content.
    if not content:
        raise ValueError(
            "Exposure analysis model returned an empty response."
        )

    # ---------------------------------------------------------
    # Parse JSON
    # ---------------------------------------------------------

    analysis = _clean_json_response(
        content
    )

    # ---------------------------------------------------------
    # Convert structured format into the format expected
    # by pitch_generator.py
    # ---------------------------------------------------------

    exposures = []

    for exposure in analysis.get(
        "exposures",
        []
    ):

        relevant_policies = []

        for source in exposure.get(
            "evidence_sources",
            []
        ):

            for evidence in retrieved_evidence:

                if evidence.get(
                    "source"
                ) == source:

                    relevant_policies.append({
                        "source": evidence.get(
                            "source",
                            ""
                        ),

                        "text": evidence.get(
                            "text",
                            ""
                        ),

                        "score": evidence.get(
                            "score",
                            None
                        )
                    })

        exposures.append({
            "risk": exposure.get(
                "risk",
                ""
            ),

            "type": exposure.get(
                "type",
                ""
            ),

            "why_relevant": exposure.get(
                "why_relevant",
                ""
            ),

            "insurance_need": exposure.get(
                "insurance_need",
                ""
            ),

            "priority": exposure.get(
                "priority",
                ""
            ),

            "policy_relevance": exposure.get(
                "policy_relevance",
                ""
            ),

            "relevant_policies": relevant_policies
        })

    return exposures