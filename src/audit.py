import json
import os
from openai import OpenAI


def _get_client():
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY environment variable is not set."
        )

    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1"
    )


def _format_policy_documents(chunks, sources, pages=None):
    """
    Format policy evidence with explicit source labels.

    Includes the page number when available so the audit model
    can actually populate the PAGE column of the claim table
    instead of leaving it blank for every row.
    """

    if not chunks:
        return "No policy evidence available."

    evidence = []

    for i, chunk in enumerate(chunks):

        if isinstance(chunk, dict):

            text = (
                chunk.get("text")
                or chunk.get("content")
                or chunk.get("chunk")
                or ""
            )

            source = (
                chunk.get("source")
                or chunk.get("file")
                or chunk.get("document")
                or (
                    sources[i]
                    if sources and i < len(sources)
                    else "Unknown source"
                )
            )

            page = (
                chunk.get("page")
                or chunk.get("page_number")
                or (
                    pages[i]
                    if pages and i < len(pages)
                    else "Not available"
                )
            )

        else:

            text = str(chunk)

            source = (
                sources[i]
                if sources and i < len(sources)
                else "Unknown source"
            )

            page = (
                pages[i]
                if pages and i < len(pages)
                else "Not available"
            )

        evidence.append(
            f"""
========================================================
POLICY EVIDENCE {i + 1}
========================================================
SOURCE:
{source}

PAGE:
{page}

TEXT:
{text}
"""
        )

    return "\n".join(evidence)


def _extract_claims_from_pitch(pitch):
    """
    Extract the policy-related statements that require
    evidence verification.

    Company observations and general Marsh positioning are
    intentionally not treated as policy coverage claims.
    """

    claims = []

    if not isinstance(pitch, dict):
        return claims

    # -----------------------------------------------------
    # POLICY MAPPING
    # -----------------------------------------------------

    policy_mapping = pitch.get(
        "policy_mapping",
        []
    )

    if isinstance(policy_mapping, list):

        for item in policy_mapping:

            if not isinstance(item, dict):
                continue

            exposure = str(
                item.get("exposure", "")
            ).strip()

            policy = str(
                item.get("policy", "")
            ).strip()

            benefit = str(
                item.get("benefit", "")
            ).strip()

            if benefit:

                claims.append({
                    "claim_type": "Policy benefit",
                    "claim": benefit,
                    "context": (
                        f"Exposure: {exposure}; "
                        f"Policy: {policy}"
                    )
                })

    # -----------------------------------------------------
    # RECOMMENDED POLICY
    # -----------------------------------------------------

    recommendation = pitch.get(
        "recommended_policy",
        {}
    )

    if isinstance(recommendation, dict):

        policy = str(
            recommendation.get("policy", "")
        ).strip()

        recommendation_text = str(
            recommendation.get(
                "recommendation",
                ""
            )
        ).strip()

        if recommendation_text:

            claims.append({
                "claim_type": "Recommendation",
                "claim": recommendation_text,
                "context": (
                    f"Recommended policy: {policy}"
                )
            })

        rationale = recommendation.get(
            "rationale",
            []
        )

        if isinstance(rationale, list):

            for reason in rationale:

                reason = str(reason).strip()

                if reason:

                    claims.append({
                        "claim_type": "Recommendation rationale",
                        "claim": reason,
                        "context": (
                            f"Recommended policy: {policy}"
                        )
                    })

        supporting_benefits = recommendation.get(
            "supporting_benefits",
            []
        )

        if isinstance(
            supporting_benefits,
            list
        ):

            for benefit in supporting_benefits:

                benefit = str(benefit).strip()

                if benefit:

                    claims.append({
                        "claim_type": "Supporting benefit",
                        "claim": benefit,
                        "context": (
                            f"Recommended policy: {policy}"
                        )
                    })

    # -----------------------------------------------------
    # CLIENT PITCH
    # -----------------------------------------------------

    client_pitch = pitch.get(
        "client_pitch",
        {}
    )

    if isinstance(client_pitch, dict):

        body = str(
            client_pitch.get(
                "body",
                ""
            )
        ).strip()

        if body:

            claims.append({
                "claim_type": "Client pitch",
                "claim": body,
                "context": (
                    "Final client-facing explanation"
                )
            })

    return claims


