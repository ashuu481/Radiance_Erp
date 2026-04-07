from flask import Flask, render_template, request, redirect, session
import sqlite3, os, qrcode

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DB ----------------
def get_db():
    conn = sqlite3.connect("erp.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- INIT ----------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS inward(
    id INTEGER PRIMARY KEY, part TEXT, qty INTEGER, type TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS stock(
    id INTEGER PRIMARY KEY, part TEXT UNIQUE, qty INTEGER DEFAULT 0, min_qty INTEGER DEFAULT 10)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS history(
    id INTEGER PRIMARY KEY, part TEXT, qty INTEGER, action TEXT, user TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")

    users = [
        ("admin","admin","admin"),
        ("inward","123","inward"),
        ("store","123","store"),
        ("production","123","production"),
        ("dispatch","123","dispatch")
    ]

    for u in users:
        cur.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES(?,?,?)", u)

    conn.commit()
    conn.close()

init_db()

# ---------------- LOGIN ----------------
@app.route('/', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username=? AND password=?", (u,p))
        user = cur.fetchone()
        conn.close()

        if user:
            session['user'] = u
            session['role'] = user['role']
            return redirect('/dashboard')

    return render_template("login.html")

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    return render_template("home.html")

# ---------------- INWARD ----------------
@app.route('/inward', methods=['GET','POST'])
def inward():
    if session.get('role') not in ['admin','inward']:
        return "Access Denied"

    part = request.args.get('part','')

    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        part = request.form['part']
        qty = int(request.form['qty'])
        t = request.form['type']

        cur.execute("INSERT INTO inward(part,qty,type) VALUES(?,?,?)",(part,qty,t))

        cur.execute("SELECT qty FROM stock WHERE part=?", (part,))
        data = cur.fetchone()

        if data:
            cur.execute("UPDATE stock SET qty=qty+? WHERE part=?", (qty,part))
        else:
            cur.execute("INSERT INTO stock(part,qty) VALUES(?,?)",(part,qty))

        cur.execute("INSERT INTO history(part,qty,action,user) VALUES(?,?,?,?)",
                    (part,qty,"INWARD",session['user']))

        conn.commit()

    cur.execute("SELECT * FROM inward")
    data = cur.fetchall()
    conn.close()

    return render_template("inward.html", data=data, part=part)

# ---------------- STORE ----------------
@app.route('/store')
def store():
    if session.get('role') not in ['admin','store']:
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM stock")
    data = cur.fetchall()

    low = [i['part'] for i in data if i['qty'] <= i['min_qty']]

    conn.close()

    return render_template("store.html", data=data, low=low)

# ---------------- PRODUCTION ----------------
@app.route('/production', methods=['GET','POST'])
def production():
    if session.get('role') not in ['admin','production']:
        return "Access Denied"

    msg = ""
    if request.method == 'POST':
        part = request.form['part']
        qty = int(request.form['qty'])

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT qty FROM stock WHERE part=?", (part,))
        s = cur.fetchone()

        if s and s['qty'] >= qty:
            cur.execute("UPDATE stock SET qty=qty-? WHERE part=?", (qty,part))
            cur.execute("INSERT INTO history(part,qty,action,user) VALUES(?,?,?,?)",
                        (part,qty,"PRODUCTION",session['user']))
            msg = "Updated"
        else:
            msg = "Not enough stock"

        conn.commit()
        conn.close()

    return render_template("production.html", msg=msg)

# ---------------- HISTORY ----------------
@app.route('/history')
def history():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM history ORDER BY date DESC")
    data = cur.fetchall()
    conn.close()
    return render_template("history.html", data=data)

# ---------------- QR ----------------
@app.route('/qr/<part>')
def qr(part):
    if not os.path.exists("static"):
        os.makedirs("static")
    img = qrcode.make(part)
    path = f"static/{part}.png"
    img.save(path)
    return f"<h3>{part}</h3><img src='/{path}'>"

# ---------------- SCAN ----------------
@app.route('/scan')
def scan():
    return render_template("scan.html")

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- RUN ----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT",10000))
    app.run(host='0.0.0.0', port=port)