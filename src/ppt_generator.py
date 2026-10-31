import os
import re
import subprocess

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.dml.color import RGBColor


# ============================================================
# MARSH-STYLE COLOUR PALETTE
# ============================================================

MARSH_BLUE = RGBColor(0, 43, 73)
MARSH_DARK = RGBColor(18, 35, 48)
MARSH_TEAL = RGBColor(0, 122, 140)
MARSH_LIGHT = RGBColor(238, 246, 248)

WHITE = RGBColor(255, 255, 255)
GREY = RGBColor(92, 105, 113)
LIGHT_GREY = RGBColor(225, 231, 234)

AMBER = RGBColor(190, 125, 30)


# ============================================================
# TEXT HELPERS
# ============================================================

def _clean_text(value):
    """
    Convert arbitrary values into clean presentation text.
    """

    if value is None:
        return ""

    if isinstance(value, list):
        return ", ".join(
            str(item).strip()
            for item in value
            if str(item).strip()
        )

    if isinstance(value, dict):
        return ", ".join(
            f"{key}: {value}"
            for key, value in value.items()
        )

    text = str(value)

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    return text


def _safe_list(value):
    """
    Always return a list.
    """

    if isinstance(value, list):
        return value

    if value:
        return [value]

    return []


def _truncate(text, max_chars):
    """
    Soft truncation.

    We avoid cutting sentences whenever possible.
    """

    text = _clean_text(text)

    if len(text) <= max_chars:
        return text

    shortened = text[:max_chars]

    sentence_end = max(
        shortened.rfind(". "),
        shortened.rfind("! "),
        shortened.rfind("? ")
    )

    if sentence_end >= int(max_chars * 0.55):
        return shortened[:sentence_end + 1].strip()

    last_space = shortened.rfind(" ")

    if last_space > 0:
        shortened = shortened[:last_space]

    return shortened.rstrip(" ,;:-") + "…"


def _adaptive_font(text, short_size, long_size, threshold=180):
    """
    Reduce font size for longer text.
    """

    text = _clean_text(text)

    if len(text) <= threshold:
        return short_size

    if len(text) <= threshold * 1.5:
        return max(long_size, short_size - 1)

    if len(text) <= threshold * 2:
        return max(long_size - 1, short_size - 2)

    return long_size


# ============================================================
# PRESENTATION STYLE
# ============================================================

def _add_background(slide, colour=WHITE):

    fill = slide.background.fill

    fill.solid()
    fill.fore_color.rgb = colour


def _add_top_bar(slide):

    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        0,
        0,
        Inches(13.333),
        Inches(0.13)
    )

    shape.fill.solid()
    shape.fill.fore_color.rgb = MARSH_TEAL
    shape.line.fill.background()


def _add_footer(slide, slide_number):

    line = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0.65),
        Inches(7.02),
        Inches(12.0),
        Inches(0.01)
    )

    line.fill.solid()
    line.fill.fore_color.rgb = LIGHT_GREY
    line.line.fill.background()

    textbox = slide.shapes.add_textbox(
        Inches(0.65),
        Inches(7.07),
        Inches(10.8),
        Inches(0.22)
    )

    tf = textbox.text_frame
    tf.clear()

    p = tf.paragraphs[0]

    run = p.add_run()

    run.text = (
        "Marsh Client Advisor  •  AI-generated draft "
        "subject to advisor review"
    )

    run.font.name = "Aptos"
    run.font.size = Pt(7.5)
    run.font.color.rgb = GREY

    number_box = slide.shapes.add_textbox(
        Inches(12.15),
        Inches(7.05),
        Inches(0.5),
        Inches(0.22)
    )

    ntf = number_box.text_frame
    ntf.clear()

    np = ntf.paragraphs[0]

    nr = np.add_run()
    nr.text = str(slide_number)

    nr.font.name = "Aptos"
    nr.font.size = Pt(8)
    nr.font.color.rgb = GREY

    np.alignment = PP_ALIGN.RIGHT


