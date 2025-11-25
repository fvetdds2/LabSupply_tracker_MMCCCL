import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import plotly.express as px
import os
from io import BytesIO

# ===========================
# SIMPLE LOGIN / PASSCODE
# ===========================
PASSCODE = "mmcccl2025"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.set_page_config(page_title="MMCCCL Laboratory Supplies Tracker", layout="wide")
    st.title("🔒 MMCCCL lab supply tracker")

    pass_input = st.text_input("Enter Passcode:", type="password")

    if st.button("Submit"):
        if pass_input == PASSCODE:
            st.session_state.authenticated = True
            st.success("✅ Access granted. Loading dashboard...")
            st.rerun()
        else:
            st.error("❌ Incorrect passcode. Please try again.")

    st.stop()

# ===========================
# PAGE SETUP
# ===========================
st.set_page_config(page_title="MMCCCL Laboratory Supplies Tracker", layout="wide")

EXCEL_PATH = "MMCCCL_supply_Nov25-2025.xlsx"

# --- Header layout ---
col1, col2 = st.columns([1, 3])

with col1:
    # logo file must be in same folder as app.py
    if os.path.exists("mmcccl_logo.png"):
        st.image("mmcccl_logo.png", use_column_width=True)
    else:
        st.write("mmcccl_logo.png not found in repo.")

