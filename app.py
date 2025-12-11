# app.py
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_login import login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, relationship
from dateutil import parser
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import shutil
from functools import wraps

from models import User, Base, Event, EventParticipant, CommunityPost
from forms import RegisterForm, EventForm, CommunityForm


User.events_created = relationship(
    Event,
    back_populates="creator",
    foreign_keys=[Event.created_by_id]
)
Event.creator = relationship(
    User,
    back_populates="events_created",
    foreign_keys=[Event.created_by_id]
)

# -----------------------------------------------------------------------------Database 
engine = create_engine('sqlite:///database.db', echo=True)
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


# -----------------------------------------------------------------------------Flask App Setup
app = Flask(__name__)
app.secret_key = 'water-cleaning-operation'

# -----------------------------------------------------------------------------WTForms Login Form 
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3)])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

# -----------------------------------------------------------------------------Login Required  
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------------------------------------------------------Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        username = form.username.data.strip()
        password = form.password.data

        db_session = Session()
        user = db_session.query(User).filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            session['username'] = user.username
            flash(f"Welcome, {username}!", "success")
            db_session.close()
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password", "danger")
            db_session.close()
            return redirect(url_for('login'))

    return render_template('login.html', form=form)

# -----------------------------------------------------------------------------Logout 
@app.route('/logout')
@login_required
def logout():
    username = session.pop('username', None)  # remove user from session
    flash(f"Goodbye, {username}! You have been logged out.", "success")
    return redirect(url_for('login'))


# -----------------------------------------------------------------------------Index
@app.route('/')
def index():
    if 'username' not in session:
        flash("Please log in first.", "warning")
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'])



# -----------------------------------------------------------------------------Register Route 
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        fullname = form.fullname.data.strip()
        username = form.username.data.strip()
        email = form.email.data.strip()
        password = form.password.data
        confirm_password = form.confirm_password.data

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('register'))

        db_session = Session()

        # Check if username already exists
        existing_user = db_session.query(User).filter_by(username=username).first()
        if existing_user:
            flash("Username already exists.", "danger")
            db_session.close()
            return redirect(url_for('register'))

        # Hash password
        hashed_password = generate_password_hash(password)

        # Create new user
        new_user = User(
            fullname=fullname,
            username=username,
            email=email,
            password=hashed_password
        )

        db_session.add(new_user)
        db_session.commit()
        db_session.close()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

# -----------------------------------------------------------------------------Events Route
@app.route('/event')
@login_required
def event():
    username = session['username']
    db_session = Session()

    # Get all events
    events = db_session.query(Event).order_by(Event.id.desc()).all()
    events_with_joined = []

    # Get current user
    current_user = db_session.query(User).filter_by(username=username).first()

    for e in events:
        # Check if current user joined the event
        joined = db_session.query(EventParticipant).filter_by(event_id=e.id, user_id=current_user.id).first() is not None

        # Count participants
        participant_count = db_session.query(EventParticipant).filter_by(event_id=e.id).count()

        # Parse datetime safely
        try:
            event_time = parser.parse(e.datetime) if isinstance(e.datetime, str) else e.datetime
        except Exception:
            event_time = e.datetime

        # Update status if event is past due
        if datetime.now() >= event_time:
            if participant_count == 0 and e.status != 'Terminated':
                e.status = 'Terminated'
                db_session.commit()
            elif participant_count > 0 and e.status == 'Pending':
                e.status = 'In Progress'
                db_session.commit()

        # Determine holder dynamically
        holder = None
        if e.creator:
            holder = e.creator.username
        else:
            first_participant = db_session.query(EventParticipant).filter_by(event_id=e.id).order_by(EventParticipant.id.asc()).first()
            if first_participant:
                user_obj = db_session.query(User).filter_by(id=first_participant.user_id).first()
                holder = user_obj.username if user_obj else None

        # Prepare event dictionary
        e_dict = {
            'id': e.id,
            'event_name': e.event_name,
            'location': e.location,
            'description': e.description,
            'datetime': e.datetime,
            'participants': participant_count,
            'max_participants': e.max_participants,
            'joined': joined,
            'holder': holder,
            'status': e.status,
            'readable_time': event_time.strftime("%b %d, %Y - %I:%M %p") if event_time else str(e.datetime),
            'image': e.image,
            'collected_trash': e.collected_trash
        }
        events_with_joined.append(e_dict)

    db_session.close()
    return render_template('event.html', username=username, events=events_with_joined)

