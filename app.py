# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length, Email, EqualTo

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from functools import wraps
from dateutil import parser
import os

from forms import LoginForm, RegisterForm, EventForm, CommunityForm
from models import Base, User, Event, EventParticipant, CommunityPost

app = Flask(__name__)
app.secret_key = 'water-cleaning-operation'

engine = create_engine('sqlite:///database.db', echo=True)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# ---------------------------------------------------------------------------------------------allowed pictures
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --------------------------------------------------------- required login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Please log in first.")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------------------------------------------------------------------------------------index/home
@app.route('/')
def index():
    return render_template('index.html')

# ---------------------------------------------------------------------------------------------Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit(): 
        username = form.username.data
        password = form.password.data

        db_session = Session()
        user = db_session.query(User).filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['username'] = user.username
            flash(f"Welcome, {username}!")
            db_session.close()
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password")
            db_session.close()
            return redirect(url_for('login'))

    return render_template('login.html', form=form)

# ----------------------------------------------------------------------------------------------register
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()

    if form.validate_on_submit(): 
        fullname = form.fullname.data
        username = form.username.data
        email = form.email.data
        password = form.password.data
        confirm_password = form.confirm_password.data

        if password != confirm_password:
            flash("Passwords do not match!")
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        db_session = Session()

        if db_session.query(User).filter_by(username=username).first():
            flash("Username already exists.")
            return redirect(url_for('register'))

        new_user = User(
            fullname=fullname,
            username=username,
            email=email,
            password=hashed_password
        )
        db_session.add(new_user)
        db_session.commit()
        flash("Registration successful! Please log in.")
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

# ----------------------------------------------------------------------------------------------logout
@app.route('/logout')
@login_required
def logout():
    username = session.pop('username', None)
    flash(f"Goodbye, {username}! You have been logged out.")
    return redirect(url_for('login'))

# ----------------------------------------------------------------------------------------------home
@app.route('/home')
@login_required
def home():
    return render_template('index.html', username=session['username'])

# ----------------------------------------------------------------------------------------------events
@app.route('/home/event')
def event():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    db_session = Session()

    events = db_session.query(Event).order_by(Event.id.desc()).all()
    events_with_joined = []
    edit_trash_event_id = session.get('edit_trash_event')

    for e in events:
        joined = db_session.query(EventParticipant).filter_by(event_id=e.id, username=username).first() is not None

        count = db_session.query(EventParticipant).filter_by(event_id=e.id).count()

        try:
            event_time = parser.parse(e.datetime)
        except Exception:
            event_time = datetime.strptime(e.datetime, "%Y-%m-%d %H:%M")

        status = e.status

        if count == 0 and datetime.now() >= event_time and status != 'Terminated':
            e.status = 'Terminated'
            db_session.commit()
            status = 'Terminated'

        first_participant = db_session.query(EventParticipant).filter_by(event_id=e.id).order_by(EventParticipant.id.asc()).first()
        holder = e.created_by
        if db_session.query(EventParticipant).filter_by(event_id=e.id, username=e.created_by).first():
            holder = e.created_by
        elif first_participant:
            holder = first_participant.username

        holder = holder.strip() if holder else e.created_by
        if not e.holder_name or e.holder_name.strip() != holder:
            e.holder_name = holder
            db_session.commit()

        e_dict = {
            'id': e.id,
            'event_name': e.event_name,
            'location': e.location,
            'description': e.description,
            'datetime': e.datetime,
            'participants': count,
            'max_participants': e.max_participants,
            'joined': joined,
            'is_editing': (edit_trash_event_id == e.id),
            'holder': holder,
            'status': status,
            'readable_time': event_time.strftime("%b %d, %Y - %I:%M %p"), 
            'image': e.image,
            'collected_trash': e.collected_trash
        }

        events_with_joined.append(e_dict)

    session.pop('edit_trash_event', None)
    db_session.close()

    return render_template('event.html', username=username, events=events_with_joined)

# ----------------------------------------------------------------------------------------------refresh
@app.route('/refresh_events', methods=['POST'])
@login_required
def refresh_events():
    db_session = Session()
    username = session['username']
    now = datetime.now()


    events = db_session.query(Event).filter_by(status='Pending').all()

    for event in events:
        event_time = parser.parse(event.datetime)  

        
        count = db_session.query(EventParticipant).filter_by(event_id=event.id).count()

      
        if now >= event_time:
            if count == 0:
                event.status = 'Terminated'
            else:
                event.status = 'In Progress'

    db_session.commit()
    db_session.close()

    return redirect(url_for('event'))