def _add_title(
    slide,
    title,
    subtitle=None
):

    title_box = slide.shapes.add_textbox(
        Inches(0.65),
        Inches(0.42),
        Inches(12.0),
        Inches(0.62)
    )

    tf = title_box.text_frame

    tf.clear()
    tf.word_wrap = True

    p = tf.paragraphs[0]

    run = p.add_run()

    run.text = _clean_text(title)

    run.font.name = "Aptos Display"
    run.font.bold = True
    run.font.size = Pt(27)
    run.font.color.rgb = MARSH_BLUE

    if subtitle:

        subtitle_box = slide.shapes.add_textbox(
            Inches(0.67),
            Inches(1.05),
            Inches(11.8),
            Inches(0.45)
        )

        stf = subtitle_box.text_frame

        stf.clear()
        stf.word_wrap = True

        sp = stf.paragraphs[0]

        sr = sp.add_run()

        sr.text = _truncate(
            subtitle,
            180
        )

        sr.font.name = "Aptos"
        sr.font.size = Pt(11)
        sr.font.color.rgb = GREY


def _add_text_box(
    slide,
    x,
    y,
    w,
    h,
    text,
    font_size=13,
    colour=MARSH_DARK,
    bold=False,
    alignment=PP_ALIGN.LEFT,
    fill_colour=None,
    margin=0.12
):

    if fill_colour is not None:

        shape = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(x),
            Inches(y),
            Inches(w),
            Inches(h)
        )

        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_colour

        shape.line.color.rgb = LIGHT_GREY

        textbox = slide.shapes.add_textbox(
            Inches(x + margin),
            Inches(y + margin),
            Inches(w - 2 * margin),
            Inches(h - 2 * margin)
        )

    else:

        textbox = slide.shapes.add_textbox(
            Inches(x),
            Inches(y),
            Inches(w),
            Inches(h)
        )

    tf = textbox.text_frame

    tf.clear()
    tf.word_wrap = True

    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0

    tf.vertical_anchor = MSO_ANCHOR.TOP

    p = tf.paragraphs[0]

    p.alignment = alignment

    run = p.add_run()

    run.text = _clean_text(text)

    run.font.name = "Aptos"
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = colour

    return textbox


def _add_bullet_list(
    slide,
    items,
    x,
    y,
    w,
    h,
    font_size=13,
    colour=MARSH_DARK,
    max_chars=190
):

    items = [
        _clean_text(item)
        for item in _safe_list(items)
        if _clean_text(item)
    ]

    if not items:
        return

    textbox = slide.shapes.add_textbox(
        Inches(x),
        Inches(y),
        Inches(w),
        Inches(h)
    )

    tf = textbox.text_frame

    tf.clear()
    tf.word_wrap = True

    tf.margin_left = Inches(0.03)
    tf.margin_right = Inches(0.03)
    tf.margin_top = Inches(0.02)
    tf.margin_bottom = Inches(0.02)

    for index, item in enumerate(items):

        p = (
            tf.paragraphs[0]
            if index == 0
            else tf.add_paragraph()
        )

        clean_item = _truncate(
            item,
            max_chars
        )

        p.text = "• " + clean_item

        p.font.name = "Aptos"
        p.font.size = Pt(
            _adaptive_font(
                clean_item,
                font_size,
                max(font_size - 2, 9),
                150
            )
        )
        p.font.color.rgb = colour

        p.space_after = Pt(7)

    return textbox


def _add_section_label(
    slide,
    x,
    y,
    text,
    width=3.0
):

    textbox = slide.shapes.add_textbox(
        Inches(x),
        Inches(y),
        Inches(width),
        Inches(0.3)
    )

    tf = textbox.text_frame

    tf.clear()

    p = tf.paragraphs[0]

    run = p.add_run()

    run.text = _clean_text(text).upper()

    run.font.name = "Aptos"
    run.font.bold = True
    run.font.size = Pt(9)
    run.font.color.rgb = MARSH_TEAL


