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
5. **Click "Start Provisioning"** — the app will:
   - Create a Lakehouse named `{Industry}_Demo_Lakehouse`
   - Upload all synthetic CSVs to `Files/{Industry}/`
   - Show a step-by-step log

### After Provisioning

1. Open the Lakehouse in **Fabric Portal**
2. In the Files section, select each CSV → **Load to Tables** (creates Delta tables)
3. Click **New semantic model** and use the schema preview to set up relationships and measures

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
│   ├── semantic_model.py   # Star schema definitions + DAX measures
│   └── orchestrator.py     # Provisioning workflow (generator/streaming)
```

---

## Notes

- The app does **not** store credentials or data between sessions.
- If a Lakehouse with the same name already exists, it will be reused.
- Default row count is 1,000 per fact table (configurable up to 10,000 in the UI).
