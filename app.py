import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import plotly.express as px
import os
import io
from io import BytesIO
from pathlib import Path
import base64
# SIMPLE LOGIN / PASSCODE PROTECTION
# -------------------------------------------------
PASSCODE = "mmcccl2025"  

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Login form
if not st.session_state.authenticated:
    st.title("🔒 MMCCCL lab supply tracker")

    pass_input = st.text_input("Enter Passcode:", type="password")

    if st.button("Submit"):
        if pass_input == PASSCODE:
            st.session_state.authenticated = True
            st.success("✅ Access granted. Loading dashboard...")
            st.rerun()
        else:
            st.error("❌ Incorrect passcode. Please try again.")

    st.stop()  # Stop the script here if not authenticated


# -------------------------------------------------
# PAGE SETUP
st.set_page_config(page_title="MMCCCL Laboratory Supplies Tracker", layout="wide")

import streamlit as st

# --- Header layout ---
col1, col2 = st.columns([1, 3])

with col1:
    st.image("mmcccl_logo.png", use_column_width=True)

with col2:
    st.markdown("""
        <h1 style="font-size: 50px; margin-bottom: 0px;">
            MMCCCL Laboratory Supplies Tracker
        </h1>
        <p style="font-size: 25px; margin-top: -10px; color: #555;">
            Inventory Management Dashboard
        </p>
    """, unsafe_allow_html=True)

# ============================================================
# STEP 1 — UPLOAD EXCEL FILE
# ============================================================
uploaded_file = st.file_uploader("Upload Inventory Excel File", type=["xlsx"])

if uploaded_file is None:
    st.info("Please upload the Excel inventory file to begin.")
    st.stop()

# Read file
df_orig = pd.read_excel(uploaded_file)

# ============================================================
# STEP 2 — COLUMN AUTO-DETECTION HELPERS
# ============================================================
def find_col(df, candidates):
    cols = df.columns.tolist()
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
auto_exp = find_col(df_orig, ["expiry", "expiration", "exp_date"])

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
df = df.rename(columns={
    platform_col: "platform",
    type_col: "type",
    item_col: "item",
    cat_col: "cat_no",
    qty_col: "quantity",
    expiry_col: "expiry_date"
})

df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)

# Parse expiry dates
today = pd.to_datetime(datetime.now().date())
df["expiry_date"] = pd.to_datetime(df["expiry_date"], errors="coerce")

# ============================================================
# STEP 4 — STATUS LABELS
# ============================================================
df["status"] = "ok"
expired = df["expiry_date"].notna() & (df["expiry_date"] < today)
exp_soon = df["expiry_date"].notna() & (df["expiry_date"] <= today + pd.Timedelta(days=30))

df.loc[expired, "status"] = "expired"
df.loc[exp_soon & ~expired, "status"] = "expiring_soon"

# Sort
df = df.sort_values(by=["platform", "type", "item"], na_position="last")

# ============================================================
# STEP 5 — SUMMARY METRICS
# ============================================================
st.subheader("Summary")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Items", df["item"].nunique())
col2.metric("Total Quantity", int(df["quantity"].sum()))
col3.metric("Expired", (df["status"] == "expired").sum())
col4.metric("Expiring Soon", (df["status"] == "expiring_soon").sum())

st.markdown("---")

# ============================================================
# STEP 6 — EDITABLE TABLE
# ============================================================
st.header("Inventory Table (Editable Quantities)")

# 1. Display the editable subset of the DataFrame.
# edit_df is the new DataFrame containing user-modified values.
edit_df = st.data_editor(
    df[["platform", "type", "item", "cat_no", "quantity", "expiry_date", "status"]],
    num_rows="dynamic"
)

# 2. Re-calculate status based on the data edited by the user.
today = pd.to_datetime(datetime.now().date())
edit_df["expiry_date"] = pd.to_datetime(edit_df["expiry_date"], errors="coerce")

# Recalculate 'status' column
edit_df["status"] = "ok"
expired = edit_df["expiry_date"].notna() & (edit_df["expiry_date"] < today)
exp_soon = edit_df["expiry_date"].notna() & (edit_df["expiry_date"] <= today + pd.Timedelta(days=30))

edit_df.loc[expired, "status"] = "expired"
edit_df.loc[exp_soon & ~expired, "status"] = "expiring_soon"

# 3. Use the corrected, edited data for all subsequent steps (df is updated).
df = edit_df.copy()

# ============================================================
# STEP 7 — DOWNLOAD UPDATED EXCEL (Now using the corrected `df`)
# ============================================================
buffer = io.BytesIO()
# The issue was likely not having a writer object defined in the original traceback's context.
# Your current implementation correctly defines it using a context manager, which is best practice.
with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
    # Use the fully corrected `df` for the download
    df.to_excel(writer, index=False, sheet_name="inventory")