def _add_card(
    slide,
    x,
    y,
    w,
    h,
    heading,
    body,
    accent=MARSH_TEAL,
    body_size=11.5
):

    card = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(x),
        Inches(y),
        Inches(w),
        Inches(h)
    )

    card.fill.solid()
    card.fill.fore_color.rgb = WHITE

    card.line.color.rgb = LIGHT_GREY

    strip = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(x),
        Inches(y),
        Inches(0.06),
        Inches(h)
    )

    strip.fill.solid()
    strip.fill.fore_color.rgb = accent
    strip.line.fill.background()

    heading_text = _clean_text(heading)

    _add_text_box(
        slide,
        x + 0.22,
        y + 0.18,
        w - 0.4,
        0.35,
        heading_text,
        font_size=13,
        colour=MARSH_BLUE,
        bold=True
    )

    body_text = _clean_text(body)

    _add_text_box(
        slide,
        x + 0.22,
        y + 0.62,
        w - 0.4,
        h - 0.78,
        _truncate(body_text, 260),
        font_size=_adaptive_font(
            body_text,
            body_size,
            9.5,
            170
        ),
        colour=MARSH_DARK
    )


# ============================================================
# SLIDE 1 — COMPANY OVERVIEW
# ============================================================

def _slide_company_overview(
    prs,
    profile,
    company_overview,
    slide_number
):

    slide = prs.slides.add_slide(
        prs.slide_layouts[6]
    )

    _add_background(
        slide,
        WHITE
    )

    _add_top_bar(slide)

    # Use pitch-generated company overview where available.
    company_name = _clean_text(
        company_overview.get(
            "company_name",
            profile.get(
                "company_name",
                "Client"
            )
        )
    )

    _add_title(
        slide,
        company_name,
        "Client profile and employee health priorities"
    )

    industry = _clean_text(
        company_overview.get(
            "industry",
            profile.get(
                "industry",
                "Not available"
            )
        )
    )

    employees = _clean_text(
        company_overview.get(
            "employee_count",
            profile.get(
                "employee_count",
                "Not available"
            )
        )
    )

    location = _clean_text(
        company_overview.get(
            "location",
            profile.get(
                "location",
                "Not available"
            )
        )
    )

    requirements = _clean_text(
        company_overview.get(
            "requirements",
            profile.get(
                "requirements",
                "Not specified"
            )
        )
    )

    _add_card(
        slide,
        0.65,
        1.62,
        3.75,
        1.3,
        "Industry",
        industry
    )

    _add_card(
        slide,
        4.75,
        1.62,
        3.75,
        1.3,
        "Workforce",
        employees
    )

    _add_card(
        slide,
        8.85,
        1.62,
        3.75,
        1.3,
        "Location",
        location
    )

    _add_section_label(
        slide,
        0.7,
        3.15,
        "Client requirement"
    )

    _add_text_box(
        slide,
        0.7,
        3.52,
        11.9,
        1.15,
        _truncate(
            requirements,
            480
        ),
        font_size=_adaptive_font(
            requirements,
            15.5,
            12,
            260
        ),
        colour=MARSH_DARK,
        fill_colour=MARSH_LIGHT
    )

    observations = _safe_list(
        company_overview.get(
            "observations",
            []
        )
    )

    if not observations:

        observations = _safe_list(
            profile.get(
                "observations",
                []
            )
        )

    if observations:

        _add_section_label(
            slide,
            0.7,
            5.02,
            "Key observations"
        )

        _add_bullet_list(
            slide,
            observations[:3],
            0.72,
            5.37,
            11.8,
            1.15,
            font_size=12.5,
            max_chars=175
        )

    _add_footer(
        slide,
        slide_number
    )


# ============================================================
# SLIDE 2 — WHY MARSH
# ============================================================

