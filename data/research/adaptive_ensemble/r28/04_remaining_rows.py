import json
from pathlib import Path
import psycopg2

password = Path(r"C:\R24_PostgreSQL_Test\secrets\tester.txt").read_text(encoding="ascii").strip()
conn = psycopg2.connect(host="127.0.0.1", port=55432, dbname="r24_synthetic_orders", user="r24_tester", password=password)
cur = conn.cursor()
cur.execute("SELECT symbol, client_order_id, status FROM exec_orders ORDER BY symbol, client_order_id")
rows = cur.fetchall()
cur.execute(
    "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='exec_orders' ORDER BY ordinal_position"
)
columns = [row[0] for row in cur.fetchall()]
print(json.dumps({"rows": rows, "columns": columns}))
conn.close()
