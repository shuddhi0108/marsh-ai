from flask import Flask, request, jsonify, send_from_directory
import os
import json

from src.ppt_generator import create_pitch_ppt
from src.company_profile import generate_company_profile
from src.build_knowledge_base import build_knowledge_base
from src.retriever import search_policy_diverse
from src.exposure_analysis import analyze_exposures
from src.pitch_generator import generate_marketing_pitch
from src.audit import audit_pitch_content


# A single generic query with a small top_k was starving the
# generator of real evidence (see retriever.py notes). Instead
# we run several targeted queries covering the distinct topics
# a pitch needs, and merge/deduplicate the results so each
# policy document gets a fair chance to surface its own clauses.
EVIDENCE_QUERIES = [
    "hospitalization expenses coverage and capping limits",
    "out-of-pocket and non-medical expense coverage",
    "day care treatment and domiciliary home healthcare coverage",
    "employee health and medical insurance benefits",
    "waiting periods, exclusions and eligibility conditions",
]

# How many regeneration attempts before we give up and return
# the failing pitch anyway, flagged for mandatory advisor review.
MAX_GENERATION_ATTEMPTS = 2


def _generate_and_audit_pitch(profile, exposures, policy_results, chunks, sources, pages):
    """
    Generate a pitch and audit it. If the audit fails, retry once
    with the same (now much richer) evidence - a single bad LLM
    sample shouldn't be the only chance a pitch gets. If it still
    fails after MAX_GENERATION_ATTEMPTS, return the last attempt
    with the audit result attached so the caller can decide what
    to do - we never silently ship a failed pitch as if it passed.
    """

    last_pitch = None
    last_audit = None

    for attempt in range(1, MAX_GENERATION_ATTEMPTS + 1):

        pitch = generate_marketing_pitch(
            profile,
            exposures,
            policy_results
        )

        audit_report = audit_pitch_content(
            pitch,
            chunks,
            sources,
            pages
        )

        last_pitch = pitch
        last_audit = audit_report

        if audit_report.get("overall_status") in ("PASS", "REVIEW"):
            return pitch, audit_report, attempt

    return last_pitch, last_audit, MAX_GENERATION_ATTEMPTS


app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    """Lightweight health check for Docker and Kubernetes probes."""
    return jsonify({"status": "healthy"}), 200

@app.route("/")
def home():
    return send_from_directory(
        "templates",
        "index.html"
    )


@app.route("/generate-pitch", methods=["POST"])
def generate_pitch():

    try:
        data = request.get_json() or {}

        company_name = data.get("company_name", "").strip()

        if not company_name:
            return jsonify({
                "error": "Company name is required"
            }), 400

        selected_files = data.get("policy_files")

        if not selected_files:
            return jsonify({
                "error": "At least one policy document is required"
            }), 400

        profile = generate_company_profile(company_name)

        index, chunks, sources, pages = build_knowledge_base(
            selected_files
        )

        policy_results = search_policy_diverse(
            EVIDENCE_QUERIES,
            index,
            chunks,
            sources,
            pages
        )

        exposures = analyze_exposures(
            profile,
            policy_results
        )

        pitch, audit_report, attempts = _generate_and_audit_pitch(
            profile,
            exposures,
            policy_results,
            chunks,
            sources,
            pages
        )

        return jsonify({
            "company_profile": profile,
            "exposures": exposures,
            "pitch": pitch,
            "audit": audit_report,
            "generation_attempts": attempts,
            "requires_advisor_review":
                audit_report.get("overall_status") != "PASS"
        })

    except Exception as e:

        return jsonify({
            "error": "Pitch generation failed",
            "details": str(e)
        }), 500


