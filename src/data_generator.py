"""
Produced by Claudio Mirti

Synthetic data generators for each industry.
Each generator returns a dict of {table_name: pd.DataFrame}.
"""
import random
from datetime import datetime, timedelta

import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)


def _date_range(days_back: int = 365, n: int = 1000) -> list:
    end = datetime.now()
    return [
        (end - timedelta(days=random.randint(0, days_back))).strftime("%Y-%m-%d")
        for _ in range(n)
    ]


# ─── RETAIL ────────────────────────────────────────────────────────────────────

def generate_retail(n: int = 1000) -> dict[str, pd.DataFrame]:
    store_ids = [f"STORE-{i:03d}" for i in range(1, 21)]
    product_ids = [f"PROD-{i:04d}" for i in range(1, 101)]
    customer_ids = [f"CUST-{i:05d}" for i in range(1, 501)]
    categories = ["Electronics", "Apparel", "Grocery", "Home & Garden", "Sports"]
    channels = ["In-Store", "Online", "Mobile"]

    dim_store = pd.DataFrame({
        "store_id": store_ids,
        "store_name": [fake.company() for _ in store_ids],
        "city": [fake.city() for _ in store_ids],
        "state": [fake.state_abbr() for _ in store_ids],
        "store_type": [random.choice(["Flagship", "Express", "Outlet"]) for _ in store_ids],
        "open_date": [fake.date_between("-10y", "-1y").strftime("%Y-%m-%d") for _ in store_ids],
    })

    dim_product = pd.DataFrame({
        "product_id": product_ids,
        "product_name": [fake.catch_phrase() for _ in product_ids],
        "category": [random.choice(categories) for _ in product_ids],
        "brand": [fake.company() for _ in product_ids],
        "unit_cost": [round(random.uniform(2, 200), 2) for _ in product_ids],
        "unit_price": [round(random.uniform(5, 500), 2) for _ in product_ids],
    })

    dim_customer = pd.DataFrame({
        "customer_id": customer_ids,
        "first_name": [fake.first_name() for _ in customer_ids],
        "last_name": [fake.last_name() for _ in customer_ids],
        "email": [fake.email() for _ in customer_ids],
        "city": [fake.city() for _ in customer_ids],
        "loyalty_tier": [random.choice(["Bronze", "Silver", "Gold", "Platinum"]) for _ in customer_ids],
    })

    fact_sales = pd.DataFrame({
        "sale_id": [f"SALE-{i:06d}" for i in range(n)],
        "date": _date_range(365, n),
        "store_id": [random.choice(store_ids) for _ in range(n)],
        "product_id": [random.choice(product_ids) for _ in range(n)],
        "customer_id": [random.choice(customer_ids) for _ in range(n)],
        "quantity": [random.randint(1, 10) for _ in range(n)],
        "unit_price": [round(random.uniform(5, 500), 2) for _ in range(n)],
        "discount_pct": [round(random.uniform(0, 0.3), 2) for _ in range(n)],
        "channel": [random.choice(channels) for _ in range(n)],
        "total_amount": [round(random.uniform(10, 2000), 2) for _ in range(n)],
    })

    return {
        "dim_store": dim_store,
        "dim_product": dim_product,
        "dim_customer": dim_customer,
        "fact_sales": fact_sales,
    }


# ─── MANUFACTURING ──────────────────────────────────────────────────────────────

