# Sample data

The CSVs, resumes, performance reviews and project reports in this folder are **synthetic demo data** generated for this project. The generator uses Faker with a fixed seed so the sample dataset can be recreated. They are not intended to represent real employees, candidates or company records.

- `raw/` — generated CSV tables loaded into PostgreSQL.
- `docs/` — sample policy, resume, review and project documents used for document retrieval.
- `extracted/` — example structured extractions used when constructing the knowledge graph. These can be regenerated with the Groq extraction step.
- `ground_truth/` — evaluation facts used by the graph extraction evaluation.

To regenerate the synthetic source data, run `python -m src.data_gen.generate_data` from the repository root. This overwrites the generated CSVs and sample documents.