def _slide_why_marsh(
    prs,
    why_marsh,
    slide_number
):

    slide = prs.slides.add_slide(
        prs.slide_layouts[6]
    )

    _add_background(
        slide,
        WHITE
    )

    _add_top_bar(slide)

    _add_title(
        slide,
        "Why Choose Marsh?",
        "Turning client-specific exposures into an evidence-based insurance strategy"
    )

    raw_points = _safe_list(
        why_marsh.get(
            "points",
            []
        )
    )

    # Fallback headings, used only when a point doesn't carry its
    # own heading (e.g. it arrived as a plain string rather than
    # the expected {"heading": ..., "text": ...} shape).
    fallback_headings = [
        "Client-specific advisory",
        "Policy intelligence",
        "Evidence-based recommendations",
        "Advisor oversight"
    ]

    # Each point is a {"heading": ..., "text": ...} dict. Previously
    # this ran _clean_text() on the whole dict, which - for a dict -
    # joins every key/value pair into one string ("heading: X, text:
    # Y"), so the literal word "heading:" ended up printed on the
    # slide instead of being used as an actual heading. Pull the two
    # fields out separately instead.
    normalized_points = []

    for index, point in enumerate(raw_points):

        if isinstance(point, dict):

            heading = _clean_text(
                point.get("heading", "")
            ) or (
                fallback_headings[index]
                if index < len(fallback_headings)
                else ""
            )

            text = _clean_text(
                point.get("text", "")
            )

        else:

            heading = (
                fallback_headings[index]
                if index < len(fallback_headings)
                else ""
            )

            text = _clean_text(point)

        if text:
            normalized_points.append((heading, text))

    normalized_points = normalized_points[:4]

    positions = [
        (0.7, 1.72),
        (6.85, 1.72),
        (0.7, 4.02),
        (6.85, 4.02)
    ]

    for index, (heading, text) in enumerate(normalized_points):

        x, y = positions[index]

        _add_card(
            slide,
            x,
            y,
            5.75,
            1.82,
            heading,
            text,
            accent=MARSH_TEAL,
            body_size=11.5
        )

    _add_footer(
        slide,
        slide_number
    )


# ============================================================
# SLIDE 3 — POLICY MAPPING
# ============================================================

def _slide_policy_mapping(
    prs,
    policy_mapping,
    slide_number
):

    slide = prs.slides.add_slide(
        prs.slide_layouts[6]
    )

    _add_background(
        slide,
        WHITE
    )

    _add_top_bar(slide)

    _add_title(
        slide,
        "Policy Benefits Mapped to Client Exposures",
        "Relevant policy evidence identified from the supplied documents"
    )

    mappings = [
        item
        for item in _safe_list(policy_mapping)
        if isinstance(item, dict)
    ]

    # Keep the slide visually manageable.
    mappings = mappings[:3]

    if not mappings:

        _add_text_box(
            slide,
            0.8,
            2.0,
            11.5,
            1.2,
            "No policy matches were returned. Advisor review is required.",
            font_size=17,
            colour=AMBER,
            bold=True,
            fill_colour=MARSH_LIGHT
        )

        _add_footer(
            slide,
            slide_number
        )

        return

    # --------------------------------------------------------
    # Column headings
    # --------------------------------------------------------

    _add_section_label(
        slide,
        0.7,
        1.55,
        "CLIENT EXPOSURE",
        width=2.3
    )

    _add_section_label(
        slide,
        3.05,
        1.55,
        "WHY IT MATTERS",
        width=2.8
    )

    _add_section_label(
        slide,
        5.95,
        1.55,
        "POLICY BENEFIT",
        width=3.7
    )

    _add_section_label(
        slide,
        9.75,
        1.55,
        "SOURCE",
        width=2.6
    )

    # --------------------------------------------------------
    # Rows
    # --------------------------------------------------------

    y_positions = [
        1.95,
        3.48,
        5.01
    ]

    for index, item in enumerate(mappings):

        y = y_positions[index]

        exposure = _clean_text(
            item.get(
                "exposure",
                "Not specified"
            )
        )

        why = _clean_text(
            item.get(
                "why_it_matters",
                "Not specified"
            )
        )

        benefit = _clean_text(
            item.get(
                "benefit",
                "Not specified"
            )
        )

        policy = _clean_text(
            item.get(
                "policy",
                "Not specified"
            )
        )

        source = _clean_text(
            item.get(
                "source",
                "Policy document"
            )
        )

        # Light background card for every row.
        row = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(0.65),
            Inches(y),
            Inches(12.0),
            Inches(1.28)
        )

        row.fill.solid()

        row.fill.fore_color.rgb = (
            MARSH_LIGHT
            if index % 2 == 0
            else WHITE
        )

        row.line.color.rgb = LIGHT_GREY

        # Exposure
        _add_text_box(
            slide,
            0.82,
            y + 0.17,
            2.05,
            0.9,
            _truncate(
                exposure,
                100
            ),
            font_size=_adaptive_font(
                exposure,
                10.5,
                9,
                75
            ),
            colour=MARSH_BLUE,
            bold=True
        )

        # Why it matters
        _add_text_box(
            slide,
            3.05,
            y + 0.17,
            2.65,
            0.9,
            _truncate(
                why,
                150
            ),
            font_size=_adaptive_font(
                why,
                9.8,
                8.7,
                105
            ),
            colour=MARSH_DARK
        )

        # Policy + benefit
        policy_text = (
            policy
            + "\n"
            + _truncate(
                benefit,
                210
            )
        )

        _add_text_box(
            slide,
            5.95,
            y + 0.14,
            3.55,
            0.98,
            policy_text,
            font_size=_adaptive_font(
                benefit,
                9.5,
                8.4,
                135
            ),
            colour=MARSH_DARK
        )

        # Source
        _add_text_box(
            slide,
            9.75,
            y + 0.17,
            2.55,
            0.9,
            _truncate(
                source,
                100
            ),
            font_size=_adaptive_font(
                source,
                9.2,
                8.2,
                70
            ),
            colour=GREY
        )

    _add_footer(
        slide,
        slide_number
    )


