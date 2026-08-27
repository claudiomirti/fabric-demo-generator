"""
by Claudio Mirti

Microsoft Fabric Data Demo Generator
Gradio UI entry point.
"""
import gradio as gr

from src.auth import get_access_token, reset_credential
from src.orchestrator import MODE_CSV, MODE_FULL, provision, validate_workspace_id
from src.semantic_model import render_schema_text, SEMANTIC_MODELS

INDUSTRIES = list(SEMANTIC_MODELS.keys())
INDUSTRY_ICONS = {
    "Retail": "🛒 Retail",
    "Manufacturing": "🏭 Manufacturing",
    "FSI": "🏦 FSI",
    "Healthcare": "🏥 Healthcare",
    "Life Science": "🔬 Life Science",
}
INDUSTRY_LABELS = [INDUSTRY_ICONS[i] for i in INDUSTRIES]
LABEL_TO_INDUSTRY = {v: k for k, v in INDUSTRY_ICONS.items()}


MODE_CSV_LABEL = "📄 CSV files only"
MODE_FULL_LABEL = "🚀 Full provisioning — Delta tables + semantic model + ontology"
MODE_LABELS = {MODE_CSV_LABEL: MODE_CSV, MODE_FULL_LABEL: MODE_FULL}

# Shown under the mode selector so the choice is made with its consequences visible.
MODE_HELP = {
    MODE_CSV_LABEL: (
        "Creates the Lakehouse and uploads the generated data as **CSV files** to "
        "the Files section. Quickest option, and leaves the modelling to you."
    ),
    MODE_FULL_LABEL: (
        "Everything above, and then: converts each CSV into a **Delta table**, "
        "creates a **Direct Lake semantic model** with business descriptions on "
        "every table, column, and measure so a **Fabric data agent** can answer "
        "questions in plain language, and creates an **Ontology** describing the "
        "same domain as entities and relationships.\n\n"
        "_Takes a few minutes longer. Ontologies are a preview feature and need a "
        "supported Fabric capacity._"
    ),
}


def check_auth() -> tuple[str, str]:
    """Try to get a token and return (status_text, color_indicator)."""
    try:
        get_access_token()
        return "✅ Authenticated — ready to connect to Fabric.", "green"
    except Exception as e:
        return f"❌ Not authenticated: {e}", "red"


def on_login_click():
    msg, _ = check_auth()
    return msg


def on_logout_click():
    reset_credential()
    return "🔓 Logged out. Click **Login** to re-authenticate."


def on_industry_change(label: str) -> str:
    industry = LABEL_TO_INDUSTRY.get(label, label)
    return render_schema_text(industry)


def on_validate_workspace(workspace_id: str) -> str:
    _, msg = validate_workspace_id(workspace_id)
    return msg


def on_mode_change(label: str) -> str:
    return MODE_HELP.get(label, "")


def on_provision(label: str, workspace_id: str, row_count: int, mode_label: str):
    industry = LABEL_TO_INDUSTRY.get(label, label)
    mode = MODE_LABELS.get(mode_label, MODE_CSV)
    log_lines = []
    for line in provision(industry, workspace_id, int(row_count), mode):
        log_lines.append(line)
        yield "\n".join(log_lines)


