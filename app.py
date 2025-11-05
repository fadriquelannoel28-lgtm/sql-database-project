from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key' 

DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


if not os.path.exists(DATABASE):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    with open('sql-database-project.sql', 'r') as f:
        sql_script = f.read()
    cursor.executescript(sql_script)
    conn.commit()
    conn.close()
    print("Database created successfully from SQL file!")

@app.route('/')
def home():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/event')
def event():
    if 'username' in session:
        return render_template('event.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/report')
def report():
    if 'username' in session:
        return render_template('report.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/community')
def community():
    if 'username' in session:
        return render_template('community.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            return redirect(url_for('home'))
        else:
            error = "Invalid username or password"

    return render_template('login.html', error=error)

@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    success = None

    if request.method == 'POST':
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password != confirm:
            error = "Passwords do not match!"
        else:
            conn = get_db_connection()

            user_check = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
            if user_check:
                error = "Username already exists!"
            else:
                hashed_pw = generate_password_hash(password)
                conn.execute(
                    "INSERT INTO users (fullname, username, email, password) VALUES (?, ?, ?, ?)",
                    (fullname, username, email, hashed_pw)
                )
                conn.commit()
                success = "Registration successful! You can now log in."
            conn.close()

    return render_template('register.html', error=error, success=success)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
