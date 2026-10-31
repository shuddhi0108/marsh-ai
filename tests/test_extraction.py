from src.text_cleaner import clean_text
from src.chunker import create_chunks
from src.embeddings import create_embeddings
from src.vector_store import create_vector_store
from src.retriever import search_policy


file_path = "data/processed/ABHI Product Brochure.txt"

with open(file_path, "r", encoding="utf-8") as file:
    text = file.read()

cleaned_text = clean_text(text)

# create_chunks returns a list of {"text": ..., "page": ...} dicts,
# not raw strings - create_embeddings/search_policy need the text
# and page pulled out into their own parallel lists.
chunk_dicts = create_chunks(cleaned_text)

chunks = [chunk["text"] for chunk in chunk_dicts]
sources = ["ABHI Product Brochure.txt"] * len(chunks)
pages = [chunk["page"] for chunk in chunk_dicts]

embeddings = create_embeddings(chunks)

index = create_vector_store(embeddings)

query = "What benefits does this policy provide?"

results = search_policy(query, index, chunks, sources, pages)

print("\nRelevant policy information:\n")

for result in results:
    print(result)
    print("\n---\n")