from flask import Flask, render_template, request, redirect, session, jsonify, Response
import sqlite3, os, qrcode
from datetime import datetime
import pandas as pd
import base64
import cv2
import numpy as np
import time

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

    cur.execute("""CREATE TABLE IF NOT EXISTS history(
        id INTEGER PRIMARY KEY,
        part TEXT,
        qty INTEGER,
        action TEXT,
        user TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            cur.execute(
                "INSERT INTO assembly(part, qty) VALUES (?,?)",
                (part, qty)
            )

            cur.execute(
                "INSERT INTO history(part, qty, action, user, date) VALUES (?,?,?,?,?)",
                (part, qty, "ASSEMBLY", session['user'], datetime.now())
            )

            conn.commit()

    data = cur.execute("SELECT * FROM assembly").fetchall()
    conn.close()

    return render_template("assembly.html", data=data)
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
            cur.execute(
                "INSERT INTO quality(part, status) VALUES (?,?)",
                (part, status)
            )
            conn.commit()

    data = cur.execute("SELECT * FROM quality").fetchall()
    conn.close()

    return render_template("quality.html", data=data)
# ---------------- LOGIN (ROOT FIXED) ----------------
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
            return redirect('/dashboard')

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

    parts = [r['part'] for r in rows]
    qtys = [r['qty'] for r in rows]

    return render_template("home.html", parts=parts, qtys=qtys)

# ---------------- CAMERA PAGE ----------------
@app.route('/camera')
def camera_page():
    if 'user' not in session:
        return redirect('/')
    return render_template('camera.html')

# ---------------- AI DEFECT DETECTION ----------------
os.makedirs("static/defects", exist_ok=True)

@app.route('/detect', methods=['POST'])
def detect():
    try:
        data = request.json['image']
        encoded = data.split(',')[1]

        img_bytes = base64.b64decode(encoded)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        # 🔥 Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 🔥 Blur to remove noise
        gray = cv2.GaussianBlur(gray, (5,5), 0)

        # 🔥 Improved thresholds (IMPORTANT FIX)
        _, white = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
        _, dark = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)

        # 🔥 Detect holes only inside white region
        holes = cv2.bitwise_and(white, dark)

        # 🔥 Clean noise
        kernel = np.ones((3,3), np.uint8)
        holes = cv2.morphologyEx(holes, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(holes, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        hole_count = 0

        for cnt in contours:
            area = cv2.contourArea(cnt)

            # 🔥 Reduced area threshold (VERY IMPORTANT)
            if area > 50:
                hole_count += 1
                x, y, w, h = cv2.boundingRect(cnt)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)

        # 🔥 RESULT
        if hole_count > 0:
            result = f"DEFECT ❌ ({hole_count})"

            # Save defect image
            filename = f"static/defects/defect_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)

        else:
            result = "OK ✅"

        # 🔥 Convert back to image
        _, buffer = cv2.imencode('.jpg', frame)
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        return jsonify({
            "result": result,
            "count": hole_count,
            "image": "data:image/jpeg;base64," + img_base64
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({"result": "Error", "count": 0})

# ---------------- INWARD ----------------
@app.route('/inward', methods=['GET', 'POST'])
def inward():
    if session.get('role') not in ['admin', 'inward']:
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        part = request.form['part']
        qty = int(request.form['qty'])
        t = request.form['type']

        cur.execute("INSERT INTO inward(part, qty, type) VALUES (?,?,?)", (part, qty, t))

        cur.execute("INSERT INTO history(part, qty, action, user, date) VALUES (?,?,?,?,?)",
                    (part, qty, "INWARD", session['user'], datetime.now()))

        cur.execute("SELECT qty FROM stock WHERE part=?", (part,))
        data = cur.fetchone()

        if data:
            cur.execute("UPDATE stock SET qty=qty+? WHERE part=?", (qty, part))
        else:
            cur.execute("INSERT INTO stock(part,qty) VALUES(?,?)", (part, qty))

        conn.commit()

    cur.execute("SELECT * FROM inward")
    data = cur.fetchall()
    conn.close()

    return render_template("inward.html", data=data)

# ---------------- STORE ----------------
@app.route('/store')
def store():
    if session.get('role') not in ['admin', 'store']:
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM stock")
    data = cur.fetchall()

    low = [i['part'] for i in data if i['qty'] <= i['min_qty']]

    conn.close()
    return render_template("store.html", data=data, low=low)

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

        cur.execute("INSERT INTO history(part, qty, action, user, date) VALUES (?,?,?,?,?)",
                    (part, qty, "PRODUCTION", session['user'], datetime.now()))

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
            msg = "Dispatched Successfully"
        else:
            msg = "Not enough stock"

        cur.execute("INSERT INTO history(part, qty, action, user, date) VALUES (?,?,?,?,?)",
                    (part, qty, "DISPATCH", session['user'], datetime.now()))

        conn.commit()
        conn.close()

    return render_template("dispatch.html", msg=msg)

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
    os.makedirs("static", exist_ok=True)
    img = qrcode.make(part)
    path = f"static/{part}.png"
    img.save(path)
    return f"<h3>{part}</h3><img src='/{path}'>"

# ---------------- SETTINGS ----------------
@app.route('/settings')
def settings():
    if 'user' not in session:
        return redirect('/')
    return render_template("settings.html")

# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- RUN ----------------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)