# ----------------------------------------------------------------------------------------------report
@app.route('/home/report', methods=['GET', 'POST'])
@login_required
def report():
    error = None
    success = None
    min_date = datetime.now()

    form = EventForm()

    if form.validate_on_submit():
        event_name = form.event_name.data
        location = form.location.data
        description = form.description.data
        event_datetime = form.datetime.data
        image = form.image.data

        if event_datetime < min_date:
            error = "You cannot select a past date!"
        else:
            max_participants = form.participants.data or 50

            db_session = Session()
            new_event = Event(
                event_name=event_name,
                location=location,
                description=description,
                datetime=event_datetime.isoformat(),
                participants=0,
                max_participants=max_participants,
                image=None,
                created_by=session['username'],
                status='Pending'
            )
            db_session.add(new_event)
            db_session.commit()

            if image and image.filename != '':
                upload_dir = "static/uploads"
                os.makedirs(upload_dir, exist_ok=True)

                dt_str = event_datetime.strftime("%Y%m%d-%H%M")
                creator_name = session['username'].replace(" ", "_")
                ext = os.path.splitext(image.filename)[1]
                filename = f"id-{new_event.id}-creator-{creator_name}-datetime-{dt_str}{ext}"

                image.save(os.path.join(upload_dir, filename))
                new_event.image = f"/static/uploads/{filename}"
                db_session.commit()

            db_session.close()
            success = f"Event '{event_name}' created successfully!"

    return render_template(
        'report.html',
        form=form,
        error=error,
        success=success,
        min_date=min_date.strftime("%Y-%m-%dT%H:%M")
    )

