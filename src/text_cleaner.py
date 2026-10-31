import re


def clean_text(text):
    """
    Normalize whitespace WITHOUT collapsing line breaks.

    chunker.py detects page markers ("--- PAGE N ---") by
    scanning line by line. The previous version replaced every
    run of whitespace - including newlines - with a single
    space, which merged the entire document into one line and
    made every page marker undetectable. That silently broke
    page-aware chunking: every chunk ended up attributed to
    page 1, and the literal "--- PAGE N ---" tokens leaked into
    the evidence text itself.

    This keeps line breaks intact and only tidies up horizontal
    whitespace (spaces/tabs) within each line, plus drops blank
    lines.
    """

    lines = text.splitlines()

    cleaned_lines = []

    for line in lines:
        line = re.sub(r"[ \t]+", " ", line).strip()

        if line:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)