import json
import os
from openai import OpenAI, APIStatusError


# ------------------------------------------------------------------
# Token / size safeguards
#
# The 402 "Prompt tokens limit exceeded" error comes from OpenRouter
# rejecting a request because the assembled prompt is bigger than the
# remaining budget on the API key. The instructional part of the
# prompt is fixed size, but the POLICY EVIDENCE block grows with how
# many chunks the retriever returns and how long each chunk is — that
# is almost always what pushes a request over the limit. The
# constants below cap that growth so requests stay under budget.
# ------------------------------------------------------------------

MAX_POLICY_RESULTS = 6          # max number of evidence chunks to include
MAX_CHARS_PER_RESULT = 1200     # max characters kept per evidence chunk
MAX_TOTAL_EVIDENCE_CHARS = 6000 # hard cap across all evidence combined
MAX_PROMPT_TOKENS = 20000       # safety margin under a 25k-token key limit

# Caps for the client profile / exposures payloads. These can be
# arbitrarily large depending on what upstream code puts into them
# (e.g. raw scraped text, long lists of employees, nested exposure
# detail), so they get the same treatment as policy evidence.
MAX_STRING_VALUE_CHARS = 400    # max chars kept for any single string value
MAX_LIST_ITEMS = 15             # max items kept in any list/array
MAX_PAYLOAD_JSON_CHARS = 4000   # hard cap on the serialized JSON itself


def _estimate_tokens(text):
    """
    Rough token estimate (~4 chars/token) used to decide whether we
    need to trim further before calling the API. This avoids a hard
    dependency on tiktoken; it only needs to be approximately right.
    """
    return max(1, len(text) // 4)


def _get_client():
    """
    Create the OpenRouter/OpenAI-compatible client.
    """

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY environment variable is not set."
        )

    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1"
    )


def _truncate(text, max_chars):
    """
    Truncate text to max_chars, adding a marker so the LLM (and any
    human debugging) knows the evidence was cut short rather than
    naturally ending there.
    """
    if text is None:
        return ""

    text = str(text)

    if len(text) <= max_chars:
        return text

    return text[:max_chars].rstrip() + "\n...[truncated for length]"


def _trim_payload(value, depth=0):
    """
    Recursively trim a JSON-serializable structure so it can't
    silently balloon the prompt: long strings are truncated, long
    lists are capped, and we bail out on absurd nesting depth.

    Structure (keys, shape) is preserved as much as possible so the
    LLM still understands what it's looking at - only the *volume*
    of data is reduced.
    """

    # Guard against pathological/circular-ish nesting.
    if depth > 6:
        return "...[nested too deep, truncated]"

    if isinstance(value, dict):
        return {
            k: _trim_payload(v, depth + 1)
            for k, v in value.items()
        }

    if isinstance(value, list):
        trimmed = [
            _trim_payload(v, depth + 1)
            for v in value[:MAX_LIST_ITEMS]
        ]
        if len(value) > MAX_LIST_ITEMS:
            trimmed.append(
                f"...[{len(value) - MAX_LIST_ITEMS} more item(s) "
                "omitted for length]"
            )
        return trimmed

    if isinstance(value, str):
        return _truncate(value, MAX_STRING_VALUE_CHARS)

    return value


def _prepare_payload_json(data, label):
    """
    Trim then serialize a payload (profile/exposures) to JSON, with
    a final hard cap on the serialized string as a last resort in
    case the trimmed structure is still too large (e.g. thousands of
    small dict keys).
    """

    trimmed = _trim_payload(data)
    payload_json = json.dumps(
        trimmed, indent=2, ensure_ascii=False, default=str
    )

    if len(payload_json) > MAX_PAYLOAD_JSON_CHARS:
        payload_json = _truncate(payload_json, MAX_PAYLOAD_JSON_CHARS)
        payload_json += (
            f"\n...[{label} truncated further to fit prompt size "
            "limits]"
        )

    return payload_json


