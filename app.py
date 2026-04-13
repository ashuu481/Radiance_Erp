from flask import Flask, render_template, request, redirect, session, jsonify, send_file
import sqlite3, os, qrcode
from datetime import datetime, timedelta
import pandas as pd
import base64, cv2, numpy as np, time

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DB ----------------
def get_db():
    conn = sqlite3.connect("erp.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- INIT DB ----------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS stock(
        id INTEGER PRIMARY KEY,
        part TEXT UNIQUE,
        qty INTEGER DEFAULT 0,
        min_qty INTEGER DEFAULT 10
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS inward(
        id INTEGER PRIMARY KEY,
        part TEXT,
        qty INTEGER,
        type TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS assembly(
        id INTEGER PRIMARY KEY,
        part TEXT,
        qty INTEGER
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS quality(
        id INTEGER PRIMARY KEY,
        part TEXT,
        status TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY,
        part TEXT,
        qty INTEGER,
        action TEXT,
        user TEXT,
        date TEXT
    )""")

    users = [
        ("admin", "admin", "admin"),
        ("inward", "123", "inward"),
        ("store", "123", "store"),
        ("production", "123", "production"),
        ("dispatch", "123", "dispatch")
    ]

    for u in users:
        cur.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES(?,?,?)", u)

    conn.commit()
    conn.close()

init_db()
@app.route('/assembly', methods=['GET', 'POST'])
def assembly():
    if 'user' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        part = request.form.get('part')
        qty = request.form.get('qty')

        if part and qty:
            cur.execute("INSERT INTO assembly(part, qty) VALUES (?,?)", (part, qty))
            cur.execute("INSERT INTO history(part, qty, action, user, date) VALUES (?,?,?,?,?)",
                        (part, qty, "ASSEMBLY", session['user'], str(datetime.now())))
            conn.commit()

    data = cur.execute("SELECT * FROM assembly").fetchall()
    conn.close()

    return render_template("assembly.html", data=data)
# ---------------- AI SETUP ----------------
os.makedirs("static/defects", exist_ok=True)
reference = cv2.imread("static/reference.jpg") if os.path.exists("static/reference.jpg") else None
last_saved = "OK"

# ---------------- LOGIN ----------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username=? AND password=?", (u, p))
        user = cur.fetchone()
        conn.close()

        if user:
            session['user'] = u
            session['role'] = user['role']

            role = user['role']
            if role == 'admin':
                return redirect('/dashboard')
            return redirect(f'/{role}')

    return render_template("login.html")

# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT part, qty FROM stock")
    rows = cur.fetchall()
    conn.close()

    return render_template("home.html", data=rows)

# ---------------- INWARD ----------------
@app.route('/inward', methods=['GET', 'POST'])
def inward():
    if session.get('role') not in ['admin', 'inward']:
        return "Access Denied ❌"

    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        part = request.form['part']
        qty = int(request.form['qty'])
        t = request.form['type']

        cur.execute("INSERT INTO inward(part, qty, type) VALUES (?,?,?)", (part, qty, t))

        cur.execute("INSERT INTO history VALUES (NULL,?,?,?,?,?)",
                    (part, qty, "INWARD", session['user'], str(datetime.now())))

        cur.execute("SELECT qty FROM stock WHERE part=?", (part,))
        data = cur.fetchone()

        if data:
            cur.execute("UPDATE stock SET qty=qty+? WHERE part=?", (qty, part))
        else:
            cur.execute("INSERT INTO stock(part,qty) VALUES(?,?)", (part, qty))

        conn.commit()

    data = cur.execute("SELECT * FROM inward").fetchall()
    conn.close()

    return render_template("inward.html", data=data)

# ---------------- STORE ----------------
@app.route('/store')
def store():
    if session.get('role') not in ['admin', 'store']:
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()
    data = cur.execute("SELECT * FROM stock").fetchall()
    conn.close()

    return render_template("store.html", data=data)

# ---------------- PRODUCTION ----------------
@app.route('/production', methods=['GET', 'POST'])
def production():
    if session.get('role') not in ['admin', 'production']:
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
            cur.execute("UPDATE stock SET qty=qty-? WHERE part=?", (qty, part))
            msg = "Updated"
        else:
            msg = "Not enough stock"

        cur.execute("INSERT INTO history VALUES (NULL,?,?,?,?,?)",
                    (part, qty, "PRODUCTION", session['user'], str(datetime.now())))

        conn.commit()
        conn.close()

    return render_template("production.html", msg=msg)

# ---------------- DISPATCH ----------------
@app.route('/dispatch', methods=['GET', 'POST'])
def dispatch():
    if session.get('role') not in ['admin', 'dispatch']:
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
            cur.execute("UPDATE stock SET qty=qty-? WHERE part=?", (qty, part))
            msg = "Dispatched"
        else:
            msg = "Not enough stock"

        cur.execute("INSERT INTO history VALUES (NULL,?,?,?,?,?)",
                    (part, qty, "DISPATCH", session['user'], str(datetime.now())))

        conn.commit()
        conn.close()

    return render_template("dispatch.html", msg=msg)

# ---------------- REPORTS ----------------
@app.route('/reports')
def reports():
    conn = get_db()
    cur = conn.cursor()

    filter_type = request.args.get("filter", "all")
    now = datetime.now()

    rows = cur.execute("SELECT * FROM history ORDER BY date DESC").fetchall()

    filtered = []
    for r in rows:
        try:
            ts = datetime.fromisoformat(r["date"])
        except:
            continue

        if filter_type == "today" and ts.date() != now.date():
            continue

        if filter_type == "week" and ts < now - timedelta(days=7):
            continue

        filtered.append(r)

    conn.close()
    return render_template("reports.html", data=filtered)

# ---------------- EXCEL EXPORT ----------------
@app.route('/export_excel')
def export_excel():
    conn = sqlite3.connect("erp.db")

    df = pd.read_sql("SELECT * FROM history", conn)

    df['date'] = pd.to_datetime(df['date'], format='mixed', errors='coerce')
    df = df.dropna(subset=['date'])

    file_path = "report.xlsx"
    df.to_excel(file_path, index=False)

    return send_file(file_path, as_attachment=True)

# ---------------- CAMERA ----------------
@app.route('/camera')
def camera():
    return render_template("camera.html")

# ---------------- AI DETECT ----------------
@app.route('/detect', methods=['POST'])
def detect():
    global last_saved

    try:
        data = request.json['image']
        encoded = data.split(',')[1]

        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        h, w = gray.shape
        roi = gray[int(h*0.3):int(h*0.8), int(w*0.2):int(w*0.8)]

        if np.mean(roi) > 230:
            return jsonify({"result": "NO PART ❌", "count": 0})

        _, white = cv2.threshold(roi, 190, 255, cv2.THRESH_BINARY)
        _, dark = cv2.threshold(roi, 70, 255, cv2.THRESH_BINARY_INV)

        holes = cv2.bitwise_and(white, dark)

        contours, _ = cv2.findContours(holes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        hole_count = sum(1 for c in contours if 150 < cv2.contourArea(c) < 4000)

        if hole_count > 0:
            result = "DEFECT ❌"
            if last_saved != "DEFECT":
                cv2.imwrite(f"static/defects/{time.time()}.jpg", frame)
                last_saved = "DEFECT"
        else:
            result = "OK ✅"
            last_saved = "OK"

        return jsonify({"result": result, "count": hole_count})

    except Exception as e:
        print(e)
        return jsonify({"result": "Error", "count": 0})
@app.route('/quality', methods=['GET', 'POST'])
def quality():
    if 'user' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        part = request.form.get('part')
        status = request.form.get('status')

        if part and status:
            cur.execute("INSERT INTO quality(part, status) VALUES (?,?)", (part, status))
            cur.execute("INSERT INTO history(part, qty, action, user, date) VALUES (?,?,?,?,?)",
                        (part, 0, f"QUALITY-{status}", session['user'], str(datetime.now())))
            conn.commit()

    data = cur.execute("SELECT * FROM quality").fetchall()
    conn.close()

    return render_template("quality.html", data=data)
# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)