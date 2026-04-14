from flask import Flask, render_template, request, redirect, session, jsonify, send_file
import psycopg2
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sqlite3
app = Flask(__name__)
app.secret_key = "super_secret_key"

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("erp.db", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- INIT DB ----------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS stock(
        id SERIAL PRIMARY KEY,
        part TEXT UNIQUE,
        qty INTEGER DEFAULT 0,
        min_qty INTEGER DEFAULT 10
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS inward(
        id SERIAL PRIMARY KEY,
        part TEXT,
        qty INTEGER,
        type TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS assembly(
        id SERIAL PRIMARY KEY,
        part TEXT,
        qty INTEGER
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS quality(
        id SERIAL PRIMARY KEY,
        part TEXT,
        status TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS history(
        id SERIAL PRIMARY KEY,
        part TEXT,
        qty INTEGER,
        action TEXT,
        username TEXT,
        date TIMESTAMP
    )""")

    users = [
        ("admin", generate_password_hash("admin123"), "admin"),
        ("inward", generate_password_hash("123"), "inward"),
        ("store", generate_password_hash("123"), "store"),
        ("production", generate_password_hash("123"), "production"),
        ("dispatch", generate_password_hash("123"), "dispatch")
    ]

    for u in users:
       cur.execute("""
INSERT OR IGNORE INTO users(username,password,role)
VALUES(?,?,?)
""", u)

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

        cur.execute("SELECT * FROM users WHERE username=?", (u,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[2], p):
            session['user'] = user[1]
            session['role'] = user[3]

            if user[3] == 'admin':
                return redirect('/dashboard')
            elif user[3] == 'inward':
                return redirect('/inward')
            elif user[3] == 'store':
                return redirect('/store')
            elif user[3] == 'production':
                return redirect('/production')
            elif user[3] == 'dispatch':
                return redirect('/dispatch')

        return render_template("login.html", error="Invalid Credentials")

    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT part, qty FROM stock")
    data = cur.fetchall()
    conn.close()

    return render_template("home.html", data=data)


# ---------------- INWARD ----------------
@app.route('/inward', methods=['GET','POST'])
def inward():
    if session.get('role') not in ['admin','inward']:
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        part = request.form['part']
        qty = int(request.form['qty'])

        cur.execute("INSERT INTO inward(part,qty,type) VALUES(?,?,?)",
                    (part,qty,"INWARD"))

        cur.execute("""
        INSERT INTO history(part,qty,action,username,date)
        VALUES(?,?,?,?,?)
        """,(part,qty,"INWARD",session['user'],str(datetime.now())))

        cur.execute("SELECT qty FROM stock WHERE part=?",(part,))
        row = cur.fetchone()

        if row:
            cur.execute("UPDATE stock SET qty=qty+? WHERE part=?",(qty,part))
        else:
            cur.execute("INSERT INTO stock(part,qty) VALUES(?,?)",(part,qty))

        conn.commit()

    cur.execute("SELECT * FROM inward")
    data = cur.fetchall()
    conn.close()

    return render_template("inward.html", data=data)


# ---------------- STORE ----------------
@app.route('/store')
def store():
    if session.get('role') not in ['admin','store']:
        return "Access Denied"

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM stock")
    data = cur.fetchall()
    conn.close()

    return render_template("store.html", data=data)


# ---------------- PRODUCTION ----------------
@app.route('/production', methods=['GET','POST'])
def production():
    if session.get('role') not in ['admin','production']:
        return "Access Denied"

    msg=""

    if request.method == 'POST':
        part = request.form['part']
        qty = int(request.form['qty'])

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT qty FROM stock WHERE part=?",(part,))
        s = cur.fetchone()

        if s and s[0] >= qty:
            cur.execute("UPDATE stock SET qty=qty-? WHERE part=?",(qty,part))
            msg="Updated"
        else:
            msg="Not enough stock"

        cur.execute("""
        INSERT INTO history(part,qty,action,username,date)
        VALUES(?,?,?,?,?)
        """,(part,qty,"PRODUCTION",session['user'],str(datetime.now())))

        conn.commit()
        conn.close()

    return render_template("production.html", msg=msg)


# ---------------- ASSEMBLY ----------------
@app.route('/assembly', methods=['GET','POST'])
def assembly():
    if 'user' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        part = request.form['part']
        qty = request.form['qty']

        cur.execute("INSERT INTO assembly(part,qty) VALUES(?,?)",(part,qty))

        cur.execute("""
        INSERT INTO history(part,qty,action,username,date)
        VALUES(?,?,?,?,?)
        """,(part,qty,"ASSEMBLY",session['user'],str(datetime.now())))

        conn.commit()

    cur.execute("SELECT * FROM assembly")
    data = cur.fetchall()
    conn.close()

    return render_template("assembly.html", data=data)


# ---------------- QUALITY ----------------
@app.route('/quality', methods=['GET','POST'])
def quality():
    if 'user' not in session:
        return redirect('/')

    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        part = request.form['part']
        status = request.form['status']

        cur.execute("INSERT INTO quality(part,status) VALUES(?,?)",(part,status))

        cur.execute("""
        INSERT INTO history(part,qty,action,username,date)
        VALUES(?,?,?,?,?)
        """,(part,0,f"QUALITY-{status}",session['user'],str(datetime.now())))

        conn.commit()

    cur.execute("SELECT * FROM quality")
    data = cur.fetchall()
    conn.close()

    return render_template("quality.html", data=data)


# ---------------- DISPATCH ----------------
@app.route('/dispatch', methods=['GET','POST'])
def dispatch():
    if session.get('role') not in ['admin','dispatch']:
        return "Access Denied"

    msg=""

    if request.method == 'POST':
        part = request.form['part']
        qty = int(request.form['qty'])

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT qty FROM stock WHERE part=?",(part,))
        s = cur.fetchone()

        if s and s[0] >= qty:
            cur.execute("UPDATE stock SET qty=qty-? WHERE part=?",(qty,part))
            msg="Dispatched"
        else:
            msg="Not enough stock"

        cur.execute("""
        INSERT INTO history(part,qty,action,username,date)
        VALUES(?,?,?,?,?)
        """,(part,qty,"DISPATCH",session['user'],str(datetime.now())))

        conn.commit()
        conn.close()

    return render_template("dispatch.html", msg=msg)


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)