# Fabric Data Demo Generator — Executive Narrative

---

## 🔴 The Problem

Every Fabric demo, POC, or data agent evaluation needs **realistic data sitting in a governed model** — and building one by hand takes the better part of a day. Today, teams either:

- Load a toy CSV — no star schema, no relationships, no measures, nothing worth showing
- Hand-build the Lakehouse and semantic model — hours of clicking, easy to get subtly wrong
- Ship an undescribed model — the data agent answers badly, or refuses to answer at all

**Result:** the demo environment becomes the bottleneck. The story you wanted to tell about Fabric never gets told, because you spent the day preparing data instead.

---

## 💡 The Why

> *"You can't show what a data agent can do on an empty workspace."*

Anyone demoing, evaluating, or teaching Microsoft Fabric needs a **repeatable way to stand up a production-shaped model** that:

- Looks like a real business — a star schema, not a row dump
- Uses the modern default (Direct Lake on OneLake), not an import copy
- Carries descriptions on every table, column, and measure — the thing data agents actually read
- Runs the same way in any workspace, in minutes, as often as you like

---

## ⚙️ The How

**One app. Five industries. Two modes.**

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│     Generate     │───▶│    Provision     │───▶│      Model       │
│  Synthetic data  │    │ Lakehouse + Delta│    │ Direct Lake + Ont│
│                  │    │                  │    │                  │
│ • Fact + 3 dims  │    │ • CSV → OneLake  │    │ • Described      │
│ • Up to 10k rows │    │ • Load Table API │    │   semantic model │
│ • Realistic keys │    │ • Layout auto-   │    │ • DAX measures   │
│   & distributions│    │   detected       │    │ • Ontology       │
└──────────────────┘    └──────────────────┘    └──────────────────┘
     Local Python            Fabric REST         Fabric + Power BI
```

| Industry | Fact Table | Key Dimensions |
|---|---|---|
| 🛒 **Retail** | `fact_sales` | store, product, customer |
| 🏭 **Manufacturing** | `fact_production` | machine, product, plant |
| 🏦 **FSI** | `fact_transactions` | customer, account, branch |
| 🏥 **Healthcare** | `fact_encounters` | patient, provider, facility |
| 🔬 **Life Science** | `fact_observations` | trial, compound, site |

---

## 🎯 The What

**A Gradio web app that provisions a complete Fabric demo** into your own workspace:

| Deliverable | Description |
|---|---|
| **5 Industry Datasets** | Retail, Manufacturing, FSI, Healthcare, Life Science — a star schema each |
| **Lakehouse + Delta Tables** | CSVs uploaded to OneLake, converted via the Load Table API |
| **Direct Lake Semantic Model** | Relationships, DAX measures, and a business description on every object |
| **Fabric Ontology** | The same domain as entity types, properties, and relationships |
| **Two Output Modes** | CSV files only, or full provisioning end-to-end |
| **Streamed Log** | Every step reported live, with non-fatal failure handling |

---

## 🏆 The Value

### vs. Building the Demo by Hand

| Capability | Manual Build | **This Generator** |
|---|---|---|
| Realistic star schema across 5 industries | Hours | **Minutes** |
| Direct Lake model built for you | ❌ | ✅ |
| Descriptions that make data agents work | Manual, skipped | **Built in** |
| Large storage format + framing | Manual, easy to miss | **Automatic** |
| Ontology item created | ❌ | ✅ |
| Repeatable in any workspace | Copy / paste / pray | **One click** |

### The Bottom Line

> **"Stop building demo data. Start demoing."**

The generator closes the gap between *"I'd like to show Fabric and a data agent"* and *"I have a governed, described, Direct Lake model with believable business data in my workspace."*

Column types are read back from Delta rather than guessed, the lakehouse layout is detected instead of assumed, and the model is framed before you ever open it — so the first question you ask actually returns an answer.

---

**Repository:** [github.com/claudiomirti/fabric-demo-generator](https://github.com/claudiomirti/fabric-demo-generator)
**Provision time:** ~3–5 minutes | **Platform:** Microsoft Fabric (Direct Lake on OneLake) | **Industries:** 5
