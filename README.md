# Your Customer Database (Streamlit × Supabase)

Expected columns:
- customer_id (text)
- number_of_visits (int)
- last_visit_at (timestamptz)

Config with `.streamlit/secrets.toml`:
[supabase]
url = "https://YOUR-PROJECT.supabase.co"
anon_key = "YOUR_KEY"
schema = "public"
table = "customers"
