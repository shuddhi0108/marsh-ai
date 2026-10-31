from src.company_profile import generate_company_profile
from src.build_knowledge_base import build_knowledge_base
from src.retriever import search_policy
from src.exposure_analysis import analyze_exposures
from src.pitch_generator import generate_marketing_pitch
from src.audit import audit_pitch_content
from src.presentation_generator import create_pitch_deck


profile = generate_company_profile("Tata Motors")

index, chunks, sources, pages = build_knowledge_base()

query = "What benefits are relevant for employee health and hospitalisation expenses?"

policy_results = search_policy(
    query,
    index,
    chunks,
    sources,
    pages 
)

exposures = analyze_exposures(
    profile,
    policy_results
)

pitch = generate_marketing_pitch(
    profile,
    exposures
)

audit_report = audit_pitch_content(
    pitch,
    chunks,
    sources
)

output_file = "output/tata_motors_pitch.pptx"

create_pitch_deck(
    pitch,
    audit_report,
    output_file
)

print("\nPresentation created successfully:")
print(output_file)