from src.build_knowledge_base import build_knowledge_base
from src.retriever import search_policy


index, chunks, sources, pages = build_knowledge_base()
query = "What benefits are available for hospitalization?"

results = search_policy(
    query,
    index,
    chunks,
    sources,
    pages 
)

print("\nRelevant policy information:\n")

for result in results:
    print("Source:", result["source"])
    print(result["text"])
    print("\n---\n")