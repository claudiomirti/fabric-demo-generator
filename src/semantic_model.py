"""
Produced by Claudio Mirti

Semantic model (star schema) definitions per industry.
Each model describes tables, columns, relationships, and key measures
as they would appear in a Power BI / Fabric semantic model.
"""

SEMANTIC_MODELS: dict[str, dict] = {
    "Retail": {
        "description": "Retail sales star schema with customer, product, and store dimensions.",
        "fact_table": "fact_sales",
        "dimensions": ["dim_customer", "dim_product", "dim_store"],
        "relationships": [
            {"from": "fact_sales.store_id",    "to": "dim_store.store_id",       "cardinality": "Many-to-One"},
            {"from": "fact_sales.product_id",  "to": "dim_product.product_id",   "cardinality": "Many-to-One"},
            {"from": "fact_sales.customer_id", "to": "dim_customer.customer_id", "cardinality": "Many-to-One"},
        ],
        "key_measures": [
            {"name": "Total Revenue",      "dax": "SUM(fact_sales[total_amount])"},
            {"name": "Total Quantity Sold","dax": "SUM(fact_sales[quantity])"},
            {"name": "Average Order Value","dax": "AVERAGE(fact_sales[total_amount])"},
            {"name": "Discount Rate",      "dax": "AVERAGE(fact_sales[discount_pct])"},
            {"name": "Unique Customers",   "dax": "DISTINCTCOUNT(fact_sales[customer_id])"},
        ],
        "tables": {
            "fact_sales": ["sale_id", "date", "store_id", "product_id", "customer_id",
                           "quantity", "unit_price", "discount_pct", "channel", "total_amount"],
            "dim_store": ["store_id", "store_name", "city", "state", "store_type", "open_date"],
            "dim_product": ["product_id", "product_name", "category", "brand", "unit_cost", "unit_price"],
            "dim_customer": ["customer_id", "first_name", "last_name", "email", "city", "loyalty_tier"],
        },
    },

    "Manufacturing": {
        "description": "Manufacturing OEE schema with machine, product, and plant dimensions.",
        "fact_table": "fact_production",
        "dimensions": ["dim_machine", "dim_product", "dim_plant"],
        "relationships": [
            {"from": "fact_production.machine_id", "to": "dim_machine.machine_id", "cardinality": "Many-to-One"},
            {"from": "fact_production.product_id", "to": "dim_product.product_id", "cardinality": "Many-to-One"},
            {"from": "fact_production.plant_id",   "to": "dim_plant.plant_id",     "cardinality": "Many-to-One"},
        ],
        "key_measures": [
            {"name": "Total Units Produced",  "dax": "SUM(fact_production[units_produced])"},
            {"name": "Defect Rate %",         "dax": "DIVIDE(SUM(fact_production[defect_count]), SUM(fact_production[units_produced])) * 100"},
            {"name": "Avg Cycle Time (sec)",  "dax": "AVERAGE(fact_production[cycle_time_sec])"},
            {"name": "Total Downtime (min)",  "dax": "SUM(fact_production[downtime_minutes])"},
            {"name": "OEE %",                 "dax": "1 - DIVIDE(SUM(fact_production[downtime_minutes]), 480 * COUNTROWS(fact_production))"},
        ],
        "tables": {
            "fact_production": ["order_id", "date", "machine_id", "product_id", "plant_id",
                                "units_produced", "defect_count", "cycle_time_sec", "downtime_minutes", "shift"],
            "dim_machine": ["machine_id", "machine_name", "plant_id", "machine_type", "manufacture_year", "status"],
            "dim_product": ["product_id", "part_name", "part_number", "category", "target_cycle_time_sec"],
            "dim_plant": ["plant_id", "plant_name", "country", "capacity_units_per_day"],
        },
    },

    "FSI": {
        "description": "Financial services transaction schema with customer, account, and branch dimensions.",
        "fact_table": "fact_transactions",
        "dimensions": ["dim_customer", "dim_account", "dim_branch"],
        "relationships": [
            {"from": "fact_transactions.account_id", "to": "dim_account.account_id",   "cardinality": "Many-to-One"},
            {"from": "dim_account.customer_id",      "to": "dim_customer.customer_id", "cardinality": "Many-to-One"},
            {"from": "dim_account.branch_id",        "to": "dim_branch.branch_id",     "cardinality": "Many-to-One"},
        ],
        "key_measures": [
            {"name": "Total Transaction Volume",   "dax": "SUM(fact_transactions[amount])"},
            {"name": "Transaction Count",          "dax": "COUNTROWS(fact_transactions)"},
            {"name": "Avg Transaction Value",      "dax": "AVERAGE(fact_transactions[amount])"},
            {"name": "Flagged Transaction Rate %", "dax": "DIVIDE(COUNTROWS(FILTER(fact_transactions, fact_transactions[is_flagged] = TRUE())), COUNTROWS(fact_transactions)) * 100"},
            {"name": "Unique Active Accounts",     "dax": "DISTINCTCOUNT(fact_transactions[account_id])"},
        ],
        "tables": {
            "fact_transactions": ["transaction_id", "date", "account_id", "transaction_type",
                                  "amount", "channel", "status", "is_flagged"],
            "dim_customer": ["customer_id", "first_name", "last_name", "date_of_birth",
                             "segment", "kyc_status", "credit_score"],
            "dim_account": ["account_id", "customer_id", "account_type", "branch_id",
                            "open_date", "currency", "status"],
            "dim_branch": ["branch_id", "branch_name", "region", "country"],
        },
    },

    "Healthcare": {
        "description": "Healthcare encounter schema with patient, provider, and facility dimensions.",
        "fact_table": "fact_encounters",
        "dimensions": ["dim_patient", "dim_provider", "dim_facility"],
        "relationships": [
            {"from": "fact_encounters.patient_id",  "to": "dim_patient.patient_id",   "cardinality": "Many-to-One"},
            {"from": "fact_encounters.provider_id", "to": "dim_provider.provider_id", "cardinality": "Many-to-One"},
            {"from": "fact_encounters.facility_id", "to": "dim_facility.facility_id", "cardinality": "Many-to-One"},
        ],
        "key_measures": [
            {"name": "Total Encounters",       "dax": "COUNTROWS(fact_encounters)"},
            {"name": "Total Charges",          "dax": "SUM(fact_encounters[total_charge])"},
            {"name": "Avg Length of Stay",     "dax": "AVERAGE(fact_encounters[length_of_stay_days])"},
            {"name": "30-Day Readmission Rate","dax": "DIVIDE(COUNTROWS(FILTER(fact_encounters, fact_encounters[readmission_30d] = TRUE())), COUNTROWS(fact_encounters)) * 100"},
            {"name": "Avg Charge per Encounter","dax": "AVERAGE(fact_encounters[total_charge])"},
        ],
        "tables": {
            "fact_encounters": ["encounter_id", "date", "patient_id", "provider_id", "facility_id",
                                "encounter_type", "primary_diagnosis", "length_of_stay_days",
                                "total_charge", "readmission_30d"],
            "dim_patient": ["patient_id", "first_name", "last_name", "date_of_birth",
                            "gender", "blood_type", "insurance_type"],
            "dim_provider": ["provider_id", "provider_name", "specialty", "facility_id", "npi"],
            "dim_facility": ["facility_id", "facility_name", "facility_type", "state", "bed_count"],
        },
    },

    "Life Science": {
        "description": "Clinical trial observation schema with trial, compound, and site dimensions.",
        "fact_table": "fact_observations",
        "dimensions": ["dim_trial", "dim_compound", "dim_site"],
        "relationships": [
            {"from": "fact_observations.trial_id",    "to": "dim_trial.trial_id",       "cardinality": "Many-to-One"},
            {"from": "fact_observations.compound_id", "to": "dim_compound.compound_id", "cardinality": "Many-to-One"},
            {"from": "fact_observations.site_id",     "to": "dim_site.site_id",         "cardinality": "Many-to-One"},
        ],
        "key_measures": [
            {"name": "Total Observations",     "dax": "COUNTROWS(fact_observations)"},
            {"name": "Adverse Event Rate %",   "dax": "DIVIDE(COUNTROWS(FILTER(fact_observations, fact_observations[adverse_event] <> BLANK())), COUNTROWS(fact_observations)) * 100"},
            {"name": "Dropout Rate %",         "dax": "DIVIDE(COUNTROWS(FILTER(fact_observations, fact_observations[dropout] = TRUE())), COUNTROWS(fact_observations)) * 100"},
            {"name": "Avg Primary Endpoint",   "dax": "AVERAGE(fact_observations[primary_endpoint_value])"},
            {"name": "Enrolled Subjects",      "dax": "DISTINCTCOUNT(fact_observations[subject_id])"},
        ],
        "tables": {
            "fact_observations": ["observation_id", "date", "trial_id", "compound_id", "site_id",
                                  "subject_id", "visit_type", "primary_endpoint_value",
                                  "adverse_event", "adverse_event_severity", "dropout"],
            "dim_trial": ["trial_id", "trial_name", "phase", "therapeutic_area", "start_date", "status"],
            "dim_compound": ["compound_id", "compound_name", "mechanism", "modality", "development_stage"],
            "dim_site": ["site_id", "site_name", "country", "principal_investigator", "capacity"],
        },
    },
}


def get_model(industry: str) -> dict:
    if industry not in SEMANTIC_MODELS:
        raise ValueError(f"No model for industry: {industry}")
    return SEMANTIC_MODELS[industry]


def render_schema_text(industry: str) -> str:
    """Render a human-readable schema overview for the Gradio UI."""
    model = get_model(industry)
    lines = [
        f"## 📊 Semantic Model: {industry}",
        f"_{model['description']}_",
        "",
        f"**Fact Table:** `{model['fact_table']}`",
        "",
        "### 📁 Tables & Columns",
    ]
    for table, cols in model["tables"].items():
        icon = "🔶" if table == model["fact_table"] else "🔷"
        lines.append(f"{icon} **{table}**")
        lines.append("  " + " · ".join(f"`{c}`" for c in cols))

    lines += ["", "### 🔗 Relationships"]
    for rel in model["relationships"]:
        lines.append(f"- `{rel['from']}` → `{rel['to']}` _{rel['cardinality']}_")

    lines += ["", "### 📐 Key Measures (DAX)"]
    for m in model["key_measures"]:
        lines.append(f"- **{m['name']}**: `{m['dax']}`")

    return "\n".join(lines)