def _format_policy_results(policy_results):
    """
    Convert retrieved policy evidence into a structured,
    source-labelled block for the LLM.

    Preserves source, page, and section information when
    available, while capping how much evidence text is included so
    the overall prompt cannot grow unbounded and blow past the
    provider's token limit.
    """

    if not policy_results:
        return "No policy evidence was retrieved."

    # Only keep the top N results - if the retriever is returning
    # them in relevance order, these are the most useful ones anyway.
    limited_results = policy_results[:MAX_POLICY_RESULTS]

    formatted = []
    total_chars = 0

    for i, result in enumerate(limited_results, start=1):

        if isinstance(result, dict):

            source = (
                result.get("source")
                or result.get("file")
                or result.get("document")
                or "Unknown policy document"
            )

            text = (
                result.get("text")
                or result.get("content")
                or result.get("chunk")
                or ""
            )

            page = (
                result.get("page")
                or result.get("page_number")
                or result.get("page_num")
                or "Not available"
            )

            section = (
                result.get("section")
                or result.get("section_title")
                or result.get("heading")
                or "Not available"
            )

        else:

            source = "Unknown policy document"
            text = str(result)
            page = "Not available"
            section = "Not available"

        # Cap the length of each individual chunk.
        text = _truncate(text, MAX_CHARS_PER_RESULT)

        # Also enforce a hard cap across all evidence combined, in
        # case there are several long chunks that each pass the
        # per-result cap but together are still too large.
        if total_chars + len(text) > MAX_TOTAL_EVIDENCE_CHARS:
            remaining = max(0, MAX_TOTAL_EVIDENCE_CHARS - total_chars)
            text = _truncate(text, remaining)

        total_chars += len(text)

        formatted.append(
            f"""
========================================================
POLICY EVIDENCE {i}
========================================================
SOURCE DOCUMENT:
{source}

PAGE:
{page}

SECTION:
{section}

EVIDENCE:
{text}
"""
        )

        if total_chars >= MAX_TOTAL_EVIDENCE_CHARS:
            omitted = len(policy_results) - i
            if omitted > 0:
                formatted.append(
                    f"\n[{omitted} additional evidence chunk(s) "
                    "omitted to stay within prompt size limits.]"
                )
            break

    return "\n".join(formatted)


