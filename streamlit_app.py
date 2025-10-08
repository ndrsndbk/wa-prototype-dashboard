import os
import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Your Customer Database", layout="wide")

# --- Centered LaTeX formula above the title ---
formula = r"""
\textbf{Community Revenue}
= (\#\ \text{of Loyal Customers} \times \text{Frequency} \times \text{AOV})
+ (\text{Referrals} \times \text{Conversion} \times \text{AOV})
"""
try:
    st.latex(formula, width="stretch")
except TypeError:
    # Fallback for Streamlit versions without the `width` parameter
    st.latex(formula)

st.title("🗂️ Your Customer Database")

# --- Config ---
def get_cfg():
    s = st.secrets.get("supabase", {})
    return {
        "url": s.get("url") or os.getenv("SUPABASE_URL", ""),
        "key": s.get("anon_key") or os.getenv("SUPABASE_KEY", ""),
        "schema": s.get("schema") or os.getenv("SUPABASE_SCHEMA", "public"),
        "table": s.get("table") or os.getenv("SUPABASE_TABLE", "customers"),
    }

cfg = get_cfg()
if not cfg["url"] or not cfg["key"]:
    st.error("Supabase URL/Key not configured. Add them to Streamlit Secrets or env vars.")
    st.stop()

client = create_client(cfg["url"], cfg["key"])
# IMPORTANT: set schema globally; do NOT pass schema= on .table()
try:
    client.postgrest.schema = cfg["schema"]
except Exception:
    pass

@st.cache_data(ttl=60)
def fetch_df(table: str) -> pd.DataFrame:
    data = client.table(table).select("customer_id, number_of_visits, last_visit_at").execute().data or []
    df = pd.DataFrame(data)
    if not df.empty:
        df["last_visit_at"] = pd.to_datetime(df["last_visit_at"], utc=True, errors="coerce")
        df["number_of_visits"] = pd.to_numeric(df.get("number_of_visits"), errors="coerce").fillna(0).astype(int)
    return df

df = fetch_df(cfg["table"])

if df.empty:
    st.info("No customer records yet. Insert data to see metrics.")
    st.stop()

# --- Helpers for periods & deltas ---
now = pd.Timestamp.utcnow()
df["days_since_last"] = (now - df["last_visit_at"]).dt.total_seconds() / 86400.0
df["days_since_last"] = df["days_since_last"].fillna(10**9)

def in_window(lo_inclusive: float, hi_inclusive: float) -> pd.Series:
    """Mask for last-visit age > lo and <= hi days ago.
       Use lo=0 for 'within the last N days' (i.e., (0, N])."""
    return (df["days_since_last"] > lo_inclusive) & (df["days_since_last"] <= hi_inclusive)

def pct_delta(curr: int, prev: int) -> str | None:
    """Percent delta for st.metric. No indicator if prev==0 or no change."""
    if prev <= 0 or curr == prev:
        return None
    change = (curr - prev) / prev * 100.0
    sign = "+" if change > 0 else "−"
    return f"{sign}{abs(change):.0f}%"

# --- Flags reused across metrics ---
new_flag = df["number_of_visits"] == 1
ret_flag = df["number_of_visits"] >= 2

# --- Period masks ---
# 30-day current window: (0, 30], previous: (30, 60]
win30_now  = in_window(0, 30)
win30_prev = in_window(30, 60)

# 7-day current window: (0, 7], previous: (7, 14]
win7_now   = in_window(0, 7)
win7_prev  = in_window(7, 14)

# --- Metrics (current + previous where relevant) ---
total_customers_all_time = len(df)

# Active = visited within the window
active_30_now  = int(win30_now.sum())
active_30_prev = int(win30_prev.sum())

# New = visit count ==1 AND visited within window
new_30_now  = int((new_flag & win30_now).sum())
new_30_prev = int((new_flag & win30_prev).sum())

# Returning = visit count >=2 AND visited within window
returning_7_now  = int((ret_flag & win7_now).sum())
returning_7_prev = int((ret_flag & win7_prev).sum())

new_7_now  = int((new_flag & win7_now).sum())
new_7_prev = int((new_flag & win7_prev).sum())

# Inactive definitions (kept as your original logic)
inactive_customers_gt_30   = int((df["days_since_last"] > 30).sum())
inactive_customers_last_30 = inactive_customers_gt_30
inactive_customers_last_7  = int((df["days_since_last"] > 7).sum())

# --- Layout & display ---
c1, c2, c3, c4 = st.columns(4)
c5, c6, c7, c8 = st.columns(4)

# Non-periodic (no delta)
with c1:
    st.metric("Total Customers (All Time)", total_customers_all_time)

# Periodic (delta vs previous matching window)
with c2:
    st.metric(
        "Active Customers (Last 30 Days)",
        active_30_now,
        delta=pct_delta(active_30_now, active_30_prev)
    )
with c3:
    st.metric(
        "New Customers (Last 30 Days)",
        new_30_now,
        delta=pct_delta(new_30_now, new_30_prev)
    )
with c4:
    st.metric(
        "Returning Customers (Last 7 Days)",
        returning_7_now,
        delta=pct_delta(returning_7_now, returning_7_prev)
    )
with c5:
    st.metric(
        "New Customers (Last 7 Days)",
        new_7_now,
        delta=pct_delta(new_7_now, new_7_prev)
    )

# Non-periodic (no delta)
with c6:
    st.metric("Inactive Customers (Haven't Visited > 30 Days)", inactive_customers_gt_30)
with c7:
    st.metric("Inactive Customers (Last 30 Days)", inactive_customers_last_30)
with c8:
    st.metric("Inactive Customers (Last 7 Days)", inactive_customers_last_7)

st.divider()
with st.expander("Preview (first 100 rows)"):
    st.dataframe(
        df[["customer_id", "number_of_visits", "last_visit_at", "days_since_last"]].head(100),
        use_container_width=True
    )
    st.caption("UTC 'now' minus 'last_visit_at'.")
