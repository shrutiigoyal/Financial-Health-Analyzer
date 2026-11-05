# Financial Health Analyzer

A FastAPI starter that retrieves annual XBRL facts from the SEC, stores source-backed
evidence in PostgreSQL, calculates financial ratios in Python, and runs a Google ADK
research → analysis → verification workflow with Gemini.

## Scope and limitations

- Accepts SEC-listed U.S. company ticker symbols and uses the latest available 10-K.
- SEC company facts are the structured source for the extracted statement metrics;
  each metric includes a link to its filing and a stable evidence ID. The latest 10-K
  primary document is also downloaded and indexed as overlapping report-text chunks.
- The RAG layer uses PostgreSQL full-text search to retrieve SEC-sourced report and
  financial-fact chunks.
- Ratios are calculated deterministically. Ratios needing missing or zero-denominator
  inputs are returned as `null`; raw financial values are in USD.
- This starter is not investment advice and does not normalize one-off items, compare
  multiple periods, cover non-U.S. filers, or render PDF reports.

## Run locally

1. Copy `.env.example` to `.env`, add a Gemini API key, and replace the SEC user-agent
   contact with a real email address.
2. Start the database and API:

   ```powershell
   docker compose up --build
   ```

3. Open `http://localhost:8000/docs` and submit:

   ```json
   { "ticker": "MSFT" }
   ```

`POST /analyze` returns the company, fiscal year, extracted metrics, ratios, citation
map, and the verified agent assessment. `GET /health` checks API availability.

## Deploy on GCP

Build and deploy the API container to Cloud Run, provision a Cloud SQL for PostgreSQL
instance, and connect it with the Cloud SQL connector. Set `DATABASE_URL`, `GEMINI_API_KEY`,
`GEMINI_MODEL`, and `SEC_USER_AGENT` as Cloud Run environment variables; store secrets in
Secret Manager and grant the service account access. The API initializes its evidence
table and search index at startup.

## Tests

```powershell
pytest
```
