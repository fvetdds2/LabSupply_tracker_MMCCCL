import io
import pandas as pd
from datetime import datetime, timedelta
import streamlit as st
import plotly.express as px
import os
from io import BytesIO
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
st.set_page_config(page_title="MMCCCL Laboratory Supply Tracker", layout="wide")

# --- Elegant Light-Themed Header Layout ---
st.markdown("""
    <style>
    .header-container {
        display: flex;
        align-items: center;
        gap: 1.2rem;
        padding: 1rem 1.5rem;
        background: linear-gradient(90deg, #f9f3f4 0%, #f2e5e8 60%, #ffffff 100%);
        border-radius: 12px;
        border: 1px solid #e3d8da;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
        margin-bottom: 1.5rem;
    }

    .logo-left {
        width: 170px;
        max-height: 80px;
        object-fit: contain;
        background-color: white;
        padding: 0.3rem;
        border-radius: 8px;
        border: 1px solid #eee;
    }

    .main-header {
        color: #6e1e33;  /* Meharry maroon */
        font-size: 1.0rem;
        font-weight: 650;
        line-height: 1.25;
        margin: 0;
        letter-spacing: 0.2px;
    }

    .sub-header {
        color: #7a4f55;  /* softer complementary tone */
        font-size: 0.6rem;
        font-weight: 400;
        margin-top: 0.25rem;
        letter-spacing: 0.3px;
    }

    @media (max-width: 768px) {
        .main-header { font-size: 1.0rem; }
        .sub-header { font-size: 0.8rem; }
    }
    </style>
""", unsafe_allow_html=True)

# --- Header / Logo ---
logo_path = "mmcccl_logo.png"
logo_html = ""
if Path(logo_path).exists():
    logo_base64 = base64.b64encode(open(logo_path, "rb").read()).decode()
    logo_html = f'<img src="data:image/png;base64,{logo_base64}" class="logo-left" />'

# --- Render Header ---
st.markdown(f"""
<div class="header-container">
    <div>{logo_html}</div>
    <div>
        <h1 class="main-header">MMCCCL Onboarding Document Review & Sign</h1>
        <p class="sub-header">Meharry Medical College Consolidated Clinical Laboratories </p>
    </div>
</div>
""", unsafe_allow_html=True)

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
# STEP 9 — PIE CHARTS (Revised for custom grouping)
# ============================================================
st.header("Inventory Status Breakdown by Type")

# Define Custom Chart Groups based on user request (Pools multiple 'type' values)
CHART_GROUPS = {
    # Universal Calibrator Groups
    "Universal Calibrator 1": ["AST 2", "uric 2", "TPRO2", "ALT2"],
    "Universal Calibrator 2": ["HDL"],
    "Universal Calibrator 3": ["Chole", "Creatinine", "glucose", "triglycerides", "urea", "total protein 2"],
    
    # QC Groups
    "QC1": ["FSH", "Free T3", "Free T4", "Testo", "TSH", "Total T4", "Total T3", "Vitamiin D"],
    "QC2": ["alblumin BCP", "ALKP", "ALT", "AST", "Bliirubin", "calcium", "CO2", "ICT", "Choles", "CRP", "Glucose", "total protein", "Rheumatoid", "Trigly", "urea nitrogen", "uric acid"],
    "QC3": ["creatinine", "microalbumin"],
}

# Filter out rows with missing item names or zero quantity before plotting
# Ensure 'type' is treated as a string for robust comparison
df_plot = df[df['item'].notna() & (df['quantity'] > 0)].copy()
df_plot['type'] = df_plot['type'].astype(str)

# Set to track types that have been included in a custom group
used_types = set()

# --- Shared Chart Generation Function ---
def generate_pie_chart(data_frame, title_name):
    """Helper function to generate a Plotly Pie Chart with custom labels."""
    if data_frame.empty:
        st.info(f"Chart Group: {title_name} — No valid items found.")
        return

    # Aggregate: sum quantity, and find the minimum (earliest) expiry date for each unique item/cat_no/alert combination
    # Group by the item details and the alert status
    summary = data_frame.groupby(["item", "cat_no", "alert"]).agg(
        quantity=('quantity', 'sum'),
        expiry_date=('expiry_date', 'min') 
    ).reset_index()

    if summary.empty:
        return

    # Create the text to display on the chart slice: Item Name + Qty + Date
    summary["date_str"] = summary["expiry_date"].dt.strftime('%Y-%m-%d').fillna('N/A')
    
    # Combine item name, catalog number, quantity, and expiration date for the custom text label
    summary["display_text"] = (
        summary["item"].astype(str) + " (" + summary["cat_no"].astype(str) + ")" +
        "<br>Qty: " + summary["quantity"].astype(str) +
        "<br>Exp: " + summary["date_str"]
    )
    
    # Use item name for the slice identity
    summary["label"] = summary["item"].astype(str) 

    # NOTE on "separated equally": Pie charts separate parts proportionally to the 'values' column (quantity).
    # Setting values to 'quantity' is standard for inventory breakdown. If you truly need equal slices, 
    # you would set values=1, but that would misrepresent the inventory breakdown by quantity.
    fig = px.pie(
        summary,
        names="label",        
        values="quantity",    # Slice size is proportional to Quantity
        color="alert",        
        title=f"Chart Group: {title_name} — Item Quantity Breakdown",
        color_discrete_map={  # Color mapping
            "red": "red",
            "yellow": "yellow",
            "green": "green"
        }
    )

    # Use the custom 'display_text' for the slice text, and explicitly remove percentage
    fig.update_traces(
        text=summary["display_text"], 
        textinfo='text',             
        hovertemplate='%{text}<extra></extra>' 
    )

    st.plotly_chart(fig, use_container_width=True)

# 1. Generate charts for the Custom Groups
st.subheader("Charts for Calibrator and QC Groupings")
for chart_name, source_types in CHART_GROUPS.items():
    # Filter the plot data to include all rows whose 'type' is in the source list
    sub = df_plot[df_plot['type'].isin(source_types)].copy()
    
    # Add the source types to the set of used types
    used_types.update(source_types)
    
    generate_pie_chart(sub, chart_name)

# 2. Generate charts for any remaining single 'type' categories
st.subheader("Charts for Remaining Individual Types")
all_types = set(df_plot["type"].dropna().unique())
remaining_types = sorted(list(all_types - used_types))

if not remaining_types:
    st.info("All relevant item types were included in the custom Calibrator/QC charts above.")
else:
    for t in remaining_types:
        # Filter the plot data for the specific remaining type
        sub = df_plot[df_plot["type"] == t].copy()
        
        # Use the original type name as the title
        generate_pie_chart(sub, t)