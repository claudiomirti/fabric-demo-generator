"""
Produced by Claudio Mirti

Semantic model (star schema) definitions per industry.

Each model describes tables, columns, relationships, and key measures as they
would appear in a Power BI / Fabric semantic model.

Why every object carries a description
--------------------------------------
These definitions are not only rendered in the UI — they are also compiled into:

  * a **TMDL semantic model** (see `src/tmdl.py`), where each description becomes
    a `///` documentation line. Fabric **data agents** and Copilot read those
    descriptions to decide which table, column, or measure answers a question,
    so vague descriptions produce a poor agent.
  * a **Fabric Ontology** (see `src/ontology.py`), where tables become entity
    types and columns become entity properties.

Description-writing rules used throughout this file:
  - Say what the column *means in business terms*, not what its name already says.
  - Mention units, currency, and ranges where they exist.
  - For keys, name the table they join to.
  - For flags, state what True means.
"""
from typing import Any

# Column type vocabulary used across the app. These are normalised into TMDL
# `dataType:` values by src/tmdl.py and into ontology `valueType` values by
# src/ontology.py.
#   string | int64 | double | boolean | dateTime


def _col(dtype: str, description: str, **extra: Any) -> dict:
    """Build a column metadata entry."""
    return {"type": dtype, "description": description, **extra}


