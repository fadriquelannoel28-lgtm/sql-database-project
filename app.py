from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key' 

DATABASE = 'database.db'

def parse_event_datetime(dt_str):
    try:
        return datetime.fromisoformat(dt_str)
    except ValueError:
        return datetime.strptime(dt_str, "%b %d, %Y - %I:%M %p")

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


conn = get_db_connection()

admin_check = conn.execute("SELECT * FROM users WHERE username='admin'").fetchone()
if not admin_check:
    hashed_password = generate_password_hash("1234")
    conn.execute(
        "INSERT INTO users (fullname, username, email, password) VALUES (?, ?, ?, ?)",
        ("Administrator", "admin", "admin@example.com", hashed_password)
    )
    conn.commit()
    print("Admin user created successfully!")
else:
    print("Admin already exists.")

conn.close()


@app.route('/')
def home():
    if 'username' in session:
        return render_template('index.html', username=session['username'])
    return redirect(url_for('login'))



@app.route('/event')
def event():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    conn = get_db_connection()
    events = conn.execute("SELECT * FROM events ORDER BY id DESC").fetchall()

    events_with_joined = []
    edit_trash_event_id = session.get('edit_trash_event') 

    for e in events:
        joined = conn.execute(
            "SELECT 1 FROM event_participants WHERE event_id=? AND username=?",
            (e['id'], username)
        ).fetchone() is not None

        count = conn.execute(
            "SELECT COUNT(*) AS count FROM event_participants WHERE event_id=?",
            (e['id'],)
        ).fetchone()['count']

        event_time = parse_event_datetime(e['datetime'])
        status = e['status']

        if count == 0 and datetime.now() >= event_time and status != 'Terminated':
            conn.execute("UPDATE events SET status='Terminated' WHERE id=?", (e['id'],))
            conn.commit()
            status = 'Terminated'

        first_participant = conn.execute(
            "SELECT username FROM event_participants WHERE event_id=? ORDER BY id ASC LIMIT 1",
            (e['id'],)
        ).fetchone()

        holder = e['created_by']  
        if conn.execute("SELECT 1 FROM event_participants WHERE event_id=? AND username=?",
                        (e['id'], e['created_by'])).fetchone():
            holder = e['created_by']
        elif first_participant:
            holder = first_participant['username']

        holder = holder.strip() if holder else e['created_by']
        if not e['holder_name'] or e['holder_name'].strip() != holder:
            conn.execute("UPDATE events SET holder_name=? WHERE id=?", (holder, e['id']))
            conn.commit()

        e_dict = dict(e)
        e_dict['joined'] = joined
        e_dict['participants'] = count
        e_dict['max_participants'] = e['max_participants']
        e_dict['is_editing'] = (edit_trash_event_id == e['id'])
        e_dict['holder'] = holder
        e_dict['status'] = status
        e_dict['readable_time'] = event_time.strftime("%b %d, %Y - %I:%M %p")

        events_with_joined.append(e_dict)

    conn.close()
    session.pop('edit_trash_event', None)

    return render_template('event.html', username=username, events=events_with_joined)