# ----------------------------------------------------------------------------------------------delete
@app.route('/delete_event/<int:event_id>', methods=['POST'])
def delete_event(event_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    db_session = Session()

    event = db_session.query(Event).filter_by(id=event_id).first()

    if not event:
        db_session.close()
        return redirect(url_for('event'))

    allowed = (
        event.created_by == username or
        username == 'admin' or
        event.holder_name == username
    )

    if allowed:
        db_session.query(EventParticipant).filter_by(event_id=event_id).delete()

        db_session.delete(event)
        db_session.commit()

    db_session.close()
    return redirect(url_for('event'))


# ----------------------------------------------------------------------------------------------join
@app.route('/join/<int:event_id>', methods=['POST'])
def join_event(event_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    db_session = Session()

    event = db_session.query(Event).filter_by(id=event_id).first()
    if not event:
        db_session.close()
        return redirect(url_for('event'))

    already_joined = (
        db_session.query(EventParticipant)
        .filter_by(event_id=event_id, username=username)
        .first()
        is not None
    )

    if not already_joined:
        participants = (
            db_session.query(EventParticipant)
            .filter_by(event_id=event_id)
            .count()
        )

      
        if participants < event.max_participants:
            join_entry = EventParticipant(event_id=event_id, username=username)
            db_session.add(join_entry)

          
            if not event.holder_name or event.holder_name.strip() == "":
                event.holder_name = username

            db_session.commit()

    db_session.close()
    return redirect(url_for('event'))


# ----------------------------------------------------------------------------------------------leave
@app.route('/leave/<int:event_id>', methods=['POST'])
def leave_event(event_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    db_session = Session()

    db_session.query(EventParticipant).filter_by(
        event_id=event_id, username=username
    ).delete()

    event = db_session.query(Event).filter_by(id=event_id).first()
    if event and event.holder_name == username:
        event.holder_name = None

    db_session.commit()
    db_session.close()

    return redirect(url_for('event'))


# ----------------------------------------------------------------------------------------------clear
@app.route('/clear_event/<int:event_id>', methods=['POST'])
@login_required
def clear_event(event_id):
    username = session['username']
    db_session = Session()

    event = db_session.query(Event).filter_by(id=event_id).first()

    if event and (username == event.holder_name or username == 'admin'):
        participant_count = db_session.query(EventParticipant).filter_by(event_id=event_id).count()

        if participant_count == 0:
            event.status = 'Terminated'
        else:
            event.status = 'Resolved'

        db_session.commit()

    db_session.close()
    return redirect(url_for('event'))


# ----------------------------------------------------------------------------------------------edit trash
@app.route('/edit_trash/<int:event_id>', methods=['POST'])
@login_required
def edit_trash(event_id):
    username = session['username']
    db_session = Session()

    event = db_session.query(Event).filter_by(id=event_id).first()

    if event:
        if username == event.holder_name or username == 'admin' or username == event.created_by:
            session['edit_trash_event'] = event_id

    db_session.close()
    return redirect(url_for('event'))


# ----------------------------------------------------------------------------------------------submit
@app.route('/submit_trash/<int:event_id>', methods=['POST'])
@login_required
def submit_trash(event_id):
    username = session['username']
    db_session = Session()

    event = db_session.query(Event).filter_by(id=event_id).first()
    if not event:
        db_session.close()
        return redirect(url_for('event'))

    if username != event.holder_name and username != event.created_by and username != 'admin':
        db_session.close()
        return "You are not allowed to submit or edit for this event.", 403

    collected_trash = request.form.get('collected_trash', 0)
    try:
        collected_trash = float(collected_trash)
    except ValueError:
        collected_trash = 0

    event.collected_trash = collected_trash
    db_session.commit()
    db_session.close()

    session.pop('edit_trash_event', None)

    return redirect(url_for('event'))




# ----------------------------------------------------------------------------------------------dashboard
@app.route('/dashboard')
def dashboard():
    db_session = Session()

    total_trash = db_session.query(Event).with_entities(
        func.coalesce(func.sum(Event.collected_trash), 0)
    ).scalar()
    total_events = db_session.query(Event).count()
    total_participants = db_session.query(EventParticipant).count()
    pending_reports = db_session.query(Event).filter_by(status='Pending').count()

    events = db_session.query(Event).order_by(Event.id.desc()).all()

    event_list = []
    for e in events:
        count = db_session.query(EventParticipant).filter_by(event_id=e.id).count()
        e_dict = {
            'id': e.id,
            'event_name': e.event_name,
            'location': e.location,
            'description': e.description,
            'datetime': e.datetime,
            'participants': count,
            'max_participants': e.max_participants,
            'status': e.status,
            'holder_name': e.holder_name,
            'collected_trash': e.collected_trash,
            'image': e.image,
            'created_by': e.created_by
        }

        try:
            event_time = parser.parse(e.datetime) if isinstance(e.datetime, str) else e.datetime
            e_dict['readable_time'] = event_time.strftime("%b %d, %Y - %I:%M %p")
        except Exception:
            e_dict['readable_time'] = str(e.datetime)

        event_list.append(e_dict)

    db_session.close()

    return render_template(
        'dashboard.html',
        total_trash=total_trash,
        total_events=total_events,
        total_participants=total_participants,
        pending_reports=pending_reports,
        events=event_list
    )

# ----------------------------------------------------------------------------------------------community
@app.route('/home/community', methods=['GET', 'POST'])
@login_required
def community():
    username = session['username']
    db_session = Session()
    form = CommunityForm()

    if form.validate_on_submit():
        description = form.description.data
        picture = form.picture.data
        image_filename = None

        if picture:
            upload_dir = app.config.get('UPLOAD_FOLDER', 'static/uploads')
            os.makedirs(upload_dir, exist_ok=True)

            dt_str = datetime.now().strftime("%Y%m%d-%H%M%S")
            ext = os.path.splitext(picture.filename)[1]
            safe_username = username.replace(" ", "_")
            filename = f"user-{safe_username}-datetime-{dt_str}{ext}"
            picture.save(os.path.join(upload_dir, filename))
            image_filename = filename

        new_post = CommunityPost(username=username, description=description, image=image_filename)
        db_session.add(new_post)
        db_session.commit()
        db_session.close()
        flash("Post created successfully!", "success")
        return redirect(url_for('community'))

    posts = db_session.query(CommunityPost).order_by(CommunityPost.created_at.desc()).all()
    posts_list = [{
        'id': post.id,
        'username': post.username,
        'description': post.description,
        'image': post.image,
        'created_at': post.created_at
    } for post in posts]

    db_session.close()
    return render_template('community.html', posts=posts_list, form=form)

# ----------------------------------------------------------------------------------------------delete post
@app.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    username = session['username']
    db_session = Session()

    post = db_session.query(CommunityPost).filter_by(id=post_id).first()

    if post and (post.username == username or username == 'admin'):
        db_session.delete(post)
        db_session.commit()

    db_session.close()
    return redirect(url_for('community'))

# ----------------------------------------------------------------------------------------------about

@app.route("/home/about")
def about():
    return render_template("about.html")

if __name__ == '__main__':
    app.run(debug=True)