SEMANTIC_MODELS: dict[str, dict] = {
    # ─────────────────────────────────────────────────────────────────────────
    "Retail": {
        "description": "Retail sales star schema with customer, product, and store dimensions.",
        "business_context": (
            "Point-of-sale and e-commerce transaction data for a multi-channel retail chain. "
            "Each row of fact_sales is one line item sold, enriched with the store that sold it, "
            "the product sold, and the loyalty customer who bought it. Use this model to answer "
            "questions about revenue, basket size, discounting, channel mix, product category "
            "performance, store performance, and customer loyalty behaviour."
        ),
        "fact_table": "fact_sales",
        "dimensions": ["dim_customer", "dim_product", "dim_store"],
        "relationships": [
            {"from": "fact_sales.store_id",    "to": "dim_store.store_id",       "cardinality": "Many-to-One"},
            {"from": "fact_sales.product_id",  "to": "dim_product.product_id",   "cardinality": "Many-to-One"},
            {"from": "fact_sales.customer_id", "to": "dim_customer.customer_id", "cardinality": "Many-to-One"},
        ],
        "key_measures": [
            {"name": "Total Revenue", "dax": "SUM(fact_sales[total_amount])",
             "format_string": "\\$#,0.00",
             "description": "Gross sales value of all line items after discount, in USD. The primary top-line KPI."},
            {"name": "Total Quantity Sold", "dax": "SUM(fact_sales[quantity])",
             "format_string": "#,0",
             "description": "Total number of product units sold across all line items."},
            {"name": "Average Order Value", "dax": "AVERAGE(fact_sales[total_amount])",
             "format_string": "\\$#,0.00",
             "description": "Mean revenue per sales line item, in USD. Rises when customers buy more or higher-priced products."},
            {"name": "Discount Rate", "dax": "AVERAGE(fact_sales[discount_pct])",
             "format_string": "0.0%",
             "description": "Average discount applied across line items, expressed as a fraction of list price (0.15 = 15% off)."},
            {"name": "Unique Customers", "dax": "DISTINCTCOUNT(fact_sales[customer_id])",
             "format_string": "#,0",
             "description": "Count of distinct loyalty customers who made at least one purchase in the filtered period."},
        ],
        "tables": {
            "fact_sales": {
                "description": "Transaction fact table. One row per sales line item, at product-per-order grain.",
                "columns": {
                    "sale_id":      _col("string", "Unique identifier of the sales line item. Primary key of the fact table."),
                    "date":         _col("dateTime", "Calendar date on which the sale was completed. Use for all time-based trending."),
                    "store_id":     _col("string", "Store where the sale occurred. Joins to dim_store."),
                    "product_id":   _col("string", "Product that was sold. Joins to dim_product."),
                    "customer_id":  _col("string", "Loyalty customer who made the purchase. Joins to dim_customer."),
                    "quantity":     _col("int64", "Number of units of the product sold on this line item."),
                    "unit_price":   _col("double", "Price charged per unit at the time of sale, in USD, before discount."),
                    "discount_pct": _col("double", "Discount applied to this line item as a fraction of list price. 0.25 means 25% off."),
                    "channel":      _col("string", "Sales channel used for the purchase. One of In-Store, Online, or Mobile."),
                    "total_amount": _col("double", "Final revenue booked for this line item in USD, after discount. Additive across all dimensions."),
                },
            },
            "dim_store": {
                "description": "Store dimension. One row per physical or virtual retail location.",
                "columns": {
                    "store_id":   _col("string", "Unique store identifier. Primary key, referenced by fact_sales.store_id."),
                    "store_name": _col("string", "Trading name of the store, used as the display label in reports."),
                    "city":       _col("string", "City in which the store is located."),
                    "state":      _col("string", "Two-letter US state code of the store location, suitable for map visuals."),
                    "store_type": _col("string", "Store format. Flagship (largest, full range), Express (small urban), or Outlet (discount)."),
                    "open_date":  _col("dateTime", "Date the store opened for trading. Use to separate mature stores from new openings."),
                },
            },
            "dim_product": {
                "description": "Product dimension. One row per sellable SKU in the catalogue.",
                "columns": {
                    "product_id":   _col("string", "Unique product/SKU identifier. Primary key, referenced by fact_sales.product_id."),
                    "product_name": _col("string", "Commercial name of the product, used as the display label in reports."),
                    "category":     _col("string", "Merchandising category: Electronics, Apparel, Grocery, Home & Garden, or Sports."),
                    "brand":        _col("string", "Brand or vendor that manufactures the product."),
                    "unit_cost":    _col("double", "Cost of goods per unit in USD. Combine with unit_price to analyse margin."),
                    "unit_price":   _col("double", "Recommended list price per unit in USD, before any promotional discount."),
                },
            },
            "dim_customer": {
                "description": "Customer dimension. One row per enrolled loyalty programme member.",
                "columns": {
                    "customer_id":  _col("string", "Unique customer identifier. Primary key, referenced by fact_sales.customer_id."),
                    "first_name":   _col("string", "Customer given name. Synthetic data — not real personal information."),
                    "last_name":    _col("string", "Customer family name. Synthetic data — not real personal information."),
                    "email":        _col("string", "Customer contact email address. Synthetic data — not real personal information."),
                    "city":         _col("string", "City of the customer's registered home address."),
                    "loyalty_tier": _col("string", "Loyalty status, ascending: Bronze, Silver, Gold, Platinum. Higher tiers indicate higher lifetime spend."),
                },
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Manufacturing": {
        "description": "Manufacturing OEE schema with machine, product, and plant dimensions.",
        "business_context": (
            "Shop-floor production data for a multi-plant discrete manufacturer. Each row of "
            "fact_production is one completed work order on one machine, capturing throughput, "
            "quality, and downtime. Use this model to answer questions about Overall Equipment "
            "Effectiveness (OEE), defect and scrap rates, cycle-time performance against target, "
            "unplanned downtime, shift comparisons, and plant or machine benchmarking."
        ),
        "fact_table": "fact_production",
        "dimensions": ["dim_machine", "dim_product", "dim_plant"],
        "relationships": [
            {"from": "fact_production.machine_id", "to": "dim_machine.machine_id", "cardinality": "Many-to-One"},
            {"from": "fact_production.product_id", "to": "dim_product.product_id", "cardinality": "Many-to-One"},
            {"from": "fact_production.plant_id",   "to": "dim_plant.plant_id",     "cardinality": "Many-to-One"},
        ],
        "key_measures": [
            {"name": "Total Units Produced", "dax": "SUM(fact_production[units_produced])",
             "format_string": "#,0",
             "description": "Total good and bad units manufactured across all work orders. The core throughput measure."},
            {"name": "Defect Rate %", "dax": "DIVIDE(SUM(fact_production[defect_count]), SUM(fact_production[units_produced])) * 100",
             "format_string": "0.00",
             "description": "Percentage of produced units that failed quality inspection. Lower is better; a rise signals a process or tooling problem."},
            {"name": "Avg Cycle Time (sec)", "dax": "AVERAGE(fact_production[cycle_time_sec])",
             "format_string": "#,0.0",
             "description": "Mean seconds taken to produce one unit. Compare against dim_product[target_cycle_time_sec] to spot underperforming runs."},
            {"name": "Total Downtime (min)", "dax": "SUM(fact_production[downtime_minutes])",
             "format_string": "#,0",
             "description": "Total minutes machines were unavailable during the work orders in scope, planned and unplanned combined."},
            {"name": "OEE %", "dax": "1 - DIVIDE(SUM(fact_production[downtime_minutes]), 480 * COUNTROWS(fact_production))",
             "format_string": "0.0%",
             "description": "Simplified Overall Equipment Effectiveness based on availability, assuming a 480-minute (8-hour) shift per work order. Higher is better."},
        ],
        "tables": {
            "fact_production": {
                "description": "Production fact table. One row per completed work order on a single machine and shift.",
                "columns": {
                    "order_id":         _col("string", "Unique work order identifier. Primary key of the fact table."),
                    "date":             _col("dateTime", "Production date on which the work order ran. Use for all time-based trending."),
                    "machine_id":       _col("string", "Machine that executed the work order. Joins to dim_machine."),
                    "product_id":       _col("string", "Part that was manufactured. Joins to dim_product."),
                    "plant_id":         _col("string", "Plant where production took place. Joins to dim_plant."),
                    "units_produced":   _col("int64", "Total units output by this work order, including units later scrapped."),
                    "defect_count":     _col("int64", "Units from this work order that failed quality inspection. Always less than or equal to units_produced."),
                    "cycle_time_sec":   _col("int64", "Actual average seconds to produce one unit on this run. Compare to the product's target cycle time."),
                    "downtime_minutes": _col("int64", "Minutes the machine was stopped during this work order. Drives availability loss in OEE."),
                    "shift":            _col("string", "Working shift during which the order ran: Morning, Afternoon, or Night."),
                },
            },
            "dim_machine": {
                "description": "Machine dimension. One row per piece of production equipment on the shop floor.",
                "columns": {
                    "machine_id":       _col("string", "Unique machine identifier. Primary key, referenced by fact_production.machine_id."),
                    "machine_name":     _col("string", "Friendly name of the machine, used as the display label in reports."),
                    "plant_id":         _col("string", "Plant in which the machine is installed. Joins to dim_plant."),
                    "machine_type":     _col("string", "Equipment class: CNC, Press, Welder, Lathe, or Conveyor."),
                    "manufacture_year": _col("int64", "Year the machine was built. Older equipment typically shows more downtime."),
                    "status":           _col("string", "Current lifecycle state: Active (in production), Maintenance (temporarily out), or Retired."),
                },
            },
            "dim_product": {
                "description": "Manufactured part dimension. One row per part number that can be produced.",
                "columns": {
                    "product_id":            _col("string", "Unique part identifier. Primary key, referenced by fact_production.product_id."),
                    "part_name":             _col("string", "Descriptive name of the part, used as the display label in reports."),
                    "part_number":           _col("string", "Engineering part number used on drawings and in the bill of materials."),
                    "category":              _col("string", "Part family: Mechanical, Electrical, Assembly, or Structural."),
                    "target_cycle_time_sec": _col("int64", "Engineering standard seconds to produce one unit. The benchmark for actual cycle time."),
                },
            },
            "dim_plant": {
                "description": "Plant dimension. One row per manufacturing site.",
                "columns": {
                    "plant_id":               _col("string", "Unique plant identifier. Primary key, referenced by fact_production.plant_id."),
                    "plant_name":             _col("string", "Name of the manufacturing site, used as the display label in reports."),
                    "country":                _col("string", "Country in which the plant operates."),
                    "capacity_units_per_day": _col("int64", "Nameplate daily production capacity in units. Compare to actual output to measure utilisation."),
                },
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "FSI": {
        "description": "Financial services transaction schema with customer, account, and branch dimensions.",
        "business_context": (
            "Retail banking transaction data. Each row of fact_transactions is one money movement "
            "on one account. Accounts belong to customers and are serviced by a branch, so this is "
            "a snowflaked star schema: the fact joins to dim_account, and dim_account joins on to "
            "dim_customer and dim_branch. Use this model to answer questions about transaction "
            "volume and value, channel adoption, suspicious activity and AML flagging, customer "
            "segment behaviour, KYC compliance, and branch performance."
        ),
        "fact_table": "fact_transactions",
        "dimensions": ["dim_customer", "dim_account", "dim_branch"],
        "relationships": [
            {"from": "fact_transactions.account_id", "to": "dim_account.account_id",   "cardinality": "Many-to-One"},
            {"from": "dim_account.customer_id",      "to": "dim_customer.customer_id", "cardinality": "Many-to-One"},
            {"from": "dim_account.branch_id",        "to": "dim_branch.branch_id",     "cardinality": "Many-to-One"},
        ],
        "key_measures": [
            {"name": "Total Transaction Volume", "dax": "SUM(fact_transactions[amount])",
             "format_string": "\\$#,0.00",
             "description": "Total monetary value of all transactions in scope, in account currency. Note this sums deposits and withdrawals together."},
            {"name": "Transaction Count", "dax": "COUNTROWS(fact_transactions)",
             "format_string": "#,0",
             "description": "Number of individual transactions in the filtered period, regardless of value."},
            {"name": "Avg Transaction Value", "dax": "AVERAGE(fact_transactions[amount])",
             "format_string": "\\$#,0.00",
             "description": "Mean value of a single transaction. Useful for spotting unusual activity by channel or segment."},
            {"name": "Flagged Transaction Rate %", "dax": "DIVIDE(COUNTROWS(FILTER(fact_transactions, fact_transactions[is_flagged] = TRUE())), COUNTROWS(fact_transactions)) * 100",
             "format_string": "0.00",
             "description": "Percentage of transactions flagged by fraud or anti-money-laundering monitoring. The primary risk KPI."},
            {"name": "Unique Active Accounts", "dax": "DISTINCTCOUNT(fact_transactions[account_id])",
             "format_string": "#,0",
             "description": "Count of distinct accounts with at least one transaction in the filtered period."},
        ],
        "tables": {
            "fact_transactions": {
                "description": "Transaction fact table. One row per money movement posted to an account.",
                "columns": {
                    "transaction_id":   _col("string", "Unique transaction identifier. Primary key of the fact table."),
                    "date":             _col("dateTime", "Date the transaction was posted to the account. Use for all time-based trending."),
                    "account_id":       _col("string", "Account the transaction was posted to. Joins to dim_account, which in turn resolves the customer and branch."),
                    "transaction_type": _col("string", "Nature of the movement: Deposit, Withdrawal, Transfer, Payment, or Fee."),
                    "amount":           _col("double", "Transaction value in the account's currency. Always positive; direction is given by transaction_type."),
                    "channel":          _col("string", "Channel through which the transaction was initiated: Branch, ATM, Online, Mobile, or POS."),
                    "status":           _col("string", "Processing outcome: Completed, Pending, Failed, or Reversed."),
                    "is_flagged":       _col("boolean", "True when fraud or AML monitoring flagged this transaction for review. Approximately 5% of rows."),
                },
            },
            "dim_customer": {
                "description": "Customer dimension. One row per banking client. Reached from the fact table through dim_account.",
                "columns": {
                    "customer_id":   _col("string", "Unique customer identifier. Primary key, referenced by dim_account.customer_id."),
                    "first_name":    _col("string", "Customer given name. Synthetic data — not real personal information."),
                    "last_name":     _col("string", "Customer family name. Synthetic data — not real personal information."),
                    "date_of_birth": _col("dateTime", "Customer date of birth. Derive age bands from this for demographic analysis."),
                    "segment":       _col("string", "Commercial segment: Retail, Premier, Private, SME, or Corporate. Drives product eligibility and servicing model."),
                    "kyc_status":    _col("string", "Know Your Customer verification state: Verified, Pending, or Expired. Expired or Pending indicates a compliance gap."),
                    "credit_score":  _col("int64", "Credit bureau score between 300 and 850. Higher scores indicate lower default risk."),
                },
            },
            "dim_account": {
                "description": "Account dimension. One row per bank account. Bridges the transaction fact to both the customer and the servicing branch.",
                "columns": {
                    "account_id":   _col("string", "Unique account identifier. Primary key, referenced by fact_transactions.account_id."),
                    "customer_id":  _col("string", "Customer who owns the account. Joins to dim_customer."),
                    "account_type": _col("string", "Product type: Checking, Savings, Credit, Loan, or Investment."),
                    "branch_id":    _col("string", "Branch that services the account. Joins to dim_branch."),
                    "open_date":    _col("dateTime", "Date the account was opened. Use to compute account tenure and vintage cohorts."),
                    "currency":     _col("string", "ISO currency code the account is denominated in: USD, EUR, GBP, or SGD."),
                    "status":       _col("string", "Account state: Active, Dormant (no recent activity), or Closed."),
                },
            },
            "dim_branch": {
                "description": "Branch dimension. One row per physical banking branch.",
                "columns": {
                    "branch_id":   _col("string", "Unique branch identifier. Primary key, referenced by dim_account.branch_id."),
                    "branch_name": _col("string", "Name of the branch, used as the display label in reports."),
                    "region":      _col("string", "Sales region the branch reports into: North, South, East, West, or Central."),
                    "country":     _col("string", "Country in which the branch operates."),
                },
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Healthcare": {
        "description": "Healthcare encounter schema with patient, provider, and facility dimensions.",
        "business_context": (
            "Clinical encounter and billing data for a hospital network. Each row of fact_encounters "
            "is one patient visit, capturing the diagnosis, the length of stay, the amount charged, "
            "and whether the patient was readmitted within 30 days. Use this model to answer "
            "questions about patient volumes, case mix by diagnosis, length of stay, readmission "
            "quality measures, payer and insurance mix, provider specialty workload, and facility "
            "utilisation. All patient data is synthetic and contains no real PHI."
        ),
        "fact_table": "fact_encounters",
        "dimensions": ["dim_patient", "dim_provider", "dim_facility"],
        "relationships": [
            {"from": "fact_encounters.patient_id",  "to": "dim_patient.patient_id",   "cardinality": "Many-to-One"},
            {"from": "fact_encounters.provider_id", "to": "dim_provider.provider_id", "cardinality": "Many-to-One"},
            {"from": "fact_encounters.facility_id", "to": "dim_facility.facility_id", "cardinality": "Many-to-One"},
        ],
        "key_measures": [
            {"name": "Total Encounters", "dax": "COUNTROWS(fact_encounters)",
             "format_string": "#,0",
             "description": "Number of patient visits in the filtered period. The core volume measure."},
            {"name": "Total Charges", "dax": "SUM(fact_encounters[total_charge])",
             "format_string": "\\$#,0.00",
             "description": "Total amount billed across all encounters, in USD. This is gross charges, not collected revenue."},
            {"name": "Avg Length of Stay", "dax": "AVERAGE(fact_encounters[length_of_stay_days])",
             "format_string": "#,0.0",
             "description": "Mean days a patient remained admitted. Zero for outpatient, emergency, and telehealth visits."},
            {"name": "30-Day Readmission Rate", "dax": "DIVIDE(COUNTROWS(FILTER(fact_encounters, fact_encounters[readmission_30d] = TRUE())), COUNTROWS(fact_encounters)) * 100",
             "format_string": "0.00",
             "description": "Percentage of encounters followed by an unplanned readmission within 30 days. A regulated quality-of-care indicator; lower is better."},
            {"name": "Avg Charge per Encounter", "dax": "AVERAGE(fact_encounters[total_charge])",
             "format_string": "\\$#,0.00",
             "description": "Mean billed amount per visit, in USD. Varies strongly by encounter type and diagnosis."},
        ],
        "tables": {
            "fact_encounters": {
                "description": "Encounter fact table. One row per patient visit or admission.",
                "columns": {
                    "encounter_id":        _col("string", "Unique encounter identifier. Primary key of the fact table."),
                    "date":                _col("dateTime", "Date the encounter began. Use for all time-based trending."),
                    "patient_id":          _col("string", "Patient who was seen. Joins to dim_patient."),
                    "provider_id":         _col("string", "Clinician primarily responsible for the encounter. Joins to dim_provider."),
                    "facility_id":         _col("string", "Facility where care was delivered. Joins to dim_facility."),
                    "encounter_type":      _col("string", "Care setting: Inpatient (admitted), Outpatient, Emergency, or Telehealth."),
                    "primary_diagnosis":   _col("string", "ICD diagnosis code recorded as the principal reason for the encounter."),
                    "length_of_stay_days": _col("int64", "Number of days the patient stayed. Zero for non-admitted encounters."),
                    "total_charge":        _col("double", "Total amount billed for the encounter in USD, before payer adjustments."),
                    "readmission_30d":     _col("boolean", "True when the patient was readmitted within 30 days of this encounter. Approximately 10% of rows."),
                },
            },
            "dim_patient": {
                "description": "Patient dimension. One row per patient in the network. Fully synthetic — contains no real PHI.",
                "columns": {
                    "patient_id":     _col("string", "Unique patient identifier. Primary key, referenced by fact_encounters.patient_id."),
                    "first_name":     _col("string", "Patient given name. Synthetic data — not real personal information."),
                    "last_name":      _col("string", "Patient family name. Synthetic data — not real personal information."),
                    "date_of_birth":  _col("dateTime", "Patient date of birth. Derive age and age bands from this for cohort analysis."),
                    "gender":         _col("string", "Recorded gender: M, F, or Other."),
                    "blood_type":     _col("string", "ABO and Rhesus blood group, for example O+ or AB-."),
                    "insurance_type": _col("string", "Payer category: Private, Medicare, Medicaid, or Uninsured. Drives reimbursement and bad-debt risk."),
                },
            },
            "dim_provider": {
                "description": "Provider dimension. One row per treating clinician.",
                "columns": {
                    "provider_id":   _col("string", "Unique provider identifier. Primary key, referenced by fact_encounters.provider_id."),
                    "provider_name": _col("string", "Clinician name, used as the display label in reports."),
                    "specialty":     _col("string", "Clinical specialty, such as Cardiology, Orthopedics, Oncology, Neurology, General Practice, or Pediatrics."),
                    "facility_id":   _col("string", "Facility where the provider is primarily based. Joins to dim_facility."),
                    "npi":           _col("string", "National Provider Identifier, the 10-digit US regulatory identifier for the clinician."),
                },
            },
            "dim_facility": {
                "description": "Facility dimension. One row per hospital, clinic, or care site.",
                "columns": {
                    "facility_id":   _col("string", "Unique facility identifier. Primary key, referenced by fact_encounters.facility_id."),
                    "facility_name": _col("string", "Name of the care site, used as the display label in reports."),
                    "facility_type": _col("string", "Site category: Hospital, Clinic, Urgent Care, or Specialist Center."),
                    "state":         _col("string", "Two-letter US state code where the facility is located, suitable for map visuals."),
                    "bed_count":     _col("int64", "Number of licensed inpatient beds. Compare with encounter volume to assess utilisation."),
                },
            },
        },
    },

    # ─────────────────────────────────────────────────────────────────────────
    "Life Science": {
        "description": "Clinical trial observation schema with trial, compound, and site dimensions.",
        "business_context": (
            "Clinical trial operations and safety data for a pharmaceutical sponsor. Each row of "
            "fact_observations is one protocol-scheduled subject visit, capturing the primary "
            "efficacy endpoint reading, any adverse event, and whether the subject dropped out. "
            "Use this model to answer questions about enrolment and retention, dropout rates, "
            "adverse event frequency and severity, endpoint performance by compound, therapeutic "
            "area and trial phase comparisons, and investigator site performance."
        ),
        "fact_table": "fact_observations",
        "dimensions": ["dim_trial", "dim_compound", "dim_site"],
        "relationships": [
            {"from": "fact_observations.trial_id",    "to": "dim_trial.trial_id",       "cardinality": "Many-to-One"},
            {"from": "fact_observations.compound_id", "to": "dim_compound.compound_id", "cardinality": "Many-to-One"},
            {"from": "fact_observations.site_id",     "to": "dim_site.site_id",         "cardinality": "Many-to-One"},
        ],
        "key_measures": [
            {"name": "Total Observations", "dax": "COUNTROWS(fact_observations)",
             "format_string": "#,0",
             "description": "Number of recorded subject visits in the filtered period. The core trial activity measure."},
            {"name": "Adverse Event Rate %", "dax": "DIVIDE(COUNTROWS(FILTER(fact_observations, fact_observations[adverse_event] <> BLANK())), COUNTROWS(fact_observations)) * 100",
             "format_string": "0.00",
             "description": "Percentage of visits at which any adverse event was reported. The headline safety signal; investigate rises by compound."},
            {"name": "Dropout Rate %", "dax": "DIVIDE(COUNTROWS(FILTER(fact_observations, fact_observations[dropout] = TRUE())), COUNTROWS(fact_observations)) * 100",
             "format_string": "0.00",
             "description": "Percentage of visits at which the subject withdrew from the study. High dropout threatens statistical power."},
            {"name": "Avg Primary Endpoint", "dax": "AVERAGE(fact_observations[primary_endpoint_value])",
             "format_string": "#,0.00",
             "description": "Mean primary efficacy endpoint reading on a 0-100 scale. The main efficacy signal; compare across compounds and visit types."},
            {"name": "Enrolled Subjects", "dax": "DISTINCTCOUNT(fact_observations[subject_id])",
             "format_string": "#,0",
             "description": "Count of distinct trial subjects with at least one recorded visit in the filtered period."},
        ],
        "tables": {
            "fact_observations": {
                "description": "Observation fact table. One row per protocol-scheduled subject visit.",
                "columns": {
                    "observation_id":         _col("string", "Unique observation identifier. Primary key of the fact table."),
                    "date":                   _col("dateTime", "Date the subject visit took place. Use for all time-based trending."),
                    "trial_id":               _col("string", "Clinical trial the observation belongs to. Joins to dim_trial."),
                    "compound_id":            _col("string", "Investigational compound administered. Joins to dim_compound."),
                    "site_id":                _col("string", "Investigator site where the visit occurred. Joins to dim_site."),
                    "subject_id":             _col("string", "Pseudonymised trial participant identifier. Count distinct values to get enrolment."),
                    "visit_type":             _col("string", "Protocol visit milestone: Screening, Baseline, Week 4, Week 12, Week 24, or End of Study."),
                    "primary_endpoint_value": _col("double", "Primary efficacy endpoint reading on a 0-100 scale. Higher values indicate a better clinical response."),
                    "adverse_event":          _col("string", "Adverse event reported at this visit, such as Nausea, Fatigue, Headache, or Dizziness. Blank when no event occurred."),
                    "adverse_event_severity": _col("string", "Clinical severity grading of the adverse event: Mild, Moderate, or Severe. Blank when no event occurred."),
                    "dropout":                _col("boolean", "True when the subject withdrew from the study at this visit. Approximately 5% of rows."),
                },
            },
            "dim_trial": {
                "description": "Trial dimension. One row per clinical study in the portfolio.",
                "columns": {
                    "trial_id":         _col("string", "Unique trial identifier. Primary key, referenced by fact_observations.trial_id."),
                    "trial_name":       _col("string", "Protocol name of the study, used as the display label in reports."),
                    "phase":            _col("string", "Development phase: Phase I (safety), Phase II (efficacy), Phase III (confirmatory), or Phase IV (post-marketing)."),
                    "therapeutic_area": _col("string", "Disease area under study, such as Oncology, Neurology, Cardiology, Immunology, or Rare Disease."),
                    "start_date":       _col("dateTime", "Date the trial began enrolling. Use to compute trial duration and vintage."),
                    "status":           _col("string", "Current trial state: Recruiting, Active, Completed, or Terminated."),
                },
            },
            "dim_compound": {
                "description": "Compound dimension. One row per investigational molecule or therapy.",
                "columns": {
                    "compound_id":       _col("string", "Unique compound identifier. Primary key, referenced by fact_observations.compound_id."),
                    "compound_name":     _col("string", "Development code name of the compound, used as the display label in reports."),
                    "mechanism":         _col("string", "Pharmacological mechanism of action: Inhibitor, Agonist, Antagonist, Monoclonal Antibody, or Gene Therapy."),
                    "modality":          _col("string", "Therapeutic modality: Small Molecule, Biologic, Cell Therapy, or RNA."),
                    "development_stage": _col("string", "Pipeline stage: Preclinical, Clinical, Approved, or Withdrawn."),
                },
            },
            "dim_site": {
                "description": "Site dimension. One row per investigator site running trial visits.",
                "columns": {
                    "site_id":                _col("string", "Unique site identifier. Primary key, referenced by fact_observations.site_id."),
                    "site_name":              _col("string", "Name of the research institute or hospital, used as the display label in reports."),
                    "country":                _col("string", "Country in which the site operates. Use for geographic enrolment analysis."),
                    "principal_investigator": _col("string", "Lead clinician accountable for the site's conduct of the protocol."),
                    "capacity":               _col("int64", "Maximum number of subjects the site can enrol concurrently. Compare with actual enrolment to find under-used sites."),
                },
            },
        },
    },
}


def get_model(industry: str) -> dict:
    if industry not in SEMANTIC_MODELS:
        raise ValueError(f"No model for industry: {industry}")
    return SEMANTIC_MODELS[industry]


def get_columns(industry: str, table: str) -> list[str]:
    """Return the ordered column names for a table."""
    return list(get_model(industry)["tables"][table]["columns"].keys())


def model_name(industry: str) -> str:
    """Canonical semantic model item name for an industry."""
    return f"{industry.replace(' ', '_')}_Demo_Model"


def ontology_name(industry: str) -> str:
    """Canonical ontology item name. Fabric requires [A-Za-z0-9_] only."""
    return f"{industry.replace(' ', '_')}_Demo_Ontology"


def lakehouse_name(industry: str) -> str:
    """Canonical lakehouse item name."""
    return f"{industry.replace(' ', '_')}_Demo_Lakehouse"


def render_schema_text(industry: str) -> str:
    """Render a human-readable schema overview for the Gradio UI."""
    model = get_model(industry)
    lines = [
        f"## 📊 Semantic Model: {industry}",
        f"_{model['description']}_",
        "",
        f"> {model['business_context']}",
        "",
        f"**Fact Table:** `{model['fact_table']}`",
        "",
        "### 📁 Tables & Columns",
    ]
    for table, meta in model["tables"].items():
        icon = "🔶" if table == model["fact_table"] else "🔷"
        lines.append(f"{icon} **{table}** — _{meta['description']}_")
        lines.append("  " + " · ".join(f"`{c}`" for c in meta["columns"]))

    lines += ["", "### 🔗 Relationships"]
    for rel in model["relationships"]:
        lines.append(f"- `{rel['from']}` → `{rel['to']}` _{rel['cardinality']}_")

    lines += ["", "### 📐 Key Measures (DAX)"]
    for m in model["key_measures"]:
        lines.append(f"- **{m['name']}**: `{m['dax']}`")
        lines.append(f"  <br/>_{m['description']}_")

    return "\n".join(lines)
