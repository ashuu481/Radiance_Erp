from flask import Flask, render_template, request, redirect, session
import sqlite3
import qrcode
import pandas as pd
app = Flask(__name__)
app.secret_key = "erp_secret_key"
import os
print("Page Loaded")
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
@app.route('/')
def home():
    return redirect('/login')
@app.route('/scan')
def scan():
    return render_template("scan.html")
@app.route('/generate_qr/<part>')
def generate_qr(part):
    if not os.path.exists("static"):
        os.makedirs("static")

    img = qrcode.make(part)
    path = f"static/{part}.png"
    img.save(path)

    return f"<h3>QR for {part}</h3><img src='/{path}'>"
import pandas as pd

@app.route('/export')
def export():
    conn = sqlite3.connect("erp.db")
    df = pd.read_sql_query("SELECT * FROM stock", conn)
    conn.close()

    file = "stock.xlsx"
    df.to_excel(file, index=False)

    return f"Exported: {file}"
@app.route('/import', methods=['GET','POST'])
def import_excel():
    if request.method == 'POST':
        file = request.files['file']

        df = pd.read_excel(file)

        conn = sqlite3.connect("erp.db")
        df.to_sql('stock', conn, if_exists='replace', index=False)
        conn.close()

        return "Imported Successfully"

    return '''
    <form method="post" enctype="multipart/form-data">
    <input type="file" name="file">
    <button>Upload</button>
    </form>
    '''

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("erp.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
   

# ---------------- INIT DB ----------------
def init_db():
    conn = get_db()
    cur = conn.cursor()
    init_db()
    # USERS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # INWARD
    cur.execute("""
    CREATE TABLE IF NOT EXISTS inward (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part TEXT,
        qty INTEGER,
        type TEXT,
        status TEXT DEFAULT 'pending'
    )
    """)

    # STOCK
    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part TEXT UNIQUE,
        qty INTEGER DEFAULT 0,
        min_qty INTEGER DEFAULT 10
    )
    """)

    # DISPATCH
    cur.execute("""
    CREATE TABLE IF NOT EXISTS dispatch (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part TEXT,
        qty INTEGER,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # STOCK HISTORY
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

    # DEFAULT USERS
    users = [
        ("admin", "admin", "admin"),
        ("inward", "123", "inward"),
        ("store", "123", "store"),
        ("production", "123", "production"),
        ("dispatch", "123", "dispatch")
    ]

    for u in users:
        cur.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES (?, ?, ?)", u)

    conn.commit()
    conn.close()

init_db()

# ---------------- LOGIN ----------------
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()
        conn.close()

        if user:
            session['user'] = username
            session['role'] = user['role']
            return redirect('/dashboard')
        else:
            return "Invalid Login ❌"

    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/login')

    return render_template("home.html")


# ---------------- INWARD ----------------
@app.route('/inward', methods=['GET', 'POST'])
def inward():
    if session.get('role') not in ['admin', 'inward']:
        return "Access Denied ❌"

    conn = get_db()
    cur = conn.cursor()

    # ✅ ALWAYS define part safely
    part = request.args.get('part', '')  # from QR
    qty = ''
    mat_type = ''

    if request.method == 'POST':
        part = request.form['part']
        qty = int(request.form['qty'])
        mat_type = request.form['type']

        # insert inward
        cur.execute("INSERT INTO inward (part, qty, type) VALUES (?, ?, ?)",
                    (part, qty, mat_type))

        # update stock
        cur.execute("SELECT qty FROM stock WHERE part=?", (part,))
        existing = cur.fetchone()

        if existing:
            cur.execute("UPDATE stock SET qty = qty + ? WHERE part=?", (qty, part))
        else:
            cur.execute("INSERT INTO stock (part, qty) VALUES (?, ?)", (part, qty))

        # history
        cur.execute("""
        INSERT INTO stock_history (part, qty, action, user)
        VALUES (?, ?, 'INWARD', ?)
        """, (part, qty, session['user']))

        conn.commit()

    cur.execute("SELECT * FROM inward")
    data = cur.fetchall()
    conn.close()

    return render_template("inward.html", data=data, part=part)


# ---------------- STORE ----------------
@app.route('/store')
def store():
    if session.get('role') not in ['admin', 'store']:
        return "Access Denied ❌"

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM stock")
    data = cur.fetchall()

    # LOW STOCK ALERT
    low_stock = [i['part'] for i in data if i['qty'] <= i['min_qty']]

    conn.close()

    return render_template("store.html", data=data, low_stock=low_stock)


# ---------------- PRODUCTION ----------------
@app.route('/production', methods=['GET', 'POST'])
def production():
    if session.get('role') not in ['admin', 'production']:
        return "Access Denied ❌"

    message = ""

    if request.method == 'POST':
        part = request.form['part']
        qty = int(request.form['qty'])

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT qty FROM stock WHERE part=?", (part,))
        stock = cur.fetchone()

        if stock and stock['qty'] >= qty:
            cur.execute("UPDATE stock SET qty = qty - ? WHERE part=?", (qty, part))

            cur.execute("""
            INSERT INTO stock_history (part, qty, action, user)
            VALUES (?, ?, 'PRODUCTION', ?)
            """, (part, qty, session['user']))

            message = "Production Updated ✅"
        else:
            message = "Not enough stock ❌"

        conn.commit()
        conn.close()

    return render_template("production.html", message=message)


# ---------------- DISPATCH ----------------
@app.route('/dispatch', methods=['GET', 'POST'])
def dispatch():
    if session.get('role') not in ['admin', 'dispatch']:
        return "Access Denied ❌"

    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        part = request.form['part']
        qty = int(request.form['qty'])

        cur.execute("INSERT INTO dispatch (part, qty) VALUES (?, ?)", (part, qty))
        conn.commit()

    cur.execute("SELECT * FROM dispatch")
    data = cur.fetchall()
    conn.close()

    return render_template("dispatch.html", data=data)


# ---------------- HISTORY ----------------
@app.route('/history')
def history():
    if session.get('role') not in ['admin', 'store']:
        return "Access Denied ❌"

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM stock_history ORDER BY date DESC")
    data = cur.fetchall()

    conn.close()

    return render_template("history.html", data=data)


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)