def generate_marketing_pitch(
    profile,
    exposures,
    policy_results
):
    """
    Generate a client-specific insurance marketing pitch.
    """

    client = _get_client()

    policy_evidence = _format_policy_results(
        policy_results
    )

    profile_json = _prepare_payload_json(profile, "Client profile")
    exposures_json = _prepare_payload_json(
        exposures, "Exposure analysis"
    )

    prompt = f"""
You are a professional insurance advisory assistant
working with Marsh.

Your task is to create a polished, client-specific
insurance marketing pitch.

The pitch will be converted into a FIVE-SLIDE client-facing
PowerPoint presentation.

The presentation must demonstrate meaningful reasoning,
not simply repeat the client's input.

============================================================
CORE OBJECTIVE
============================================================

Develop a client-specific marketing pitch for Marsh's
insurance policies.

The pitch must demonstrate:

1. Understanding of the client.
2. Understanding of the client's stated insurance need.
3. Identification of relevant exposures.
4. Mapping of those exposures to documented policy benefits.
5. A clear explanation of why Marsh's advisory role is
   relevant.
6. ONE final recommended policy.
7. Practical next steps for the client.

The presentation should feel like something an insurance
advisor could actually use in a client conversation.

============================================================
CRITICAL GROUNDING RULES
============================================================

POLICY EVIDENCE IS AUTHORITATIVE.

You MUST NOT invent:

- coverage
- benefits
- limits
- percentages
- exclusions
- waiting periods
- eligibility conditions
- claim conditions
- policy features
- pricing
- savings
- statistics

If a policy feature is not present in the supplied evidence,
do not claim that it exists.

If evidence is insufficient, explicitly say:

"Requires advisor verification."

Do not fill evidence gaps using general insurance knowledge.

Never transfer a benefit from one policy to another.

Every policy-related statement must be associated with the
correct source document.

============================================================
CLIENT FACTS VS ASSUMPTIONS
============================================================

The client profile contains information supplied to the
application.

Use those facts directly.

If information is missing, you may use a reasonable
assumption ONLY when necessary.

Every assumption MUST be labelled:

"Assumption: ..."

Do not present assumptions as confirmed company facts.

Industry context may help explain why an exposure could
matter, but do not state that the company definitely has
that exposure unless the information supports it.

============================================================
MARSH POSITIONING
============================================================

The presentation must explain why Marsh is relevant without
inventing corporate claims.

Focus on the advisory role:

- understanding client exposures
- connecting exposures to insurance needs
- comparing relevant policy evidence
- helping the client evaluate alternatives
- evidence-based recommendation
- advisor review before client use

Do NOT invent:

- Marsh market-share claims
- awards
- revenue
- customer numbers
- performance statistics
- guaranteed savings
- unsupported Marsh product capabilities

============================================================
CLIENT PROFILE
============================================================

{profile_json}

============================================================
EXPOSURE ANALYSIS
============================================================

{exposures_json}

============================================================
RETRIEVED POLICY EVIDENCE
============================================================

{policy_evidence}

============================================================
SLIDE 1 — COMPANY OVERVIEW
============================================================

Create a concise but informative overview.

Include:

- Company name
- Industry
- Employee count
- Location
- Stated requirement

Then provide 2–3 meaningful observations explaining what
the client's stated requirement means from an insurance
advisory perspective.

Do not simply repeat the input.

For missing information, clearly label assumptions.

Keep observations to one or two sentences each.

============================================================
SLIDE 2 — WHY CHOOSE MARSH?
============================================================

Explain the advisory value of Marsh for this particular
client.

Provide 4 concise points.

Each point should have:

- a short heading
- a one-sentence explanation

The points should demonstrate:

1. Client-specific exposure assessment
2. Evidence-based policy evaluation
3. Alignment of employee needs with documented policy
   benefits
4. Advisor review and implementation support

Avoid generic corporate slogans.

The slide should answer:

"Why would this client use an insurance advisor rather than
simply selecting a policy directly?"

Do not make unsupported claims about Marsh.

============================================================
SLIDE 3 — EXPOSURES → POLICY BENEFITS
============================================================

This is the most important analytical slide.

Select 3–4 of the most relevant exposures.

For each one provide:

EXPOSURE:
What client need or exposure is being addressed?

WHY IT MATTERS:
Why does it matter for this particular client's stated
requirement?

POLICY RESPONSE:
What documented policy benefit addresses it?

POLICY:
Which policy/product provides that benefit?

SOURCE:
Which policy document supports the statement?

Only use benefits supported by the supplied evidence.

Avoid repeating the same benefit.

Do not create generic insurance risks merely to fill space.

If evidence is insufficient for an exposure, say:

"Requires advisor verification."

============================================================
SLIDE 4 — RECOMMENDED POLICY
============================================================

Select ONE policy/product from the supplied policy evidence.

This must be a defensible recommendation based on:

- the client's stated requirement
- the identified exposures
- the retrieved policy evidence

Do NOT select a policy because it sounds commercially
attractive.

Provide:

POLICY:
The product name.

RECOMMENDATION:
One concise paragraph explaining why it aligns with the
client's stated need.

KEY REASONS:
Exactly 3 concise reasons.

Each reason must be supported by the retrieved evidence.

SUPPORTING BENEFITS:
2–3 documented benefits.

EVIDENCE:
List the source policy document(s).

If the evidence is not sufficient to make a defensible
recommendation, explicitly state:

"Insufficient evidence for a final recommendation;
advisor verification required."

Do not recommend multiple policies.

============================================================
SLIDE 5 — CLIENT CONVERSATION & NEXT STEPS
============================================================

Create a professional client-facing closing slide.

Provide:

HEADLINE:
A concise statement focused on the client's need.

BODY:
A short paragraph explaining:

- the client's main concern
- the exposure identified
- how the recommended solution addresses it
- why the solution is relevant

Do not simply repeat Slide 4.

Then provide exactly 4 practical next steps:

1. Confirm employee and coverage requirements.
2. Review policy terms and applicable conditions.
3. Validate the recommendation with the advisor.
4. Proceed to the next stage of policy evaluation.

These steps may be adapted to the specific client, but must
remain practical and realistic.

============================================================
WRITING STYLE
============================================================

The presentation should sound:

- professional
- analytical
- client-focused
- concise
- confident but not exaggerated

Avoid:

- huge paragraphs
- generic AI language
- unnecessary jargon
- repetitive statements
- marketing clichés
- unsupported superlatives

Use complete sentences.

Every item should be understandable without reading the
other slides.

============================================================
LENGTH CONSTRAINTS
============================================================

The PowerPoint has limited space.

Therefore:

COMPANY OBSERVATIONS:
2–3 items, maximum approximately 20 words each.

WHY MARSH:
4 points, maximum approximately 25 words each.

POLICY MAPPING:
3–4 rows.

WHY IT MATTERS:
maximum approximately 18 words.

BENEFIT:
maximum approximately 25 words.

RECOMMENDATION:
maximum approximately 55 words.

RECOMMENDATION REASONS:
exactly 3, maximum approximately 20 words each.

SUPPORTING BENEFITS:
2–3 items.

CLIENT BODY:
maximum approximately 70 words.

NEXT STEPS:
exactly 4 items, maximum approximately 15 words each.

Do not sacrifice factual accuracy to meet the word limits.

============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

Use EXACTLY this structure:

{{
    "company_overview": {{
        "title": "Understanding the Client",
        "company_name": "",
        "industry": "",
        "employee_count": "",
        "location": "",
        "requirements": "",
        "observations": [
            ""
        ]
    }},

    "why_marsh": {{
        "title": "Why Choose Marsh?",
        "points": [
            {{
                "heading": "",
                "text": ""
            }}
        ]
    }},

    "policy_mapping": [
        {{
            "exposure": "",
            "why_it_matters": "",
            "policy": "",
            "benefit": "",
            "source": ""
        }}
    ],

    "recommended_policy": {{
        "policy": "",
        "recommendation": "",
        "rationale": [
            "",
            "",
            ""
        ],
        "supporting_benefits": [
            ""
        ],
        "sources": [
            ""
        ]
    }},

    "client_pitch": {{
        "headline": "",
        "body": "",
        "next_steps": [
            "",
            "",
            "",
            ""
        ]
    }}
}}

IMPORTANT:

Return JSON only.

Do not use markdown.

Do not add commentary before or after the JSON.
"""

    system_message = (
        "You are a precise insurance advisory "
        "assistant. Generate client-ready content "
        "using only supplied policy evidence. "
        "Return valid JSON only."
    )

    # Final safety check: even after capping evidence above, verify
    # the assembled prompt is within budget. If something upstream
    # (e.g. a very large profile/exposures payload) still pushes it
    # over, fail fast with a clear message instead of letting the
    # API reject it with an opaque 402.
    estimated_tokens = _estimate_tokens(system_message + prompt)

    if estimated_tokens > MAX_PROMPT_TOKENS:
        raise RuntimeError(
            "The assembled prompt is too large "
            f"(~{estimated_tokens} estimated tokens, limit "
            f"{MAX_PROMPT_TOKENS}). This is usually caused by a "
            "very large client profile or exposures payload - "
            "trim those before calling generate_marketing_pitch, "
            "or raise MAX_PROMPT_TOKENS if your OpenRouter key has "
            "a larger budget."
        )

    try:
        response = client.chat.completions.create(
            model=os.getenv(
                "OPENROUTER_MODEL",
                "openai/gpt-4o-mini"
            ),
            messages=[
                {
                    "role": "system",
                    "content": system_message
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.15,
            max_completion_tokens=4000
        )

    except APIStatusError as e:
        if e.status_code == 402:
            raise RuntimeError(
                "OpenRouter rejected the request for exceeding "
                "the key's token/credit limit (HTTP 402). Add "
                "credits or raise the key's limit at "
                "https://openrouter.ai/settings/credits, or "
                "reduce MAX_POLICY_RESULTS / "
                "MAX_TOTAL_EVIDENCE_CHARS in this file to shrink "
                "the prompt further."
            ) from e
        raise

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "The LLM returned an empty response."
        )

    content = content.strip()

    # Remove markdown JSON fences if necessary.
    if content.startswith("```json"):
        content = content[7:]

    elif content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    try:

        result = json.loads(content)

    except json.JSONDecodeError as e:

        raise RuntimeError(
            "The LLM returned invalid JSON.\n\n"
            f"Raw response:\n{content}"
        ) from e

    required_sections = [
        "company_overview",
        "why_marsh",
        "policy_mapping",
        "recommended_policy",
        "client_pitch"
    ]

    missing = [
        section
        for section in required_sections
        if section not in result
    ]

    if missing:

        raise RuntimeError(
            "The LLM response is missing required sections: "
            + ", ".join(missing)
        )

    # Basic structural validation.
    if not isinstance(
        result["policy_mapping"],
        list
    ):
        raise RuntimeError(
            "policy_mapping must be a list."
        )

    if not isinstance(
        result["why_marsh"].get("points"),
        list
    ):
        raise RuntimeError(
            "why_marsh.points must be a list."
        )

    if not isinstance(
        result["recommended_policy"].get("rationale"),
        list
    ):
        raise RuntimeError(
            "recommended_policy.rationale must be a list."
        )

    if not isinstance(
        result["client_pitch"].get("next_steps"),
        list
    ):
        raise RuntimeError(
            "client_pitch.next_steps must be a list."
        )

    return result