buffer.seek(0)

st.download_button(
    "Download Updated Inventory Excel",
    data=buffer,
    file_name="inventory_updated.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.markdown("---")

#STEP 8 — EXPIRING SOON LIST DOWNLOAD (item + cat_no + quantity)
# ============================================================
# Filter and select item, cat_no, and quantity
exp_soon_df = df[df["status"] == "expiring_soon"][["item", "cat_no", "quantity"]]

# Aggregate quantity for display/download if the same item/cat_no appears multiple times
exp_soon_grouped = exp_soon_df.groupby(["item", "cat_no"]).agg({"quantity": "sum"}).reset_index()

st.subheader("Items Expiring in 30 Days (Item Name and Total Quantity)")
st.dataframe(exp_soon_grouped, use_container_width=True) # Use the grouped data

csv_data = exp_soon_grouped.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download Expiring Soon Items (item + cat_no + qty)",
    data=csv_data,
    file_name="expiring_items.csv",
    mime="text/csv"
)

st.markdown("---")

# ============================================================
# STEP 9 — PIE CHARTS (Clean Version, Equal Slices)
# ============================================================

st.header("Inventory Status Breakdown by Type")

# ------------ Group Definitions ----------------
CAL_GROUPS = {
    "Universal Calibrator 1": ["AST 2", "uric 2", "TPRO2", "ALT2"],
    "Universal Calibrator 2": ["HDL"],
    "Universal Calibrator 3": [
        "Chole", "Creatinine", "glucose", "triglycerides", "urea", "total protein 2"
    ]
}

QC_GROUPS = {
    "QC1": ["FSH", "Free T3", "Free T4", "Testo", "TSH", "Total T4", "Total T3", "Vitamiin D"],
    "QC2": [
        "alblumin BCP", "ALKP", "ALT", "AST", "Bilirubin", "calcium",
        "CO2", "ICT", "Choles", "CRP", "Glucose", "total protein",
        "Rheumatoid", "Trigly", "urea nitrogen", "uric acid"
    ],
    "QC3": ["creatinine", "microalbumin"]
}

# Add alert color
df_plot = df.copy()
df_plot["alert"] = df_plot["status"].map({
    "expired": "red",
    "expiring_soon": "yellow",
    "ok": "green"
})


# ------------ Helper function to build pie chart -------------
def make_pie_chart(df_sub, title):
    if df_sub.empty:
        return

    # Build display text
    df_sub = df_sub.copy()
    df_sub["exp_str"] = df_sub["expiry_date"].dt.strftime("%Y-%m-%d").fillna("N/A")

    df_sub["label_text"] = (
        df_sub["item"].astype(str)
        + "<br>Qty: " + df_sub["quantity"].astype(str)
        + "<br>Exp: " + df_sub["exp_str"]
    )

    # Equal-sized slices → values=1
    fig = px.pie(
        df_sub,
        names="item",
        values=[1] * len(df_sub),
        color="alert",
        title=title,
        color_discrete_map={"red": "red", "yellow": "yellow", "green": "green"}
    )

    fig.update_traces(
        text=df_sub["label_text"],
        textinfo="text",
        hovertemplate="%{text}<extra></extra>"
    )

    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# 1️⃣ PIE CHARTS FOR UNIVERSAL CALIBRATOR GROUPS
# ============================================================
st.subheader("Universal Calibrator Charts")

for group_name, type_list in CAL_GROUPS.items():
    sub = df_plot[df_plot["type"].isin(type_list)]
    make_pie_chart(sub, group_name)


# ============================================================
# 2️⃣ PIE CHARTS FOR QC GROUPS (Added into Each Type’s Chart)
# ============================================================

st.subheader("Quality Control (QC) Charts")

all_qc_types = set(sum(QC_GROUPS.values(), []))  # flatten list

for t in sorted(all_qc_types):
    # Items of this specific type
    base = df_plot[df_plot["type"] == t]

    if base.empty:
        continue

    # Add QC items depending on which group this type belongs to
    qc_additions = pd.DataFrame()

    for qc_group, qc_types in QC_GROUPS.items():
        if t in qc_types:
            qc_additions = pd.concat([
                qc_additions,
                df_plot[df_plot["type"] == qc_group]
            ])

    combined = pd.concat([base, qc_additions])
    make_pie_chart(combined, f"{t} (with QC items)")


# ============================================================
# 3️⃣ PIE CHARTS FOR REMAINING INDIVIDUAL TYPES
# ============================================================

st.subheader("Other Individual Type Charts")

used_types = set(sum(CAL_GROUPS.values(), [])) | set(all_qc_types)
remaining = sorted(set(df_plot["type"].unique()) - used_types)

for t in remaining:
    sub = df_plot[df_plot["type"] == t]
    make_pie_chart(sub, t)