# ─────────────────────────────────────────────────────────────────────────────
# UI Layout
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
.gr-button-primary { background: #0078d4 !important; color: white !important; }
.title-row { text-align: center; }
.status-box textarea { font-size: 13px !important; }
"""

with gr.Blocks(title="Fabric Data Demo Generator") as app:

    # ── Header ────────────────────────────────────────────────────────────────
    gr.Markdown(
        """
        # 🏭 Microsoft Fabric — Data Demo Generator
        Generate industry-specific synthetic datasets and provision them directly into your **Microsoft Fabric** workspace.
        """,
        elem_classes="title-row",
    )

    # ── Step 1: Authentication ─────────────────────────────────────────────────
    with gr.Accordion("🔐 Step 1 — Authenticate to Microsoft Fabric", open=True):
        gr.Markdown(
            "Uses your **Azure CLI** session (`az login`) or opens a browser login prompt. "
            "No credentials are stored by this app."
        )
        with gr.Row():
            btn_login = gr.Button("🔑 Login / Verify Auth", variant="primary", scale=2)
            btn_logout = gr.Button("🔓 Logout", variant="secondary", scale=1)
        auth_status = gr.Markdown("_Click Login to verify your authentication status._")

        btn_login.click(on_login_click, outputs=auth_status)
        btn_logout.click(on_logout_click, outputs=auth_status)

    # ── Step 2: Industry + Workspace ──────────────────────────────────────────
    with gr.Accordion("⚙️ Step 2 — Configure Your Demo", open=True):
        with gr.Row():
            with gr.Column(scale=1):
                industry_radio = gr.Radio(
                    choices=INDUSTRY_LABELS,
                    value=INDUSTRY_LABELS[0],
                    label="🏢 Select Industry",
                    interactive=True,
                )
                row_slider = gr.Slider(
                    minimum=100,
                    maximum=10000,
                    value=1000,
                    step=100,
                    label="📊 Rows to Generate per Fact Table",
                    info="More rows = richer dataset, but slower upload.",
                )
            with gr.Column(scale=2):
                workspace_input = gr.Textbox(
                    label="🔗 Fabric Workspace ID",
                    placeholder="e.g. 00000000-0000-0000-0000-000000000000",
                    info="Find it in the Fabric portal URL: app.fabric.microsoft.com/groups/{workspace-id}/...",
                    lines=1,
                )
                validate_btn = gr.Button("🔎 Validate Workspace", variant="secondary")
                workspace_status = gr.Markdown("_Enter your Workspace ID and click Validate._")

                validate_btn.click(
                    on_validate_workspace,
                    inputs=workspace_input,
                    outputs=workspace_status,
                )

    # ── Step 3: Schema Preview ─────────────────────────────────────────────────
    with gr.Accordion("📐 Step 3 — Preview Semantic Model Schema", open=True):
        schema_preview = gr.Markdown(
            value=render_schema_text(INDUSTRIES[0]),
            label="Schema Preview",
        )
        industry_radio.change(
            on_industry_change,
            inputs=industry_radio,
            outputs=schema_preview,
        )

    # ── Step 4: Output mode ───────────────────────────────────────────────────
    with gr.Accordion("🎯 Step 4 — Choose What to Create", open=True):
        mode_radio = gr.Radio(
            choices=[MODE_CSV_LABEL, MODE_FULL_LABEL],
            value=MODE_CSV_LABEL,
            label="Output mode",
            interactive=True,
        )
        mode_help = gr.Markdown(MODE_HELP[MODE_CSV_LABEL])
        mode_radio.change(on_mode_change, inputs=mode_radio, outputs=mode_help)

    # ── Step 5: Provision ─────────────────────────────────────────────────────
    with gr.Accordion("🚀 Step 5 — Provision to Fabric", open=True):
        gr.Markdown(
            "Runs the provisioning selected in Step 4 and streams the log below. "
            "Re-running for the same industry reuses the Lakehouse and replaces "
            "the semantic model and ontology, so it is safe to run more than once."
        )
        provision_btn = gr.Button("🚀 Start Provisioning", variant="primary", size="lg")
        log_output = gr.Textbox(
            label="📋 Provisioning Log",
            lines=20,
            max_lines=40,
            interactive=False,
            placeholder="Provisioning log will appear here...",
        )

        provision_btn.click(
            on_provision,
            inputs=[industry_radio, workspace_input, row_slider, mode_radio],
            outputs=log_output,
        )

    # ── Footer ────────────────────────────────────────────────────────────────
    gr.Markdown(
        """
        ---
        📌 **Tip:** After provisioning, open the Lakehouse in Fabric → **Load to Tables** on each CSV → 
        then use **New semantic model** to create a Power BI model matching the schema shown above.
        
        💬 **Demo Questions:** See [`DEMO_QUESTIONS.md`](./DEMO_QUESTIONS.md) for ready-made questions
        to ask your Fabric Copilot or data agent once the dataset is live.

        🔒 This app does **not** store any credentials or data beyond your session.

        ---
        <div style="text-align:center; opacity:0.75;">Made by <b>Claudio Mirti</b></div>
        """
    )


if __name__ == "__main__":
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        inbrowser=True,
        theme=gr.themes.Soft(primary_hue="blue", secondary_hue="sky"),
        css=CSS,
    )
