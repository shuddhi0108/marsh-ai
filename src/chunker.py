def create_chunks(text, chunk_size=500):
    """
    Create page-aware chunks.

    The processed policy text contains markers such as:
        --- PAGE 1 ---

    Each chunk keeps its page number so retrieved
    evidence can be traced back to the source page.
    """

    chunks = []

    current_page = 1
    current_words = []

    for line in text.splitlines():

        line = line.strip()

        if not line:
            continue

        # Detect page markers created by pdf_extractor.py
        if line.startswith("--- PAGE ") and line.endswith(" ---"):

            if current_words:
                for i in range(0, len(current_words), chunk_size):
                    words = current_words[i:i + chunk_size]

                    chunks.append({
                        "text": " ".join(words),
                        "page": current_page
                    })

            try:
                current_page = int(
                    line.replace("--- PAGE ", "")
                        .replace(" ---", "")
                        .strip()
                )
            except ValueError:
                pass

            current_words = []
            continue

        current_words.extend(line.split())

    # Add the final page
    if current_words:
        for i in range(0, len(current_words), chunk_size):
            words = current_words[i:i + chunk_size]

            chunks.append({
                "text": " ".join(words),
                "page": current_page
            })

    return chunks