# -----------------------------------------------------------------------------Report (Create) 
@app.route('/report', methods=['GET', 'POST'])
@login_required
def report():
    form = EventForm() 
    error = None
    success = None
    min_date = datetime.now()

    if form.validate_on_submit():
        event_name = form.event_name.data.strip()
        location = form.location.data.strip()
        description = form.description.data.strip()
        event_datetime = form.datetime.data  
        max_participants = form.participants.data or 50
        image_file = form.image.data  

        
        if event_datetime < min_date:
            error = "You cannot select a past date!"
        else:
            db_session = Session()

            # Create new Event
            new_event = Event(
                event_name=event_name,
                location=location,
                description=description,
                datetime=event_datetime,
                max_participants=max_participants,
                collected_trash=0,
                status='Pending',
                created_by_id=db_session.query(User.id).filter_by(username=session['username']).scalar()
            )

            db_session.add(new_event)
            db_session.commit()

            # Handle uploaded image
            if image_file and image_file.filename != '':
                upload_dir = os.path.join('static', 'uploads')
                os.makedirs(upload_dir, exist_ok=True)

                filename = secure_filename(f"event-{new_event.id}-{image_file.filename}")
                image_file.save(os.path.join(upload_dir, filename))
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

# -----------------------------------------------------------------------------Dashboard
@app.route('/dashboard')
@login_required
def dashboard():
    db_session = Session()

    # Summary stats
    total_trash = db_session.query(func.coalesce(func.sum(Event.collected_trash), 0)).scalar()
    total_events = db_session.query(Event).count()
    total_participants = db_session.query(EventParticipant).count()
    pending_reports = db_session.query(Event).filter_by(status='Pending').count()

    # List all events
    events = db_session.query(Event).order_by(Event.id.desc()).all()
    event_list = []

    for e in events:
        participants_count = db_session.query(EventParticipant).filter_by(event_id=e.id).count()

        try:
            event_time = parser.parse(e.datetime) if isinstance(e.datetime, str) else e.datetime
            readable_time = event_time.strftime("%b %d, %Y - %I:%M %p")
        except Exception:
            readable_time = str(e.datetime)

        
        holder_name = getattr(e, 'holder', 'No holder yet') 
        created_by = getattr(e, 'created_by', 'Unknown')     

        e_dict = {
            'id': e.id,
            'event_name': e.event_name,
            'location': e.location,
            'description': e.description,
            'datetime': e.datetime,
            'participants': participants_count,
            'max_participants': e.max_participants,
            'status': e.status,
            'holder_name': holder_name,
            'collected_trash': getattr(e, 'collected_trash', 0), 
            'image': getattr(e, 'image', '/static/uploads/default.jpg'),
            'created_by': created_by,
            'readable_time': readable_time
        }
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

# -----------------------------------------------------------------------------Community 
@app.route('/community', methods=['GET', 'POST'])
@login_required
def community():
    username = session['username']
    db_session = Session()
    form = CommunityForm()

    # Handle new post submission 
    if form.validate_on_submit():
        description = form.description.data.strip()
        picture = form.picture.data
        image_filename = None

        if picture and picture.filename != '':
            upload_dir = app.config.get('UPLOAD_FOLDER', 'static/uploads')
            os.makedirs(upload_dir, exist_ok=True)

            dt_str = datetime.now().strftime("%Y%m%d-%H%M%S")
            ext = os.path.splitext(picture.filename)[1]
            safe_username = username.replace(" ", "_")
            filename = f"user-{safe_username}-datetime-{dt_str}{ext}"

            picture.save(os.path.join(upload_dir, filename))
            image_filename = filename 

        # Create post
        new_post = CommunityPost(
            user_id=db_session.query(User.id).filter_by(username=username).scalar(),
            description=description,
            image=image_filename
        )

        db_session.add(new_post)
        db_session.commit()
        db_session.close()
        flash("Post created successfully!", "success")
        return redirect(url_for('community'))

    # Get all posts 
    posts = db_session.query(CommunityPost).order_by(CommunityPost.created_at.desc()).all()
    posts_list = []

    for post in posts:
        author = db_session.query(User).filter_by(id=post.user_id).first()
        posts_list.append({
            'id': post.id,
            'username': author.username if author else "Unknown",
            'description': post.description,
            'image': post.image, 
            'created_at': post.created_at
        })

    db_session.close()
    return render_template('community.html', posts=posts_list, form=form)