def generate_manufacturing(n: int = 1000) -> dict[str, pd.DataFrame]:
    machine_ids = [f"MCH-{i:03d}" for i in range(1, 31)]
    product_ids = [f"PART-{i:04d}" for i in range(1, 51)]
    plant_ids = [f"PLANT-{i:02d}" for i in range(1, 6)]

    dim_machine = pd.DataFrame({
        "machine_id": machine_ids,
        "machine_name": [f"Machine {fake.word().capitalize()}" for _ in machine_ids],
        "plant_id": [random.choice(plant_ids) for _ in machine_ids],
        "machine_type": [random.choice(["CNC", "Press", "Welder", "Lathe", "Conveyor"]) for _ in machine_ids],
        "manufacture_year": [random.randint(2005, 2022) for _ in machine_ids],
        "status": [random.choice(["Active", "Maintenance", "Retired"]) for _ in machine_ids],
    })

    dim_product = pd.DataFrame({
        "product_id": product_ids,
        "part_name": [fake.catch_phrase() for _ in product_ids],
        "part_number": [f"PN-{random.randint(10000,99999)}" for _ in product_ids],
        "category": [random.choice(["Mechanical", "Electrical", "Assembly", "Structural"]) for _ in product_ids],
        "target_cycle_time_sec": [random.randint(30, 600) for _ in product_ids],
    })

    dim_plant = pd.DataFrame({
        "plant_id": plant_ids,
        "plant_name": [f"{fake.city()} Plant" for _ in plant_ids],
        "country": [fake.country() for _ in plant_ids],
        "capacity_units_per_day": [random.randint(500, 5000) for _ in plant_ids],
    })

    fact_production = pd.DataFrame({
        "order_id": [f"WO-{i:06d}" for i in range(n)],
        "date": _date_range(365, n),
        "machine_id": [random.choice(machine_ids) for _ in range(n)],
        "product_id": [random.choice(product_ids) for _ in range(n)],
        "plant_id": [random.choice(plant_ids) for _ in range(n)],
        "units_produced": [random.randint(50, 1000) for _ in range(n)],
        "defect_count": [random.randint(0, 20) for _ in range(n)],
        "cycle_time_sec": [random.randint(30, 700) for _ in range(n)],
        "downtime_minutes": [random.randint(0, 120) for _ in range(n)],
        "shift": [random.choice(["Morning", "Afternoon", "Night"]) for _ in range(n)],
    })

    return {
        "dim_machine": dim_machine,
        "dim_product": dim_product,
        "dim_plant": dim_plant,
        "fact_production": fact_production,
    }


# ─── FSI (Financial Services) ──────────────────────────────────────────────────

def generate_fsi(n: int = 1000) -> dict[str, pd.DataFrame]:
    customer_ids = [f"CLI-{i:05d}" for i in range(1, 501)]
    account_ids = [f"ACC-{i:06d}" for i in range(1, 1001)]
    branch_ids = [f"BRN-{i:03d}" for i in range(1, 21)]

    dim_customer = pd.DataFrame({
        "customer_id": customer_ids,
        "first_name": [fake.first_name() for _ in customer_ids],
        "last_name": [fake.last_name() for _ in customer_ids],
        "date_of_birth": [fake.date_of_birth(minimum_age=18, maximum_age=80).strftime("%Y-%m-%d") for _ in customer_ids],
        "segment": [random.choice(["Retail", "Premier", "Private", "SME", "Corporate"]) for _ in customer_ids],
        "kyc_status": [random.choice(["Verified", "Pending", "Expired"]) for _ in customer_ids],
        "credit_score": [random.randint(300, 850) for _ in customer_ids],
    })

    dim_account = pd.DataFrame({
        "account_id": account_ids,
        "customer_id": [random.choice(customer_ids) for _ in account_ids],
        "account_type": [random.choice(["Checking", "Savings", "Credit", "Loan", "Investment"]) for _ in account_ids],
        "branch_id": [random.choice(branch_ids) for _ in account_ids],
        "open_date": [fake.date_between("-5y", "-1m").strftime("%Y-%m-%d") for _ in account_ids],
        "currency": [random.choice(["USD", "EUR", "GBP", "SGD"]) for _ in account_ids],
        "status": [random.choice(["Active", "Dormant", "Closed"]) for _ in account_ids],
    })

    dim_branch = pd.DataFrame({
        "branch_id": branch_ids,
        "branch_name": [f"{fake.city()} Branch" for _ in branch_ids],
        "region": [random.choice(["North", "South", "East", "West", "Central"]) for _ in branch_ids],
        "country": ["United States"] * len(branch_ids),
    })

    fact_transactions = pd.DataFrame({
        "transaction_id": [f"TXN-{i:07d}" for i in range(n)],
        "date": _date_range(365, n),
        "account_id": [random.choice(account_ids) for _ in range(n)],
        "transaction_type": [random.choice(["Deposit", "Withdrawal", "Transfer", "Payment", "Fee"]) for _ in range(n)],
        "amount": [round(random.uniform(1, 50000), 2) for _ in range(n)],
        "channel": [random.choice(["Branch", "ATM", "Online", "Mobile", "POS"]) for _ in range(n)],
        "status": [random.choice(["Completed", "Pending", "Failed", "Reversed"]) for _ in range(n)],
        "is_flagged": [random.choice([False] * 19 + [True]) for _ in range(n)],
    })

    return {
        "dim_customer": dim_customer,
        "dim_account": dim_account,
        "dim_branch": dim_branch,
        "fact_transactions": fact_transactions,
    }


