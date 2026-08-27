# 🏭 Microsoft Fabric — Data Demo Generator

A Gradio-powered web app that generates synthetic industry datasets and provisions them directly into a **Microsoft Fabric** workspace (creates a Lakehouse + uploads CSV files).

<img width="2560" height="1765" alt="image" src="https://github.com/user-attachments/assets/9c13ec81-034c-464f-b9d5-4bf0e877cb65" />


## Supported Industries

| Industry | Fact Table | Key Dimensions |
|---|---|---|
| 🛒 Retail | `fact_sales` | dim_store, dim_product, dim_customer |
| 🏭 Manufacturing | `fact_production` | dim_machine, dim_product, dim_plant |
| 🏦 FSI | `fact_transactions` | dim_customer, dim_account, dim_branch |
| 🏥 Healthcare | `fact_encounters` | dim_patient, dim_provider, dim_facility |
| 🔬 Life Science | `fact_observations` | dim_trial, dim_compound, dim_site |

---

## Prerequisites

- **Python 3.10+**
- **Azure CLI** installed and logged in, **or** a browser available for interactive login
  ```bash
  az login
  ```
- A **Microsoft Fabric** workspace (you need at least Contributor role)
- An active **Microsoft Fabric capacity** (trial or paid)

---

## Setup

```bash
cd fabric-demo-generator
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Run

```bash
python app.py
```

The app opens automatically at **http://localhost:7860**

---

## Usage

1. **Authenticate** — click "Login / Verify Auth". Uses Azure CLI first, then falls back to browser.
2. **Select your industry** and configure the number of rows to generate.
3. **Enter your Workspace ID** — found in the Fabric portal URL:  
   `https://app.fabric.microsoft.com/groups/{workspace-id}/...`
4. **Preview the semantic model** schema (star schema tables, relationships, DAX measures).
5. **Choose what to create** — see [Output modes](#output-modes) below.
6. **Click "Start Provisioning"** — the app streams a step-by-step log as it works.

---

## Output modes

Step 4 decides how far provisioning goes.

### 📄 CSV files only

- Creates a Lakehouse named `{Industry}_Demo_Lakehouse`
- Uploads all synthetic CSVs to `Files/{Industry}/`

Quickest option. To finish the model by hand afterwards: open the Lakehouse in
the Fabric portal, select each CSV → **Load to Tables**, then click **New
semantic model** and use the schema preview to set up relationships and measures.

### 🚀 Full provisioning

Everything above, and then:

- **Delta tables** — each uploaded CSV is converted into a managed Delta table
  via the Lakehouse *Load table* API. The lakehouse layout is detected
  automatically, so both classic (`Tables/`) and schema-enabled (`Tables/dbo/`)
  lakehouses work.
- **Semantic model** — a **Direct Lake on OneLake** model named
  `{Industry}_Demo_Model`, containing the star-schema relationships and the DAX
  measures shown in the preview. Every table, column, and measure carries a
  business description, which is what a **Fabric data agent** reads to map a
  natural-language question onto the right model objects. Column data types are
  read back from the Delta tables rather than guessed, so the model matches
  storage exactly.
- **Large storage format** — the model is switched to large semantic model
  storage format, which Direct Lake requires. The portal does this
  automatically; the REST API does not.
- **Framing** — the model is refreshed once so it picks up the Delta metadata.
  Until this happens a Direct Lake model has no snapshot and returns no data.
- **Ontology** — a Fabric **Ontology** item named `{Industry}_Demo_Ontology`
  that describes the same domain as entity types (Customer, Product, Store,
  Sale…), their properties, and the relationships between them, bound to the
  Delta tables.

Takes a few minutes longer. Semantic model and ontology creation are non-fatal:
if either fails, the log says so and the Lakehouse with its Delta tables is
still left in place.

> **Note:** Ontologies are a Fabric preview feature and require a supported
> Fabric capacity plus Contributor rights on the workspace.

> **Note:** Setting the storage format and framing use the Power BI REST API
> (`api.powerbi.com`), which is a different token audience from the Fabric API.
> You may see an extra consent prompt the first time.

Re-running for the same industry reuses the Lakehouse and replaces the semantic
model and ontology, so it is safe to run more than once.

### After full provisioning

The model is ready to query as soon as provisioning finishes.

1. In Fabric, create a **data agent** and add `{Industry}_Demo_Model` as a data source.
2. Ask questions in plain language — see [`DEMO_QUESTIONS.md`](./DEMO_QUESTIONS.md) for ideas.

---

## Project Structure

```
fabric-demo-generator/
├── app.py                  # Gradio UI + entry point
├── requirements.txt
├── src/
│   ├── auth.py             # Azure authentication (CLI / browser)
│   ├── fabric_client.py    # Fabric REST API + OneLake upload
│   ├── data_generator.py   # Synthetic data generators per industry
│   ├── semantic_model.py   # Star schema definitions, descriptions, DAX measures
│   ├── tmdl.py             # Builds the Direct Lake semantic model (TMSL/model.bim)
│   ├── ontology.py         # Builds the Fabric Ontology definition
│   └── orchestrator.py     # Provisioning workflow (generator/streaming)
```

---

## Notes

- The app does **not** store credentials or data between sessions.
- If a Lakehouse with the same name already exists, it will be reused.
- Default row count is 1,000 per fact table (configurable up to 10,000 in the UI).
- Full provisioning replaces an existing semantic model or ontology of the same
  name rather than leaving a stale definition behind.
