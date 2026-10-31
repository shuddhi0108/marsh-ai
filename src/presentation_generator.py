from pptx import Presentation


def create_pitch_deck(pitch, audit_report, output_file):

    if isinstance(pitch, str):
        import json

        pitch = pitch.replace("```json", "")
        pitch = pitch.replace("```", "")
        pitch = json.loads(pitch)

    presentation = Presentation()

    # Slide 1: Company Overview
    slide = presentation.slides.add_slide(
        presentation.slide_layouts[1]
    )

    slide.shapes.title.text = "Client Overview"

    slide.placeholders[1].text = (
        f"Company: {pitch['company_overview']}\n\n"
        "Identified exposures:\n"
        + "\n".join(
            f"• {item['risk']}"
            for item in pitch["policy_benefits"]
        )
    )

    # Slide 2: Why Marsh
    slide = presentation.slides.add_slide(
        presentation.slide_layouts[1]
    )

    slide.shapes.title.text = "Why Marsh"

    slide.placeholders[1].text = pitch["why_marsh"]

    # Slide 3: Policy Benefits
    slide = presentation.slides.add_slide(
        presentation.slide_layouts[1]
    )

    slide.shapes.title.text = "Policy Benefits"

    benefits = []

    for item in pitch["policy_benefits"]:
        benefits.append(
            f"{item['risk']}\n"
            f"{item['benefit']}\n"
            f"Source: {item['source']}"
        )

    slide.placeholders[1].text = "\n\n".join(benefits)

    # Slide 4: Recommendation
    slide = presentation.slides.add_slide(
        presentation.slide_layouts[1]
    )

    slide.shapes.title.text = "Recommended Policy"

    recommendation = pitch["recommendation"]

    slide.placeholders[1].text = (
        f"Policy: {recommendation['policy']}\n\n"
        f"Reason: {recommendation['reason']}"
    )

    # Slide 5: Audit Summary
    slide = presentation.slides.add_slide(
        presentation.slide_layouts[1]
    )

    slide.shapes.title.text = "AI Content Audit"

    slide.placeholders[1].text = (
        f"Overall Status: {audit_report['overall_status']}\n\n"
        f"Confidence Score: "
        f"{audit_report['confidence_score']}\n\n"
        f"Advisor Action: "
        f"{audit_report['advisor_action']}"
    )

    presentation.save(output_file)