def audit_pitch_content(
    pitch,
    chunks,
    sources,
    pages=None
):
    """
    Audit policy-related statements in the generated pitch.

    The audit is an internal advisor-facing artifact.

    It does NOT become a client-facing slide.
    """

    client = _get_client()

    claims = _extract_claims_from_pitch(
        pitch
    )

    policy_evidence = _format_policy_documents(
        chunks,
        sources,
        pages
    )

    if not claims:

        return {
            "overall_status": "REVIEW",
            "confidence_score": 0,
            "claims_checked": 0,
            "supported_claims": 0,
            "review_claims": 0,
            "unsupported_claims": 0,
            "claims": [],
            "advisor_action": (
                "No auditable policy claims were found. "
                "The advisor should manually review the "
                "presentation before client use."
            )
        }

    claims_text = "\n\n".join(
        [
            (
                f"CLAIM {i + 1}\n"
                f"TYPE: {item['claim_type']}\n"
                f"STATEMENT: {item['claim']}\n"
                f"CONTEXT: {item['context']}"
            )
            for i, item in enumerate(claims)
        ]
    )

    prompt = f"""
You are a strict insurance policy-content auditor.

Your job is to determine whether policy-related statements
in an AI-generated Marsh insurance pitch are supported by
the supplied policy documents.

You MUST use ONLY the supplied policy evidence.

============================================================
AUDIT RULES
============================================================

SUPPORTED
---------
Use SUPPORTED only when the supplied policy evidence clearly
supports the claim.

REVIEW
------
Use REVIEW when:

- evidence is incomplete;
- evidence is ambiguous;
- the claim requires interpretation;
- the source exists but does not clearly establish the full
  statement;
- advisor confirmation is appropriate.

IMPORTANT FOR RECOMMENDATIONS
-----------------------------
The following claim types are not direct policy-benefit claims:

- Recommendation
- Recommendation rationale
- Client pitch

For these claim types:

- Use REVIEW when the statement is an interpretation,
  recommendation, client-specific conclusion, or general
  business statement that cannot be directly traced to a
  policy clause.
- Do NOT mark the statement UNSUPPORTED merely because it has
  no direct policy clause.
- If the statement contains a specific policy benefit, figure,
  coverage condition, or other factual policy assertion, that
  factual part MUST be traceable to the supplied policy evidence.
- Keep source/page/section/clause blank when there is genuinely
  no direct policy source, and explain that advisor judgement
  is required.

UNSUPPORTED
-----------
Use UNSUPPORTED when:

- no supplied evidence supports a direct policy claim;
- the claim contains a benefit not present in the documents;
- the claim contains a figure not present in the documents;
- the claim attributes a benefit to the wrong policy;
- the claim goes beyond what the evidence establishes.

Never use general insurance knowledge to upgrade a claim
from REVIEW to SUPPORTED.

Never assume a benefit exists because it is common in
insurance.

Never use evidence from one policy document to support
another policy.

============================================================
POLICY EVIDENCE
============================================================

{policy_evidence}

============================================================
PITCH CLAIMS
============================================================

{claims_text}

============================================================
SOURCE TRACEABILITY
============================================================

For every claim:

1. Determine its status.
2. For direct policy claims marked SUPPORTED, identify the
   exact source document.
3. Identify the page and section when available in the supplied
   evidence.
4. Identify the relevant clause or policy wording when
   available.
5. Quote or summarize the relevant evidence.
6. Explain why the evidence supports, partially supports,
   or does not support the claim.

If no source supports a direct policy claim, write:

"No matching policy clause found."

Do not invent page numbers, section names, or clause numbers.

For Recommendation, Recommendation rationale, and Client pitch
claims that are REVIEW because they require advisor judgement,
it is acceptable for source/page/section/clause to be blank.

============================================================
CONFIDENCE
============================================================

Calculate:

confidence_score =
SUPPORTED claims / total audited claims * 100

Round to the nearest whole number.

Important:

A high confidence score does NOT override an UNSUPPORTED
claim.

If there is even one clearly UNSUPPORTED claim, the overall
status must be FAIL.

============================================================
OVERALL STATUS
============================================================

PASS:
- zero UNSUPPORTED claims
- at least 80% SUPPORTED

REVIEW:
- zero UNSUPPORTED claims
- but one or more REVIEW claims
- OR fewer than 80% are SUPPORTED

FAIL:
- one or more UNSUPPORTED claims

============================================================
ADVISOR ACTION
============================================================

PASS:
Recommend approval subject to normal advisor review.

REVIEW:
Recommend that the advisor edit or verify the flagged claims
before client use.

FAIL:
Recommend rejecting the current pitch until unsupported
claims are removed or corrected.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

Use exactly this structure:

{{
    "overall_status": "PASS",
    "confidence_score": 0,
    "claims_checked": 0,
    "supported_claims": 0,
    "review_claims": 0,
    "unsupported_claims": 0,

    "claims": [
        {{
            "claim_type": "",
            "claim": "",
            "status": "SUPPORTED",
            "source": "",
            "evidence": "",
            "explanation": ""
        }}
    ],

    "advisor_action": ""
}}
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
                "You are a strict insurance policy "
                "auditor. Use only supplied evidence. "
                "Never invent policy clauses. Return "
                "valid JSON only."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.0,
        max_completion_tokens=4000
    )
    

    content = response.choices[0].message.content

    if not content:
        raise RuntimeError(
            "The audit model returned an empty response."
        )

    content = content.strip()

    if content.startswith("```json"):
        content = content[7:]

    elif content.startswith("```"):
        content = content[3:]

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    try:

        audit_report = json.loads(
            content
        )

    except json.JSONDecodeError as e:

        raise RuntimeError(
            "The audit model returned invalid JSON.\n\n"
            f"Raw response:\n{content}"
        ) from e

    # -----------------------------------------------------
    # Validate / normalize audit fields
    # -----------------------------------------------------

    audit_report.setdefault(
        "claims",
        []
    )

    # The model decides each claim's status, but Python calculates
    # the final summary so the audit result always matches the
    # actual claim-level results.
    audited_claims = audit_report.get(
        "claims",
        []
    )

    if not isinstance(audited_claims, list):
        audited_claims = []
        audit_report["claims"] = audited_claims

    supported_claims = 0
    review_claims = 0
    unsupported_claims = 0

    for claim in audited_claims:
        if not isinstance(claim, dict):
            continue

        status = str(
            claim.get("status", "REVIEW")
        ).strip().upper()

        if status == "SUPPORTED":
            supported_claims += 1
        elif status == "UNSUPPORTED":
            unsupported_claims += 1
        else:
            # Unknown or missing statuses require advisor review.
            claim["status"] = "REVIEW"
            review_claims += 1

    claims_checked = (
        supported_claims
        + review_claims
        + unsupported_claims
    )

    if claims_checked == 0:
        overall_status = "REVIEW"
        confidence_score = 0
        advisor_action = (
            "No auditable policy claims were found. "
            "The advisor should manually review the "
            "presentation before client use."
        )

    else:
        confidence_score = round(
            (supported_claims / claims_checked) * 100
        )

        if unsupported_claims > 0:
            overall_status = "FAIL"
            advisor_action = (
                "Recommend rejecting the current pitch until "
                "unsupported claims are removed or corrected."
            )

        elif supported_claims >= 0.80 * claims_checked:
            overall_status = "PASS"
            advisor_action = (
                "Recommend approval subject to normal advisor review."
            )

        else:
            overall_status = "REVIEW"
            advisor_action = (
                "Recommend that the advisor edit or verify the "
                "flagged claims before client use."
            )

    audit_report["claims_checked"] = claims_checked
    audit_report["supported_claims"] = supported_claims
    audit_report["review_claims"] = review_claims
    audit_report["unsupported_claims"] = unsupported_claims
    audit_report["overall_status"] = overall_status
    audit_report["confidence_score"] = confidence_score
    audit_report["advisor_action"] = advisor_action

    return audit_report

def get_advisor_action(audit):
    """
    Return the advisor action from an audit report.
    Kept for compatibility with the audit test.
    """

    if not isinstance(audit, dict):
        return "Advisor review required."

    return audit.get(
    "advisor_action",
    "Advisor review required."
    )
        
        
        