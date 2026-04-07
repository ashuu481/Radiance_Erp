import sqlite3

conn = sqlite3.connect("erp.db")
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS inward")

cur.execute("""
CREATE TABLE inward (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part TEXT,
    qty INTEGER,
    type TEXT,
    status TEXT DEFAULT 'pending'
)
""")

conn.commit()
conn.close()

print("Inward table fixed successfully")