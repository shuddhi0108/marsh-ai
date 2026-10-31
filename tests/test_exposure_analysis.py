from src.company_profile import generate_company_profile
from src.build_knowledge_base import build_knowledge_base
from src.retriever import search_policy
from src.exposure_analysis import analyze_exposures


profile = generate_company_profile("Tata Motors")

index, chunks, sources, pages = build_knowledge_base()

query = "What benefits cover employee health and hospitalisation expenses?"

policy_results = search_policy(
    query,
    index,
    chunks,
    sources,
    pages
)

exposures = analyze_exposures(profile, policy_results)

for exposure in exposures:
    print("\nRisk:", exposure["risk"])
    print("Type:", exposure["type"])
    print("Relevant policies:")

    for result in exposure["relevant_policies"]:
        print("-", result["source"])
        