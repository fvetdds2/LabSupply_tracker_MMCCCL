import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import plotly.express as px   # currently unused, but ok to leave
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

EXCEL_PATH = "MMCCCL_supply_Nov26-2025.xlsx"

# --- Header layout ---
col1, col2 = st.columns([1, 3])

with col1:
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
df_orig = df.copy()

st.subheader("📊 Supply Inventory Raw Data")
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

#============================================================
# STEP 3 — STANDARDIZE COLUMNS (NO SIDEBAR)
# ============================================================

df = df_orig.copy()

# choose actual column names (fall back to default names if not found)
platform_col = auto_platform or "platform"
type_col = auto_type or "type"
item_col = auto_item or "item"
cat_col = auto_catno or "cat_no"
qty_col = auto_qty or "quantity"
expiry_col = auto_exp or "expiry_date"

# create missing cols if they do not exist
for col in [platform_col, type_col, item_col, cat_col, qty_col, expiry_col]:
    if col not in df.columns:
        df[col] = pd.NA

# rename to internal standard column names
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

# numeric quantity
df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)

# clean type labels
df["type"] = df["type"].astype(str).str.strip()

# parse dates
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

edit_df["expiry_date"] = pd.to_datetime(edit_df["expiry_date"], errors="coerce")

edit_df["status"] = "ok"
expired_mask = edit_df["expiry_date"].notna() & (edit_df["expiry_date"] < today)
exp_soon_mask = edit_df["expiry_date"].notna() & (
    edit_df["expiry_date"] <= today + pd.Timedelta(days=30)
)

edit_df.loc[expired_mask, "status"] = "expired"
edit_df.loc[exp_soon_mask & ~expired_mask, "status"] = "expiring_soon"

edit_df["type"] = edit_df["type"].astype(str).str.strip()

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
# STEP 8 — EXPIRING SOON LIST DOWNLOAD
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
# STEP 9 — STATUS MATRIX (Reagent / Calibrator / QC + quantities)
# ============================================================

st.header("Status Matrix — Reagent / Calibrator / QC by Test Type")

CAL_MAP = {
    "AST2": "Universal Calibrator1",
    "Uric Acid 2": "Universal Calibrator1",
    "ALT2": "Universal Calibrator1",
    "Ultra HDL": "Universal Calibrator2",
    "Choles": "Universal Calibrator3",
    "Creatinine": "Universal Calibrator3",
    "Glucose": "Universal Calibrator3",
    "TRIG": "Universal Calibrator3",
    "Urea": "Universal Calibrator3",
    "Albumin BCP": "Universal Calibrator3",
    "Calcium": "Universal Calibrator3",
    "Total Protein2": "Universal Calibrator3",
}

QC_MAP = {
    "FSH": "QC1",
    "Free T3": "QC1",
    "Anti-TPO": "QC1",
    "Free T4": "QC1",
    "Testosterone": "QC1",
    "TSH": "QC1",
    "Total T4": "QC1",
    "Total T3": "QC1",
    "Vitamin D": "QC1",
    "Albumin BCP": "QC2",
    "ALKP": "QC2",
    "ALT2": "QC2",
    "AST2": "QC2",
    "Billirubin": "QC2",
    "Calcium": "QC2",
    "CO2": "QC2",
    "ICT": "QC2",
    "Choles": "QC2",
    "CRP": "QC2",
    "Glucose": "QC2",
    "Total Protein2": "QC2",
    "Rheumatoid": "QC2",
    "TRIG": "QC2",
    "Urea": "QC2",
    "Ultra HDL": "QC2",
    "Uric Acid 2": "QC2",
    "Creatinine": "QC3",
    "Microalbumin": "QC3",
}

def classify_component(item_name: str) -> str:
    name = str(item_name).lower()
    if "reagent" in name:
        return "Reagent"
    if "calibrator" in name or "calib" in name:
        return "Calibrator"
    if "qc" in name or "control" in name:
        return "QC"
    return "Other"

matrix_df_src = df.copy()
matrix_df_src["component"] = matrix_df_src["item"].apply(classify_component)
matrix_df_src["type"] = matrix_df_src["type"].astype(str).str.strip()

def get_status_and_qty(sub: pd.DataFrame):
    if sub.empty:
        return "missing", 0
    qty = int(sub["quantity"].sum())
    if (sub["status"] == "expired").any():
        status = "expired"
    elif (sub["status"] == "expiring_soon").any():
        status = "expiring_soon"
    else:
        status = "ok"
    return status, qty

# 🚫 Types that should NOT appear as rows in the matrix
EXCLUDE_TYPES = {
    "universal calibrator1",
    "universal calibrator2",
    "universal calibrator3",
    "maintenance",
    "nan",
    "test supply",
    "qc1",
    "qc2",
    "qc3",
}

types_in_data = set(matrix_df_src["type"].dropna().unique())

test_types = sorted(
    t for t in types_in_data
    if str(t).strip().lower() not in EXCLUDE_TYPES
)

rows = []
for t in test_types:
    row = {"Type": t}

    # Reagent
    sub_reag = matrix_df_src[
        (matrix_df_src["type"] == t) & (matrix_df_src["component"] == "Reagent")
    ]
    reag_status, reag_qty = get_status_and_qty(sub_reag)
    row["Reagent_status"] = reag_status
    row["Reagent_qty"] = reag_qty

    # Calibrator (local + mapped Universal Calibrator)
    sub_cal_local = matrix_df_src[
        (matrix_df_src["type"] == t) & (matrix_df_src["component"] == "Calibrator")
    ]
    if t in CAL_MAP:
        cal_type = CAL_MAP[t]
        sub_cal_shared = matrix_df_src[
            (matrix_df_src["type"] == cal_type)
            & (matrix_df_src["component"] == "Calibrator")
        ]
        sub_cal = pd.concat([sub_cal_local, sub_cal_shared])
    else:
        sub_cal = sub_cal_local
    cal_status, cal_qty = get_status_and_qty(sub_cal)
    row["Calibrator_status"] = cal_status
    row["Calibrator_qty"] = cal_qty

    # QC (local + mapped QC1/2/3)
    sub_qc_local = matrix_df_src[
        (matrix_df_src["type"] == t) & (matrix_df_src["component"] == "QC")
    ]
    if t in QC_MAP:
        qc_type = QC_MAP[t]
        sub_qc_shared = matrix_df_src[
            (matrix_df_src["type"] == qc_type)
            & (matrix_df_src["component"] == "QC")
        ]
        sub_qc = pd.concat([sub_qc_local, sub_qc_shared])
    else:
        sub_qc = sub_qc_local
    qc_status, qc_qty = get_status_and_qty(sub_qc)
    row["QC_status"] = qc_status
    row["QC_qty"] = qc_qty

    rows.append(row)

status_matrix = pd.DataFrame(rows).set_index("Type")

status_display = status_matrix.copy()
status_display[["Reagent_status", "Calibrator_status", "QC_status"]] = (
    status_display[["Reagent_status", "Calibrator_status", "QC_status"]].replace(
        {
            "ok": "🟢 OK",
            "expiring_soon": "🟡 Soon",
            "expired": "🔴 Expired",
            "missing": "⚪ Missing",
        }
    )
)

st.dataframe(status_display, use_container_width=True)

st.markdown(
    """
**Legend:**  
🟢 OK – available • 🟡 Soon – expiring in 30 days  
🔴 Expired – expired • ⚪ Missing – no item in inventory  

Columns `_qty` show the **total quantity** of that component
(including shared Universal Calibrators and QC1/2/3 when mapped).
"""
)