@app.route("/generate-ppt", methods=["POST"])
def generate_ppt():

    try:

        data = request.get_json() or {}

        company_name = data.get(
            "company_name",
            ""
        ).strip()

        industry = data.get(
            "industry",
            ""
        ).strip()

        employee_count = data.get(
            "employee_count",
            ""
        )

        location = data.get(
            "location",
            ""
        ).strip()

        requirements = data.get(
            "requirements",
            ""
        ).strip()

        selected_files = data.get(
            "policy_files"
        )

        if not company_name:

            return jsonify({
                "error": "Company name is required"
            }), 400

        if not selected_files:

            return jsonify({
                "error": "At least one policy document is required"
            }), 400

        # ---------------------------------------------------------
        # 1. Generate company profile
        # ---------------------------------------------------------

        profile = generate_company_profile(
            company_name
        )

        # Add information explicitly entered by the user.
        # User-provided information takes priority over assumptions.

        if industry:
            profile["industry"] = industry

        if employee_count:

            try:
                profile["employee_count"] = int(
                    employee_count
                )

            except (ValueError, TypeError):

                profile["employee_count"] = employee_count

        if location:
            profile["location"] = location

        if requirements:
            profile["requirements"] = requirements

        # ---------------------------------------------------------
        # 2. Build policy knowledge base
        # ---------------------------------------------------------

        index, chunks, sources, pages = build_knowledge_base(
            selected_files
        )

        if not chunks:

            return jsonify({
                "error": "No policy content could be extracted from the supplied documents."
            }), 400

        # ---------------------------------------------------------
        # 3. Retrieve policy evidence
        # ---------------------------------------------------------

        policy_results = search_policy_diverse(
            EVIDENCE_QUERIES,
            index,
            chunks,
            sources,
            pages
        )

        if not policy_results:

            return jsonify({
                "error": "No relevant policy information was found."
            }), 400

        # ---------------------------------------------------------
        # 4. Analyse client exposures
        # ---------------------------------------------------------

        exposures = analyze_exposures(
            profile,
            policy_results
        )

        # ---------------------------------------------------------
        # 5. Generate pitch + audit it, retrying once on failure.
        #
        # Previously the pitch was generated once and the audit
        # result was computed but NEVER checked - a pitch that
        # failed audit with 0% confidence still got turned into a
        # "Presentation generated successfully" PPTX. Now:
        #   - we retry generation if the audit fails, since richer
        #     evidence (see EVIDENCE_QUERIES above) usually fixes it
        #   - we still deliver the file even after a final FAIL, so
        #     the advisor has something to review, but the response
        #     clearly marks it as requiring review/rejection instead
        #     of silently saying "success"
        # ---------------------------------------------------------

        pitch, audit_report, attempts = _generate_and_audit_pitch(
            profile,
            exposures,
            policy_results,
            chunks,
            sources,
            pages
        )

        # ---------------------------------------------------------
        # 7. Prepare output directory
        # ---------------------------------------------------------

        os.makedirs(
            "output",
            exist_ok=True
        )

        output_path = os.path.join(
            "output",
            "marsh_client_advisor.pptx"
        )

        audit_path = os.path.join(
            "output",
            "marsh_client_advisor_audit.json"
        )

        # ---------------------------------------------------------
        # 8. Save internal audit report
        # ---------------------------------------------------------

        with open(
            audit_path,
            "w",
            encoding="utf-8"
        ) as audit_file:

            json.dump(
                audit_report,
                audit_file,
                indent=4,
                ensure_ascii=False,
                default=str
            )

        # ---------------------------------------------------------
        # 9. Generate client-facing PowerPoint
        # ---------------------------------------------------------

        create_pitch_ppt(
            profile,
            pitch,
            audit_report,
            output_path
        )

        # ---------------------------------------------------------
        # 10. Verify PPT creation
        # ---------------------------------------------------------

        if not os.path.exists(output_path):

            return jsonify({
                "error": "PPT generation failed",
                "details": "The PowerPoint file was not created."
            }), 500

        overall_status = audit_report.get("overall_status", "REVIEW")

        if overall_status == "PASS":
            message = "Presentation generated and passed audit."
        elif overall_status == "REVIEW":
            message = (
                "Presentation generated, but some claims need "
                "advisor verification before client use."
            )
        else:
            message = (
                "Presentation generated, but FAILED audit - "
                "do not send to the client until unsupported "
                "claims are corrected."
            )

        return jsonify({

            "message": message,

            "file":
                "marsh_client_advisor.pptx",

            "download_url":
                "/download-ppt",

            "audit_file":
                "marsh_client_advisor_audit.json",

            "audit_summary": {
                "overall_status": overall_status,
                "confidence_score": audit_report.get("confidence_score"),
                "claims_checked": audit_report.get("claims_checked"),
                "review_claims": audit_report.get("review_claims"),
                "unsupported_claims": audit_report.get("unsupported_claims"),
                "advisor_action": audit_report.get("advisor_action"),
            },

            "generation_attempts": attempts,

            "requires_advisor_review": overall_status != "PASS"
        })

    except Exception as e:

        return jsonify({

            "error":
                "PPT generation failed",

            "details":
                str(e)

        }), 500


@app.route("/download-ppt", methods=["GET"])
def download_ppt():

    file_path = os.path.join(
        "output",
        "marsh_client_advisor.pptx"
    )

    if not os.path.exists(file_path):

        return jsonify({
            "error": "Presentation file not found"
        }), 404

    return send_from_directory(

        "output",

        "marsh_client_advisor.pptx",

        as_attachment=True,

        download_name=
            "marsh_client_advisor.pptx"
    )


@app.route("/download-audit", methods=["GET"])
def download_audit():

    file_path = os.path.join(
        "output",
        "marsh_client_advisor_audit.json"
    )

    if not os.path.exists(file_path):

        return jsonify({
            "error": "Audit report not found"
        }), 404

    return send_from_directory(

        "output",

        "marsh_client_advisor_audit.json",

        as_attachment=True,

        download_name=
            "marsh_client_advisor_audit.json"
    )


if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5001,
        debug=True
    )