import os
import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Your Customer Database", layout="wide")
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

now = pd.Timestamp.utcnow()
df["days_since_last"] = (now - df["last_visit_at"]).dt.total_seconds() / 86400.0
df["days_since_last"] = df["days_since_last"].fillna(10**9)

last_7d  = df["days_since_last"] <= 7
last_30d = df["days_since_last"] <= 30
new_flag = df["number_of_visits"] == 1
ret_flag = df["number_of_visits"] >= 2
inactive_7  = df["days_since_last"] > 7
inactive_30 = df["days_since_last"] > 30

total_customers_all_time     = len(df)
active_customers_last_30     = int(last_30d.sum())
new_customers_last_30        = int((new_flag & last_30d).sum())
returning_customers_last_7   = int((ret_flag & last_7d).sum())
new_customers_last_7         = int((new_flag & last_7d).sum())
inactive_customers_gt_30     = int(inactive_30.sum())
inactive_customers_last_30   = inactive_customers_gt_30
inactive_customers_last_7    = int(inactive_7.sum())

c1, c2, c3, c4 = st.columns(4)
c5, c6, c7, c8 = st.columns(4)
with c1: st.metric("Total Customers (All Time)", total_customers_all_time)
with c2: st.metric("Active Customers (Last 30 Days)", active_customers_last_30)
with c3: st.metric("New Customers (Last 30 Days)", new_customers_last_30)
with c4: st.metric("Returning Customers (Last 7 Days)", returning_customers_last_7)
with c5: st.metric("New Customers (Last 7 Days)", new_customers_last_7)
with c6: st.metric("Inactive Customers (Haven't Visited > 30 Days)", inactive_customers_gt_30)
with c7: st.metric("Inactive Customers (Last 30 Days)", inactive_customers_last_30)
with c8: st.metric("Inactive Customers (Last 7 Days)", inactive_customers_last_7)

st.divider()
with st.expander("Preview (first 100 rows)"):
    st.dataframe(df[["customer_id","number_of_visits","last_visit_at","days_since_last"]].head(100), use_container_width=True)
    st.caption("UTC 'now' minus 'last_visit_at'.")
