import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from pathlib import Path
from datetime import date

st.set_page_config(
    page_title="Procura | Purchase Management",
    page_icon="🛍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
    --navy: #16324F;
    --navy-deep: #10263C;
    --teal: #0F766E;
    --teal-light: #DDF4F0;
    --ink: #1E293B;
    --muted: #64748B;
    --canvas: #F4F7FA;
    --line: #DCE5ED;
}
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    color: var(--ink);
}
.stApp { background: var(--canvas); }
.block-container { padding-top: 1.7rem; padding-bottom: 2rem; }
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--navy-deep) 0%, var(--navy) 100%);
    border-right: 1px solid #294760;
}
[data-testid="stSidebar"] * { color: #F8FAFC; }
[data-testid="stSidebar"] [aria-selected="true"] {
    background: rgba(45, 212, 191, 0.16);
    border-radius: 8px;
}
.hero {
    background: linear-gradient(120deg, #16324F 0%, #145B67 58%, #0F766E 100%);
    padding: 30px;
    border-radius: 18px;
    color: #FFFFFF;
    margin-bottom: 25px;
    box-shadow: 0 10px 26px rgba(22, 50, 79, .13);
}
.hero h1 { color: #FFFFFF; font-size: 34px; margin: 0; font-weight: 800; }
.hero p { color: #D9F3EF; margin: 8px 0 0 0; }
.metric-card {
    background: #FFFFFF;
    padding: 22px;
    border-radius: 14px;
    border: 1px solid var(--line);
    box-shadow: 0 4px 14px rgba(22, 50, 79, .045);
}
.metric-label { color: var(--muted); font-size: 13px; font-weight: 600; }
.metric-value { color: var(--navy); font-size: 27px; font-weight: 800; margin-top: 8px; }
.metric-icon { font-size: 25px; margin-bottom: 10px; }
.section-title { color: var(--navy); font-size: 21px; font-weight: 750; margin: 18px 0 12px 0; }
div[data-testid="stForm"], div[data-testid="stDataFrame"] {
    border-radius: 12px;
    border-color: var(--line);
}
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] > button {
    border-radius: 9px;
    font-weight: 600;
    border: 1px solid var(--teal);
    transition: all .15s ease-in-out;
}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primary"] {
    background: var(--teal);
    color: #FFFFFF;
}
.stButton > button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {
    background: #115E59;
    border-color: #115E59;
    color: #FFFFFF;
}
.stDownloadButton > button { color: var(--teal); background: #FFFFFF; }
.stDownloadButton > button:hover { color: #115E59; border-color: #115E59; }
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 15px 17px;
    box-shadow: 0 3px 12px rgba(22, 50, 79, .035);
}
[data-testid="stMetricLabel"] { color: var(--muted); }
[data-testid="stMetricValue"] { color: var(--navy); }
[data-baseweb="tab-list"] { gap: 8px; }
[data-baseweb="tab"] { color: var(--navy); }
[data-baseweb="tab-highlight"] { background-color: var(--teal); }
input:focus, textarea:focus { border-color: var(--teal) !important; }
a { color: var(--teal); }
hr { border-color: var(--line); }
</style>
""", unsafe_allow_html=True)

# Permanent local database stored beside app.py (not in Streamlit session memory).
DB_PATH = Path(__file__).resolve().parent / "procura.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            po_number TEXT PRIMARY KEY,
            supplier TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            status TEXT NOT NULL,
            order_date TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn

def load_purchases():
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT po_number, supplier, category, amount, status, order_date
            FROM purchases
            ORDER BY created_at DESC, po_number DESC
        """).fetchall()
    return pd.DataFrame(rows, columns=[
        "PO Number", "Supplier", "Category", "Amount", "Status", "Date"
    ]).assign(Date=lambda data: pd.to_datetime(data["Date"]).dt.date)

def save_purchase(po, supplier, category, amount, status, order_date):
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO purchases
                (po_number, supplier, category, amount, status, order_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (po, supplier, category, float(amount), status, order_date.isoformat()))

# Add the original sample records only once, when the database is completely empty.
# Existing database records are never overwritten on app reruns.
with get_connection() as conn:
    count = conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
    if count == 0:
        sample_rows = [
            ("PO-1001", "Tech Solutions", "Electronics", 85000, "Approved", date.today().isoformat()),
            ("PO-1002", "Office World", "Office Supplies", 12500, "Pending", date.today().isoformat()),
            ("PO-1003", "Global Systems", "Software", 54000, "Delivered", date.today().isoformat()),
            ("PO-1004", "Smart Devices", "Electronics", 32000, "Pending", date.today().isoformat()),
            ("PO-1005", "Office World", "Office Supplies", 7800, "Approved", date.today().isoformat()),
        ]
        conn.executemany("""
            INSERT INTO purchases
                (po_number, supplier, category, amount, status, order_date)
            VALUES (?, ?, ?, ?, ?, ?)
        """, sample_rows)

df = load_purchases()

with st.sidebar:
    st.markdown("# 🛍️ Procura")
    st.caption("PURCHASE INTELLIGENCE")
    st.divider()
    page = st.radio(
        "NAVIGATION",
        ["🏠 Dashboard", "📝 New Purchase", "📦 Purchase Orders", "📊 Analytics"],
        label_visibility="visible"
    )
    st.divider()
    st.markdown("### ⚡ Quick overview")
    st.caption("Manage purchase requests, suppliers and spending from one place.")
    st.markdown("---")
    st.caption("Procura v1.0 • Purchase Management")

st.markdown("""
<div class="hero">
    <h1>Purchase Management</h1>
    <p>Your intelligent workspace for purchasing, approvals and spending insights.</p>
</div>
""", unsafe_allow_html=True)

total = len(df)
spend = df["Amount"].sum() if total else 0
pending = int((df["Status"] == "Pending").sum())
delivered = int((df["Status"] == "Delivered").sum())

def metric(icon, label, value, note):
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-icon">{icon}</div>
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div style="color:#64748b;font-size:12px;margin-top:8px">{note}</div>
    </div>
    """, unsafe_allow_html=True)

if page == "🏠 Dashboard":
    st.markdown('<div class="section-title">📈 Business at a glance</div>',
                unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric("🧾", "PURCHASE ORDERS", f"{total}", "Total recorded orders")
    with c2:
        metric("💰", "TOTAL SPEND", f"₹{spend:,.0f}", "Recorded purchase value")
    with c3:
        metric("⏳", "PENDING APPROVAL", f"{pending}", "Orders awaiting action")
    with c4:
        metric("📦", "DELIVERED", f"{delivered}", "Completed deliveries")

    left, right = st.columns([1.5, 1])
    with left:
        st.markdown('<div class="section-title">💳 Spending by category</div>',
                    unsafe_allow_html=True)
        if not df.empty:
            cat = df.groupby("Category", as_index=False)["Amount"].sum()
            fig = px.bar(cat, x="Category", y="Amount", color="Category", color_discrete_sequence=["#0F766E", "#16324F", "#5B8E9B", "#94A3B8", "#C08B45"],
                         text_auto=".2s")
            fig.update_layout(
                showlegend=False, plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(l=10, r=10, t=25, b=10),
                yaxis_title="Spend (₹)", xaxis_title=""
            )
            st.plotly_chart(fig, width="stretch")

    with right:
        st.markdown('<div class="section-title">🎯 Order status</div>',
                    unsafe_allow_html=True)
        if not df.empty:
            statuses = df["Status"].value_counts().reset_index()
            statuses.columns = ["Status", "Count"]
            fig2 = px.pie(statuses, names="Status", values="Count", hole=.62)
            fig2.update_layout(
                paper_bgcolor="white", margin=dict(l=5, r=5, t=25, b=5),
                legend_title_text=""
            )
            st.plotly_chart(fig2, width="stretch")

    st.markdown('<div class="section-title">🕒 Recent purchase orders</div>',
                unsafe_allow_html=True)

    st.dataframe(df, width="stretch")

elif page == "📝 New Purchase":
    st.markdown("### ✨ Create a purchase order")
    st.caption("Enter the details below to register a new purchase.")
    with st.form("purchase_form", clear_on_submit=True):
        a, b = st.columns(2)
        with a:
            po = st.text_input("Purchase Order Number", placeholder="PO-1006")
            supplier = st.text_input("Supplier Name", placeholder="Enter supplier")
            category = st.selectbox(
                "Category",
                ["Electronics", "Office Supplies", "Software",
                 "Furniture", "Services", "Other"]
            )
        with b:
            amount = st.number_input("Amount (₹)", min_value=1.0, step=500.0)
            order_date = st.date_input("Order Date", value=date.today())
            status = st.selectbox("Status", ["Pending", "Approved", "Delivered"])
        submitted = st.form_submit_button("➕ Create Purchase Order",
                                          type="primary", width="stretch")
        if submitted:
            if not po.strip() or not supplier.strip():
                st.error("Please enter both the PO number and supplier name.")
            else:
                try:
                    save_purchase(
                        po.strip(), supplier.strip(), category,
                        amount, status, order_date
                    )
                except sqlite3.IntegrityError:
                    st.error("This purchase order number already exists.")
                except sqlite3.Error as exc:
                    st.error(f"Could not save purchase order to the database: {exc}")
                else:
                    st.success(f"Purchase order {po.strip()} saved permanently!")
                    st.rerun()

elif page == "📦 Purchase Orders":
    st.markdown("### 📦 Purchase order register")
    q1, q2 = st.columns([2, 1])
    with q1:
        search = st.text_input("🔍 Search supplier or PO number")
    with q2:
        status_filter = st.selectbox(
            "Filter by status", ["All", "Pending", "Approved", "Delivered"]
        )
    view = df.copy()
    if search:
        view = view[
            view["Supplier"].str.contains(search, case=False, na=False)
            | view["PO Number"].str.contains(search, case=False, na=False)
        ]
    if status_filter != "All":
        view = view[view["Status"] == status_filter]
    st.dataframe(view, width="stretch", hide_index=True)
    st.download_button(
        "⬇️ Export purchase orders to CSV",
        data=view.to_csv(index=False).encode("utf-8"),
        file_name="purchase_orders.csv",
        mime="text/csv"
    )

elif page == "📊 Analytics":
    st.markdown("### 📊 Purchase analytics")
    if df.empty:
        st.info("Create a purchase order to see analytics.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Average order value", f"₹{df['Amount'].mean():,.2f}")
        with c2:
            st.metric("Highest order value", f"₹{df['Amount'].max():,.2f}")
        supplier_spend = df.groupby("Supplier", as_index=False)["Amount"].sum()
        fig3 = px.bar(
            supplier_spend.sort_values("Amount", ascending=False),
            x="Supplier", y="Amount", color="Amount", color_continuous_scale=["#DDF4F0", "#0F766E", "#16324F"],
            title="Spend by supplier", text_auto=".2s"
        )
        fig3.update_layout(
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis_title="Spend (₹)", xaxis_title=""
        )
        st.plotly_chart(fig3, width="stretch")
        st.markdown("#### Category breakdown")
        st.dataframe(
            df.groupby("Category", as_index=False).agg(
                Orders=("PO Number", "count"),
                Total_Spend=("Amount", "sum")
            ),
            width="stretch", hide_index=True
        )

st.divider()
st.caption("© Procura Purchase Management • Built with Streamlit")
