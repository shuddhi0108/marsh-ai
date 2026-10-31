from src.company_profile import generate_company_profile


profile = generate_company_profile("Tata Motors")

print("Company:", profile["company_name"])
print("Industry:", profile["industry"])
print("Size:", profile["employee_count"])

print("\nKey risks:")
for item in profile["key_risks"]:
    print("-", item["risk"], "(", item["type"], ")")