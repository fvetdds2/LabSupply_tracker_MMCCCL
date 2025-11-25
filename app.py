import io
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import plotly.express as px
import os
from io import BytesIO

st.set_page_config(page_title="Lab Supply Inventory", layout="wide")
st.title("Lab Supply Inventory — Interactive Dashboard")

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

# ============================================================
# STEP 8 — EXPIRING SOON LIST DOWNLOAD (item + cat_no)
# ============================================================
exp_soon_df = df[df["status"] == "expiring_soon"][["item", "cat_no"]]

st.subheader("Items Expiring in 30 Days")
st.dataframe(exp_soon_df)

csv_data = exp_soon_df.to_csv(index=False).encode("utf-8")

st.download_button(
    "Download Expiring Soon (item + cat_no)",
    data=csv_data,
    file_name="expiring_items.csv",
    mime="text/csv"
)

st.markdown("---")

# ============================================================
# STEP 9 — PIE CHARTS
# ============================================================
st.header("Status Dashboard")

counts = df["status"].value_counts().reindex(["expired", "expiring_soon", "ok"]).fillna(0)

fig = px.pie(
    names=counts.index,
    values=counts.values,
    title="Overall Inventory Status",
    color=counts.index,
    color_discrete_map={
        "expired": "red",
        "expiring_soon": "yellow",
        "ok": "green"
    }
)

st.plotly_chart(fig, use_container_width=True)

# Group by type
st.subheader("By Type")

types = sorted(df["type"].dropna().unique().astype(str))

for t in types:
    sub = df[df["type"].astype(str) == t]
    counts = sub["status"].value_counts().reindex(["expired", "expiring_soon", "ok"]).fillna(0)

    fig2 = px.pie(
        names=counts.index,
        values=counts.values,
        title=f"Type: {t}",
        color=counts.index,
        color_discrete_map={
            "expired": "red",
            "expiring_soon": "yellow",
            "ok": "green"
        }
    )
    st.plotly_chart(fig2, use_container_width=True)