# ============================================================
# SLIDE 4 — FINAL RECOMMENDATION
# ============================================================

def _slide_recommendation(
    prs,
    recommendation,
    slide_number
):

    slide = prs.slides.add_slide(
        prs.slide_layouts[6]
    )

    _add_background(
        slide,
        MARSH_LIGHT
    )

    _add_top_bar(slide)

    _add_title(
        slide,
        "Recommended Policy",
        "Final recommendation based on the client's identified exposures and supplied policy evidence"
    )

    policy_name = _clean_text(
        recommendation.get(
            "policy",
            "Recommendation requires advisor review"
        )
    )

    # --------------------------------------------------------
    # Main policy panel
    # --------------------------------------------------------

    panel = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.7),
        Inches(1.62),
        Inches(11.9),
        Inches(1.18)
    )

    panel.fill.solid()
    panel.fill.fore_color.rgb = WHITE
    panel.line.color.rgb = LIGHT_GREY

    _add_text_box(
        slide,
        1.0,
        1.91,
        11.3,
        0.55,
        _truncate(
            policy_name,
            100
        ),
        font_size=22,
        colour=MARSH_BLUE,
        bold=True,
        alignment=PP_ALIGN.CENTER
    )

    # --------------------------------------------------------
    # Rationale
    # --------------------------------------------------------

    _add_section_label(
        slide,
        0.75,
        3.13,
        "Why this policy aligns"
    )

    rationale = _safe_list(
        recommendation.get(
            "rationale",
            []
        )
    )

    _add_bullet_list(
        slide,
        rationale[:3],
        0.8,
        3.52,
        5.85,
        2.25,
        font_size=12,
        max_chars=175
    )

    # --------------------------------------------------------
    # Supporting benefits
    # --------------------------------------------------------

    _add_section_label(
        slide,
        7.0,
        3.13,
        "Supporting benefits"
    )

    benefits = _safe_list(
        recommendation.get(
            "supporting_benefits",
            []
        )
    )

    _add_bullet_list(
        slide,
        benefits[:3],
        7.05,
        3.52,
        5.35,
        2.25,
        font_size=12,
        max_chars=175
    )

    # --------------------------------------------------------
    # Sources
    # --------------------------------------------------------

    sources = _safe_list(
        recommendation.get(
            "sources",
            []
        )
    )

    if sources:

        source_text = (
            "Source evidence: "
            + ", ".join(
                _clean_text(source)
                for source in sources[:3]
                if _clean_text(source)
            )
        )

        _add_text_box(
            slide,
            0.8,
            6.03,
            11.5,
            0.55,
            _truncate(
                source_text,
                240
            ),
            font_size=8.5,
            colour=GREY
        )

    _add_footer(
        slide,
        slide_number
    )


# ============================================================
# SLIDE 5 — CLIENT CONVERSATION
# ============================================================