# -----------------------------------------------------------------------------Event Participant
@app.route('/event/<int:event_id>/participants')
@login_required
def event_participants(event_id):
    db_session = Session()

    # Get the event
    event = db_session.query(Event).filter_by(id=event_id).first()
    if not event:
        db_session.close()
        flash("Event not found.", "danger")
        return redirect(url_for('event'))

    # Get participants
    participants = (
        db_session.query(EventParticipant)
        .filter_by(event_id=event_id)
        .all()
    )

    participants_list = []
    for p in participants:
        user = db_session.query(User).filter_by(id=p.user_id).first()
        if user:
            participants_list.append({
                'id': user.id,
                'username': user.username,
                'fullname': user.fullname,
                'email': user.email
            })

    db_session.close()

    return render_template(
        'event_participants.html',
        event=event,
        participants=participants_list
    )
# -----------------------------------------------------------------------------Delete Event
@app.route('/event/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    db_session = Session()
    
    # Get the event
    event = db_session.query(Event).filter_by(id=event_id).first()
    if not event:
        db_session.close()
        flash("Event not found.", "danger")
        return redirect(url_for('event'))

    # Only allow creator to delete
    current_user = db_session.query(User).filter_by(username=session['username']).first()
    if event.created_by_id != current_user.id:
        db_session.close()
        flash("You are not authorized to delete this event.", "danger")
        return redirect(url_for('event'))

    db_session.query(EventParticipant).filter_by(event_id=event_id).delete()

    db_session.delete(event)
    db_session.commit()
    db_session.close()

    flash(f"Event '{event.event_name}' has been deleted successfully.", "success")
    return redirect(url_for('event'))

# -----------------------------------------------------------------------------Join Event
@app.route('/event/<int:event_id>/join', methods=['POST'])
@login_required
def join_event(event_id):
    db_session = Session()

    # Get the event
    event = db_session.query(Event).filter_by(id=event_id).first()
    if not event:
        db_session.close()
        flash("Event not found.", "danger")
        return redirect(url_for('event'))

    # Get current user
    current_user = db_session.query(User).filter_by(username=session['username']).first()

    # Check if user already joined
    already_joined = db_session.query(EventParticipant).filter_by(event_id=event_id, user_id=current_user.id).first()
    if already_joined:
        db_session.close()
        flash("You have already joined this event.", "warning")
        return redirect(url_for('event'))

    # Check max participants
    participant_count = db_session.query(EventParticipant).filter_by(event_id=event_id).count()
    if participant_count >= event.max_participants:
        db_session.close()
        flash("This event has reached the maximum number of participants.", "danger")
        return redirect(url_for('event'))

    # Add participant
    new_participant = EventParticipant(
        event_id=event_id,
        user_id=current_user.id
    )
    db_session.add(new_participant)
    db_session.commit()

    # Access event attributes BEFORE closing session
    event_name = event.event_name

    db_session.close()
    flash(f"You have successfully joined '{event_name}'!", "success")
    return redirect(url_for('event'))

# ----------------------------------------------------------------------------- Leave Event
@app.route('/event/<int:event_id>/leave', methods=['POST'])
@login_required
def leave_event(event_id):
    db_session = Session()

    # Get the event
    event = db_session.query(Event).filter_by(id=event_id).first()
    if not event:
        db_session.close()
        flash("Event not found.", "danger")
        return redirect(url_for('event'))

    # Get current user
    current_user = db_session.query(User).filter_by(username=session['username']).first()

    # Check if user is a participant
    participant = db_session.query(EventParticipant).filter_by(event_id=event_id, user_id=current_user.id).first()
    if not participant:
        db_session.close()
        flash("You are not a participant of this event.", "warning")
        return redirect(url_for('event'))

    # Access event attributes BEFORE deleting or closing session
    event_name = event.event_name

    # Remove participant
    db_session.delete(participant)
    db_session.commit()
    db_session.close()

    flash(f"You have successfully left '{event_name}'.", "success")
    return redirect(url_for('event'))

# -----------------------------------------------------------------------------Clear Event Participants
@app.route('/event/<int:event_id>/clear', methods=['POST'])
@login_required
def clear_event(event_id):
    db_session = Session()
    event = db_session.query(Event).filter_by(id=event_id).first()
    if not event:
        db_session.close()
        flash("Event not found.", "danger")
        return redirect(url_for('event'))

    # Store event name
    event_name = event.event_name

    event.status = 'Resolved'
    db_session.commit()
    db_session.close()

    flash(f"Area cleared for '{event_name}'. Please submit collected trash.", "success")
    return redirect(url_for('event'))

# -----------------------------------------------------------------------------Edit Trash 
@app.route('/event/<int:event_id>/edit_trash', methods=['POST'])
@login_required
def edit_trash(event_id):
    db_session = Session()

    event = db_session.query(Event).filter_by(id=event_id).first()
    if not event:
        db_session.close()
        flash("Event not found.", "danger")
        return redirect(url_for('event'))

    # Only allow admin, holder, or creator to edit
    current_user = db_session.query(User).filter_by(username=session['username']).first()
    holder_username = None
    if event.creator:
        holder_username = event.creator.username
    else:
        first_participant = db_session.query(EventParticipant).filter_by(event_id=event.id).order_by(EventParticipant.id.asc()).first()
        if first_participant:
            user_obj = db_session.query(User).filter_by(id=first_participant.user_id).first()
            holder_username = user_obj.username if user_obj else None

    if session['username'] not in [holder_username, 'admin', event.creator.username if event.creator else None]:
        db_session.close()
        flash("You are not authorized to edit this event's trash.", "danger")
        return redirect(url_for('event'))

    session['editing_event_id'] = event_id

    db_session.close()
    return redirect(url_for('event'))

# -----------------------------------------------------------------------------Submit Trash
@app.route('/event/<int:event_id>/submit_trash', methods=['POST'])
@login_required
def submit_trash(event_id):
    db_session = Session()

    event = db_session.query(Event).filter_by(id=event_id).first()
    if not event:
        db_session.close()
        flash("Event not found.", "danger")
        return redirect(url_for('event'))

    current_user = db_session.query(User).filter_by(username=session['username']).first()
    holder_username = None
    if event.creator:
        holder_username = event.creator.username
    else:
        first_participant = db_session.query(EventParticipant).filter_by(event_id=event.id).order_by(EventParticipant.id.asc()).first()
        if first_participant:
            user_obj = db_session.query(User).filter_by(id=first_participant.user_id).first()
            holder_username = user_obj.username if user_obj else None

    if session['username'] not in [holder_username, 'admin', event.creator.username if event.creator else None]:
        db_session.close()
        flash("You are not authorized to submit this event's trash.", "danger")
        return redirect(url_for('event'))

    # Update collected trash
    try:
        collected_trash = float(request.form.get('collected_trash', 0))
    except ValueError:
        collected_trash = 0

    event.collected_trash = collected_trash
    db_session.commit()

    #  Access event_name before closing session
    event_name = event.event_name

    db_session.close()
    session.pop('editing_event_id', None)

    flash(f"Collected trash for '{event_name}' updated to {collected_trash} kg.", "success")
    return redirect(url_for('event'))

# -----------------------------------------------------------------------------Delete Post
@app.route('/community/delete/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    db_session = Session()  
    post = db_session.query(CommunityPost).get(post_id)

    if not post:
        flash("Post not found.", "error")
        db_session.close()
        return redirect(url_for('community'))

    # Get author username
    author = db_session.query(User).filter_by(id=post.user_id).first()
    author_username = author.username if author else None

    # Only allow the owner or admin to delete
    if author_username != session['username'] and session['username'] != 'admin':
        flash("You are not allowed to delete this post.", "error")
        db_session.close()
        return redirect(url_for('community'))

    # Delete the post image file if exists
    if post.image:
        try:
            image_path = post.image.replace("/static/", "static/")
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            print(f"Error deleting image: {e}")

    # Delete post
    db_session.delete(post)
    db_session.commit()
    db_session.close()
    
    flash("Post deleted successfully.", "success")
    return redirect(url_for('community'))


# -----------------------------------------------------------------------------About 
@app.route('/about')
@login_required 
def about():
    return render_template('about.html')

# -----------------------------------------------------------------------------Run App
if __name__ == '__main__':
    app.run(debug=True)
