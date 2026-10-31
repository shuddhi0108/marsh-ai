from src.embeddings import model


def search_policy(
    query,
    index,
    chunks,
    sources,
    pages,
    top_k=10
):

    query_embedding = model.encode([query])

    top_k = min(top_k, len(chunks))

    distances, indices = index.search(
        query_embedding,
        top_k
    )

    results = []

    for i in indices[0]:

        if i < 0:
            continue

        results.append({
            "text": chunks[i],
            "source": sources[i],
            "page": pages[i]
        })

    return results


def search_policy_diverse(
    queries,
    index,
    chunks,
    sources,
    pages,
    top_k_per_query=6
):

    seen = set()
    merged = []

    for query in queries:

        results = search_policy(
            query,
            index,
            chunks,
            sources,
            pages,
            top_k=top_k_per_query
        )

        for result in results:

            key = (
                result["source"],
                result["page"],
                result["text"]
            )

            if key in seen:
                continue

            seen.add(key)
            merged.append(result)

    return merged