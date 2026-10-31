import fitz


def extract_pdf(file_path):
    pdf = fitz.open(file_path)

    pages = []

    for page in pdf:
        text = page.get_text()
        pages.append(text)

    pdf.close()

    return pages


def save_text(pages, output_file):
    with open(output_file, "w", encoding="utf-8") as file:
        for i, page in enumerate(pages):
            file.write(f"\n--- PAGE {i + 1} ---\n")
            file.write(page)