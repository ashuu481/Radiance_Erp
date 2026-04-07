import sqlite3

conn = sqlite3.connect("erp.db")
cur = conn.cursor()

# Drop old table (only if empty or testing)
cur.execute("DROP TABLE IF EXISTS stock")

# New advanced stock table
cur.execute("""
CREATE TABLE stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part TEXT UNIQUE,
    qty INTEGER DEFAULT 0,
    min_qty INTEGER DEFAULT 10
)
""")

conn.commit()
conn.close()

print("Stock table upgraded")