def _slide_client_pitch(
    prs,
    client_pitch,
    slide_number
):

    slide = prs.slides.add_slide(
        prs.slide_layouts[6]
    )

    _add_background(
        slide,
        WHITE
    )

    _add_top_bar(slide)

    headline = _clean_text(
        client_pitch.get(
            "headline",
            "A more focused approach to employee health protection"
        )
    )

    _add_title(
        slide,
        "Client Conversation",
        headline
    )

    body = _clean_text(
        client_pitch.get(
            "body",
            ""
        )
    )

    # --------------------------------------------------------
    # Main client message
    # --------------------------------------------------------

    _add_text_box(
        slide,
        0.75,
        1.7,
        11.8,
        1.95,
        _truncate(
            body,
            850
        ),
        font_size=_adaptive_font(
            body,
            15.5,
            11.5,
            400
        ),
        colour=MARSH_DARK,
        fill_colour=MARSH_LIGHT
    )

    # --------------------------------------------------------
    # Next steps
    # --------------------------------------------------------

    _add_section_label(
        slide,
        0.75,
        4.02,
        "Recommended next steps"
    )

    next_steps = _safe_list(
        client_pitch.get(
            "next_steps",
            []
        )
    )

    _add_bullet_list(
        slide,
        next_steps[:4],
        0.8,
        4.4,
        11.6,
        1.65,
        font_size=12.5,
        max_chars=180
    )

    # --------------------------------------------------------
    # Advisor disclaimer
    # --------------------------------------------------------

    _add_text_box(
        slide,
        0.8,
        6.25,
        11.5,
        0.45,
        (
            "AI-generated advisory draft — policy terms, eligibility, "
            "limits and exclusions should be validated by a Marsh "
            "advisor before client use."
        ),
        font_size=8.5,
        colour=GREY
    )

    _add_footer(
        slide,
        slide_number
    )


# ============================================================
# MAIN PPT GENERATOR
# ============================================================

def create_pitch_ppt(
    profile,
    pitch,
    audit_report,
    output_path
):
    """
    Create the final 5-slide client-facing Marsh pitch.

    The audit report is deliberately NOT rendered as a slide.
    It remains an internal output saved separately by app.py.
    """

    prs = Presentation()

    # Widescreen 16:9
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    # --------------------------------------------------------
    # Remove default blank slide
    # --------------------------------------------------------

    if len(prs.slides) > 0:

        xml_slides = prs.slides._sldIdLst

        for slide_id in list(xml_slides):
            xml_slides.remove(slide_id)

    # --------------------------------------------------------
    # Slide 1
    # --------------------------------------------------------

    _slide_company_overview(
        prs,
        profile,
        pitch.get(
            "company_overview",
            {}
        ),
        1
    )

    # --------------------------------------------------------
    # Slide 2
    # --------------------------------------------------------

    _slide_why_marsh(
        prs,
        pitch.get(
            "why_marsh",
            {}
        ),
        2
    )

    # --------------------------------------------------------
    # Slide 3
    # --------------------------------------------------------

    _slide_policy_mapping(
        prs,
        pitch.get(
            "policy_mapping",
            []
        ),
        3
    )

    # --------------------------------------------------------
    # Slide 4
    # --------------------------------------------------------

    _slide_recommendation(
        prs,
        pitch.get(
            "recommended_policy",
            {}
        ),
        4
    )

    # --------------------------------------------------------
    # Slide 5
    # --------------------------------------------------------

    _slide_client_pitch(
        prs,
        pitch.get(
            "client_pitch",
            {}
        ),
        5
    )

    # --------------------------------------------------------
    # Save PPT
    # --------------------------------------------------------

    output_directory = os.path.dirname(
        output_path
    )

    if output_directory:

        os.makedirs(
            output_directory,
            exist_ok=True
        )

    prs.save(
        output_path
    )

    # --------------------------------------------------------
    # Optional PDF generation
    # --------------------------------------------------------

    pdf_path = (
        os.path.splitext(output_path)[0]
        + ".pdf"
    )

    soffice_path = "/opt/homebrew/bin/soffice"

    if os.path.exists(soffice_path):

        try:

            subprocess.run(
                [
                    soffice_path,
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    output_directory or ".",
                    output_path
                ],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=120
            )

        except Exception:

            # PDF generation is optional.
            # PPT generation should still succeed.
            pass

    return output_path