@app.route('/join/<int:event_id>', methods=['POST'])
def join_event(event_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    conn = get_db_connection()

    already_joined = conn.execute(
        "SELECT * FROM event_participants WHERE event_id=? AND username=?",
        (event_id, username)
    ).fetchone()

    if not already_joined:
        participants = conn.execute(
            "SELECT COUNT(*) AS count FROM event_participants WHERE event_id=?",
            (event_id,)
        ).fetchone()['count']

        max_participants = conn.execute(
            "SELECT max_participants FROM events WHERE id=?",
            (event_id,)
        ).fetchone()['max_participants']

        if participants < max_participants:
            conn.execute(
                "INSERT INTO event_participants (event_id, username) VALUES (?, ?)",
                (event_id, username)
            )

            current_holder = conn.execute(
                "SELECT holder_name FROM events WHERE id=?",
                (event_id,)
            ).fetchone()['holder_name']

            if not current_holder:
                conn.execute(
                    "UPDATE events SET holder_name=? WHERE id=?",
                    (username, event_id)
                )

            conn.commit()

    conn.close()
    return redirect(url_for('event'))


@app.route('/leave/<int:event_id>', methods=['POST'])
def leave_event(event_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM event_participants WHERE event_id=? AND username=?",
        (event_id, username)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('event'))

@app.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    conn = get_db_connection()

    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if event and (event['created_by'] == username or username == 'admin' or event['holder_name'] == username):
        conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
        conn.execute("DELETE FROM event_participants WHERE event_id = ?", (event_id,))
        conn.commit()

    conn.close()
    return redirect(url_for('event'))

@app.route('/refresh_events', methods=['POST'])
def refresh_events():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    events = conn.execute("SELECT * FROM events WHERE status = 'Pending'").fetchall()
    now = datetime.now()

    for event in events:
        event_time = parse_event_datetime(event['datetime'])

        count = conn.execute(
            "SELECT COUNT(*) AS count FROM event_participants WHERE event_id=?",
            (event['id'],)
        ).fetchone()['count']

        if now >= event_time:
            if count == 0:
                conn.execute("UPDATE events SET status = 'Terminated' WHERE id = ?", (event['id'],))
            else:
                conn.execute("UPDATE events SET status = 'In Progress' WHERE id = ?", (event['id'],))

    conn.commit()
    conn.close()
    
    return redirect(url_for('event'))

@app.route('/clear_event/<int:event_id>', methods=['POST'])
def clear_event(event_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    conn = get_db_connection()
    
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    
    if event and (username == event['holder_name'] or username == 'admin'):
        participant_count = conn.execute(
            "SELECT COUNT(*) AS count FROM event_participants WHERE event_id=?",
            (event_id,)
        ).fetchone()['count']
        
        if participant_count == 0:
            conn.execute("UPDATE events SET status = 'Terminated' WHERE id = ?", (event_id,))
        else:
            conn.execute("UPDATE events SET status = 'Resolved' WHERE id = ?", (event_id,))
        
        conn.commit()

    conn.close()
    return redirect(url_for('event'))

@app.route('/submit_trash/<int:event_id>', methods=['POST'])
def submit_trash(event_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()

    holder = event['holder_name']
    if not (session['username'] == holder or session['username'] == event['created_by'] or session['username'] == 'admin'):
        conn.close()
        return "You are not allowed to submit or edit trash for this event.", 403

    collected_trash = request.form.get('collected_trash', 0)
    try:
        collected_trash = float(collected_trash)  
    except ValueError:
        collected_trash = 0

    conn.execute(
        "UPDATE events SET collected_trash = ? WHERE id = ?",
        (collected_trash, event_id)
    )
    conn.commit()
    conn.close()
    return redirect(url_for('event'))

@app.route('/edit_trash/<int:event_id>', methods=['POST'])
def edit_trash(event_id):
    
    conn = get_db_connection()
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    conn.close()

   
    session['edit_trash_event'] = event_id  
    return redirect(url_for('event')) 


MAX_PARTICIPANTS = 50

@app.route('/report', methods=['GET', 'POST'])
def report():
    if 'username' not in session:
        return redirect(url_for('login'))

    error = None
    success = None
    min_date = datetime.now().strftime("%Y-%m-%dT%H:%M")  

    if request.method == 'POST':
        event_name = request.form.get('event_name')
        location = request.form.get('location')
        description = request.form.get('description')
        datetime_input = request.form.get('datetime')  
        image = request.files.get('image')

        if datetime_input < min_date:
            error = "You cannot select a past date!"
        else:
            image_filename = None
            if image and image.filename != '':
                upload_dir = "static/uploads"
                os.makedirs(upload_dir, exist_ok=True)
                image_filename = os.path.join(upload_dir, image.filename)
                image.save(image_filename)

            max_participants_input = request.form.get('participants')
            max_participants = int(max_participants_input) if max_participants_input else 50

            event_datetime = datetime.strptime(datetime_input, "%Y-%m-%dT%H:%M")

            conn = get_db_connection()
            conn.execute(
                "INSERT INTO events (event_name, location, description, datetime, participants, max_participants, image, created_by, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_name,
                    location,
                    description,
                    event_datetime.isoformat(),
                    0,  
                    max_participants,
                    image_filename,
                    session['username'],
                    'Pending'  
                )
            )
            conn.commit()
            conn.close()
            success = f"Event '{event_name}' created successfully!"

    return render_template(
        'report.html',
        error=error,
        success=success,
        username=session['username'],
        min_date=min_date
    )

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
