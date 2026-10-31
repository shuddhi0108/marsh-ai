import os

from src.text_cleaner import clean_text
from src.chunker import create_chunks
from src.embeddings import create_embeddings
from src.vector_store import create_vector_store


def build_knowledge_base(selected_files=None):

    policy_folder = "data/processed"

    all_chunks = []
    all_sources = []
    all_pages = []

    if selected_files:

        available_files = {
            file_name
            for file_name in os.listdir(policy_folder)
            if file_name.endswith(".txt")
        }

        invalid_files = [
            file_name
            for file_name in selected_files
            if file_name not in available_files
        ]

        if invalid_files:
            raise ValueError(
                f"Invalid policy file(s): {invalid_files}"
            )

    for file_name in os.listdir(policy_folder):

        if not file_name.endswith(".txt"):
            continue

        if selected_files and file_name not in selected_files:
            continue

        file_path = os.path.join(
            policy_folder,
            file_name
        )

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:
            text = file.read()

        cleaned_text = clean_text(text)

        chunks = create_chunks(cleaned_text)

        for chunk in chunks:

            all_chunks.append(chunk["text"])
            all_sources.append(file_name)
            all_pages.append(chunk["page"])

    if not all_chunks:
        raise ValueError(
            "No policy documents were selected."
        )

    embeddings = create_embeddings(
        all_chunks
    )

    index = create_vector_store(
        embeddings
    )

    return (
        index,
        all_chunks,
        all_sources,
        all_pages
    )