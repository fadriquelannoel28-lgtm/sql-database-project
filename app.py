from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # for session management

DATABASE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Create database and tables if not exist
if not os.path.exists(DATABASE):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    with open('sql-database-project.sql', 'r') as f:
        sql_script = f.read()
    cursor.executescript(sql_script)
    conn.commit()
    conn.close()
    print("Database and tables created successfully!")

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?", 
            (username, password)
        ).fetchone()
        conn.close()

        if user:
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

        # Check if passwords match
        if password != confirm:
            error = "Passwords do not match!"
            return render_template('register.html', error=error)

        conn = get_db_connection()

        # Check if username exists
        user_check = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user_check:
            error = "Username already exists!"
            conn.close()
            return render_template('register.html', error=error)

        # Insert new user
        conn.execute(
            "INSERT INTO users (fullname, username, email, password) VALUES (?, ?, ?, ?)",
            (fullname, username, email, password)
        )
        conn.commit()
        conn.close()

        success = "Registration successful! You can now log in."
        return render_template('register.html', success=success)

    return render_template('register.html')

@app.route('/')
def home():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('username', None)
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

if __name__ == '__main__':
    app.run(debug=True)
