import sqlite3

conn = sqlite3.connect("erp.db")
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS stock_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part TEXT,
    qty INTEGER,
    action TEXT,
    user TEXT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()

print("Stock history ready")