with col2:
    st.markdown(
        """
        <h1 style="font-size: 50px; margin-bottom: 0px;">
            MMCCCL Laboratory Supplies Tracker
        </h1>
        <p style="font-size: 25px; margin-top: -10px; color: #555;">
            Inventory Management Dashboard
        </p>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# ============================================================
# STEP 1 — LOAD EXCEL FILE FROM REPO
# ============================================================
if not os.path.exists(EXCEL_PATH):
    st.error(f"❌ Excel file not found in repo: {EXCEL_PATH}")
    st.info("Make sure the file is inside your repository root in GitHub Codespaces.")
    st.stop()

df = pd.read_excel(EXCEL_PATH)
df_orig = df.copy()  # for auto-detection helper

st.subheader("📊 Supply Inventory Data (Raw)")
st.dataframe(df, use_container_width=True)

# ============================================================
# STEP 2 — COLUMN AUTO-DETECTION HELPERS
# ============================================================
def find_col(df_in, candidates):
    cols = df_in.columns.tolist()
    lower = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in lower:
            return lower[cand.lower()]
    for cand in candidates:
        for c in cols:
            if cand.lower() in c.lower():
                return c
    return None

auto_platform = find_col(df_orig, ["platform", "site"])
auto_type = find_col(df_orig, ["type", "category"])
auto_item = find_col(df_orig, ["item", "description", "item_description"])
auto_catno = find_col(df_orig, ["cat_no", "catalog", "catalog_number"])
auto_qty = find_col(df_orig, ["quantity", "qty"])
auto_exp = find_col(df_orig, ["expiry", "expiration", "exp_date", "expiry_date"])

# ============================================================
# STEP 3 — SIDEBAR COLUMN MAPPING
# ============================================================
st.sidebar.header("Column Mapping")

platform_col = st.sidebar.text_input("Platform column", value=auto_platform or "platform")
type_col = st.sidebar.text_input("Type column", value=auto_type or "type")
item_col = st.sidebar.text_input("Item column", value=auto_item or "item")
cat_col = st.sidebar.text_input("Catalog number column", value=auto_catno or "cat_no")
qty_col = st.sidebar.text_input("Quantity column", value=auto_qty or "quantity")
expiry_col = st.sidebar.text_input("Expiry date column", value=auto_exp or "expiry_date")

df = df_orig.copy()

# If columns missing, create them
for col in [platform_col, type_col, item_col, cat_col, qty_col, expiry_col]:
    if col not in df.columns:
        df[col] = pd.NA

# Normalize names
df = df.rename(
    columns={
        platform_col: "platform",
        type_col: "type",
        item_col: "item",
        cat_col: "cat_no",
        qty_col: "quantity",
        expiry_col: "expiry_date",
    }
)

df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)

# Parse expiry dates
today = pd.to_datetime(datetime.now().date())
df["expiry_date"] = pd.to_datetime(df["expiry_date"], errors="coerce")

# ============================================================
# STEP 4 — STATUS LABELS
# ============================================================
df["status"] = "ok"
expired_mask = df["expiry_date"].notna() & (df["expiry_date"] < today)
exp_soon_mask = df["expiry_date"].notna() & (
    df["expiry_date"] <= today + pd.Timedelta(days=30)
)

df.loc[expired_mask, "status"] = "expired"
df.loc[exp_soon_mask & ~expired_mask, "status"] = "expiring_soon"

# Sort
df = df.sort_values(by=["platform", "type", "item"], na_position="last")

# ============================================================
# STEP 5 — SUMMARY METRICS
# ============================================================
st.subheader("Summary")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Items", int(df["item"].nunique()))
col2.metric("Total Quantity", int(df["quantity"].sum()))
col3.metric("Expired", int((df["status"] == "expired").sum()))
col4.metric("Expiring Soon", int((df["status"] == "expiring_soon").sum()))

st.markdown("---")

# ============================================================
# STEP 6 — EDITABLE TABLE
# ============================================================
st.header("Inventory Table (Editable Quantities)")

edit_df = st.data_editor(
    df[["platform", "type", "item", "cat_no", "quantity", "expiry_date", "status"]],
    num_rows="dynamic",
)

# Recalculate expiration status based on edited data
edit_df["expiry_date"] = pd.to_datetime(edit_df["expiry_date"], errors="coerce")

edit_df["status"] = "ok"
expired_mask = edit_df["expiry_date"].notna() & (edit_df["expiry_date"] < today)
exp_soon_mask = edit_df["expiry_date"].notna() & (
    edit_df["expiry_date"] <= today + pd.Timedelta(days=30)
)

edit_df.loc[expired_mask, "status"] = "expired"
edit_df.loc[exp_soon_mask & ~expired_mask, "status"] = "expiring_soon"

df = edit_df.copy()

# ============================================================
# STEP 7 — DOWNLOAD UPDATED EXCEL
# ============================================================
buffer = BytesIO()
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    df.to_excel(writer, index=False, sheet_name="inventory")
buffer.seek(0)

st.download_button(
    "Download Updated Inventory Excel",
    data=buffer,
    file_name="inventory_updated.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.markdown("---")

# ============================================================
# STEP 8 — EXPIRING SOON LIST DOWNLOAD (item + cat_no + quantity)
# ============================================================
exp_soon_df = df[df["status"] == "expiring_soon"][["item", "cat_no", "quantity"]]
exp_soon_grouped = (
    exp_soon_df.groupby(["item", "cat_no"]).agg({"quantity": "sum"}).reset_index()
)

st.subheader("Items Expiring in 30 Days (Item Name and Total Quantity)")
st.dataframe(exp_soon_grouped, use_container_width=True)

csv_data = exp_soon_grouped.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download Expiring Soon Items (item + cat_no + qty)",
    data=csv_data,
    file_name="expiring_items.csv",
    mime="text/csv",
)

st.markdown("---")

# ============================================================
# STEP 9 — PIE CHARTS WITH CORRECT GROUPING & HORIZONTAL LABELS
# ============================================================
st.header("Inventory Status Breakdown by Type")

# ---- Calibrator mapping: for each assay type, which Universal Calibrator type to add ----
CAL_MAP = {
    "AST 2": "Universal Calibrator 1",
    "uric 2": "Universal Calibrator 1",
    "TPRO2": "Universal Calibrator 1",
    "ALT2": "Universal Calibrator 1",
    "HDL": "Universal Calibrator 2",
    "Chole": "Universal Calibrator 3",
    "Creatinine": "Universal Calibrator 3",
    "glucose": "Universal Calibrator 3",
    "triglycerides": "Universal Calibrator 3",
    "urea": "Universal Calibrator 3",
    "total protein 2": "Universal Calibrator 3",
}

# ---- QC mapping: for each assay type, which QC type to add ----
QC_MAP = {
    # QC1
    "FSH": "QC1",
    "Free T3": "QC1",
    "Free T4": "QC1",
    "Testo": "QC1",
    "TSH": "QC1",
    "Total T4": "QC1",
    "Total T3": "QC1",
    "Vitamiin D": "QC1",
    # QC2
    "alblumin BCP": "QC2",
    "ALKP": "QC2",
    "ALT": "QC2",
    "AST": "QC2",
    "Bilirubin": "QC2",
    "calcium": "QC2",
    "CO2": "QC2",
    "ICT": "QC2",
    "Choles": "QC2",
    "CRP": "QC2",
    "Glucose": "QC2",
    "total protein": "QC2",
    "Rheumatoid": "QC2",
    "Trigly": "QC2",
    "urea nitrogen": "QC2",
    "uric acid": "QC2",
    # QC3
    "creatinine": "QC3",
    "microalbumin": "QC3",
}

# Add alert color for plotting
df_plot = df.copy()
df_plot["alert"] = df_plot["status"].map(
    {"expired": "red", "expiring_soon": "yellow", "ok": "green"}
)

# Ensure 'type' is string for grouping
df_plot["type"] = df_plot["type"].astype(str)

def make_pie(df_sub, title):
    """Create a pie chart with equal slices and horizontal labels."""
    if df_sub.empty:
        return

    df_sub = df_sub.copy()
    df_sub["exp_str"] = df_sub["expiry_date"].dt.strftime("%Y-%m-%d").fillna("N/A")
    df_sub["label"] = (
        df_sub["item"].astype(str)
        + " — Qty: "
        + df_sub["quantity"].astype(str)
        + " — Exp: "
        + df_sub["exp_str"]
    )

    fig = px.pie(
        df_sub,
        names="item",
        values=[1] * len(df_sub),  # equal slice sizes
        color="alert",
        title=title,
        color_discrete_map={"red": "red", "yellow": "yellow", "green": "green"},
    )
    fig.update_traces(
        text=df_sub["label"],
        textinfo="text",
        hovertemplate="%{text}<extra></extra>",
    )
    st.plotly_chart(fig, use_container_width=True)

all_types = sorted(df_plot["type"].dropna().unique())

for t in all_types:
    base = df_plot[df_plot["type"] == t]
    if base.empty:
        continue

    combined = base.copy()

    # Add Universal Calibrator if mapping exists
    if t in CAL_MAP:
        cal_type = CAL_MAP[t]
        cal_rows = df_plot[df_plot["type"] == cal_type]
        combined = pd.concat([combined, cal_rows], ignore_index=True)

    # Add QC if mapping exists
    if t in QC_MAP:
        qc_type = QC_MAP[t]
        qc_rows = df_plot[df_plot["type"] == qc_type]
        combined = pd.concat([combined, qc_rows], ignore_index=True)

    make_pie(combined, f"Type: {t}")