# ─── HEALTHCARE ────────────────────────────────────────────────────────────────

def generate_healthcare(n: int = 1000) -> dict[str, pd.DataFrame]:
    patient_ids = [f"PAT-{i:05d}" for i in range(1, 501)]
    provider_ids = [f"PRV-{i:04d}" for i in range(1, 101)]
    facility_ids = [f"FAC-{i:03d}" for i in range(1, 21)]
    diagnosis_codes = [f"ICD-{random.randint(100,999)}" for _ in range(50)]

    dim_patient = pd.DataFrame({
        "patient_id": patient_ids,
        "first_name": [fake.first_name() for _ in patient_ids],
        "last_name": [fake.last_name() for _ in patient_ids],
        "date_of_birth": [fake.date_of_birth(minimum_age=0, maximum_age=95).strftime("%Y-%m-%d") for _ in patient_ids],
        "gender": [random.choice(["M", "F", "Other"]) for _ in patient_ids],
        "blood_type": [random.choice(["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]) for _ in patient_ids],
        "insurance_type": [random.choice(["Private", "Medicare", "Medicaid", "Uninsured"]) for _ in patient_ids],
    })

    dim_provider = pd.DataFrame({
        "provider_id": provider_ids,
        "provider_name": [f"Dr. {fake.last_name()}" for _ in provider_ids],
        "specialty": [random.choice(["Cardiology", "Orthopedics", "Oncology", "Neurology", "General Practice", "Pediatrics"]) for _ in provider_ids],
        "facility_id": [random.choice(facility_ids) for _ in provider_ids],
        "npi": [str(random.randint(1000000000, 9999999999)) for _ in provider_ids],
    })

    dim_facility = pd.DataFrame({
        "facility_id": facility_ids,
        "facility_name": [f"{fake.city()} Medical Center" for _ in facility_ids],
        "facility_type": [random.choice(["Hospital", "Clinic", "Urgent Care", "Specialist Center"]) for _ in facility_ids],
        "state": [fake.state_abbr() for _ in facility_ids],
        "bed_count": [random.randint(20, 500) for _ in facility_ids],
    })

    fact_encounters = pd.DataFrame({
        "encounter_id": [f"ENC-{i:07d}" for i in range(n)],
        "date": _date_range(365, n),
        "patient_id": [random.choice(patient_ids) for _ in range(n)],
        "provider_id": [random.choice(provider_ids) for _ in range(n)],
        "facility_id": [random.choice(facility_ids) for _ in range(n)],
        "encounter_type": [random.choice(["Inpatient", "Outpatient", "Emergency", "Telehealth"]) for _ in range(n)],
        "primary_diagnosis": [random.choice(diagnosis_codes) for _ in range(n)],
        "length_of_stay_days": [random.randint(0, 30) for _ in range(n)],
        "total_charge": [round(random.uniform(100, 50000), 2) for _ in range(n)],
        "readmission_30d": [random.choice([False] * 9 + [True]) for _ in range(n)],
    })

    return {
        "dim_patient": dim_patient,
        "dim_provider": dim_provider,
        "dim_facility": dim_facility,
        "fact_encounters": fact_encounters,
    }


# ─── LIFE SCIENCE ──────────────────────────────────────────────────────────────

def generate_life_science(n: int = 1000) -> dict[str, pd.DataFrame]:
    trial_ids = [f"TRIAL-{i:04d}" for i in range(1, 51)]
    compound_ids = [f"COMP-{i:04d}" for i in range(1, 101)]
    site_ids = [f"SITE-{i:03d}" for i in range(1, 31)]
    subject_ids = [f"SUBJ-{i:05d}" for i in range(1, 501)]

    dim_trial = pd.DataFrame({
        "trial_id": trial_ids,
        "trial_name": [f"Study {fake.word().capitalize()}-{random.randint(100,999)}" for _ in trial_ids],
        "phase": [random.choice(["Phase I", "Phase II", "Phase III", "Phase IV"]) for _ in trial_ids],
        "therapeutic_area": [random.choice(["Oncology", "Neurology", "Cardiology", "Immunology", "Rare Disease"]) for _ in trial_ids],
        "start_date": [fake.date_between("-5y", "-1y").strftime("%Y-%m-%d") for _ in trial_ids],
        "status": [random.choice(["Recruiting", "Active", "Completed", "Terminated"]) for _ in trial_ids],
    })

    dim_compound = pd.DataFrame({
        "compound_id": compound_ids,
        "compound_name": [f"Compound-{fake.lexify('??').upper()}{random.randint(100,999)}" for _ in compound_ids],
        "mechanism": [random.choice(["Inhibitor", "Agonist", "Antagonist", "Monoclonal Antibody", "Gene Therapy"]) for _ in compound_ids],
        "modality": [random.choice(["Small Molecule", "Biologic", "Cell Therapy", "RNA"]) for _ in compound_ids],
        "development_stage": [random.choice(["Preclinical", "Clinical", "Approved", "Withdrawn"]) for _ in compound_ids],
    })

    dim_site = pd.DataFrame({
        "site_id": site_ids,
        "site_name": [f"{fake.city()} Research Institute" for _ in site_ids],
        "country": [fake.country() for _ in site_ids],
        "principal_investigator": [f"Dr. {fake.last_name()}" for _ in site_ids],
        "capacity": [random.randint(10, 200) for _ in site_ids],
    })

    fact_observations = pd.DataFrame({
        "observation_id": [f"OBS-{i:07d}" for i in range(n)],
        "date": _date_range(365 * 3, n),
        "trial_id": [random.choice(trial_ids) for _ in range(n)],
        "compound_id": [random.choice(compound_ids) for _ in range(n)],
        "site_id": [random.choice(site_ids) for _ in range(n)],
        "subject_id": [random.choice(subject_ids) for _ in range(n)],
        "visit_type": [random.choice(["Screening", "Baseline", "Week 4", "Week 12", "Week 24", "End of Study"]) for _ in range(n)],
        "primary_endpoint_value": [round(random.uniform(0, 100), 2) for _ in range(n)],
        "adverse_event": [random.choice([None] * 8 + ["Nausea", "Fatigue", "Headache", "Dizziness"]) for _ in range(n)],
        "adverse_event_severity": [random.choice(["Mild", "Moderate", "Severe"]) if random.random() < 0.2 else None for _ in range(n)],
        "dropout": [random.choice([False] * 19 + [True]) for _ in range(n)],
    })

    return {
        "dim_trial": dim_trial,
        "dim_compound": dim_compound,
        "dim_site": dim_site,
        "fact_observations": fact_observations,
    }


GENERATORS = {
    "Retail": generate_retail,
    "Manufacturing": generate_manufacturing,
    "FSI": generate_fsi,
    "Healthcare": generate_healthcare,
    "Life Science": generate_life_science,
}


def generate_data(industry: str, n: int = 1000) -> dict[str, pd.DataFrame]:
    if industry not in GENERATORS:
        raise ValueError(f"Unknown industry: {industry}. Choose from: {list(GENERATORS.keys())}")
    return GENERATORS[industry](n)
