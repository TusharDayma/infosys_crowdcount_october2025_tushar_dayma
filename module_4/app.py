from flask import Flask, render_template, Response, jsonify, send_file, request, redirect, url_for, flash, g
from detector import PersonTracker
from repoet_generator import generate_pdf
import cv2
import logging
from typing import Generator
import os
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, set_access_cookies, unset_jwt_cookies, jwt_required, get_jwt_identity, verify_jwt_in_request, get_jwt
from dotenv import load_dotenv
import datetime
import io
import csv
# --- NEW: For admin decorator ---
from functools import wraps
from sqlalchemy import func
# ---

# --- Load environment variables ---
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Upload Folders
UPLOAD_FOLDER = 'uploads'
PROFILE_PIC_FOLDER = os.path.join('static', 'profile_pics')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROFILE_PIC_FOLDER, exist_ok=True)

app = Flask(__name__)

# --- Database Config ---
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROFILE_PIC_FOLDER'] = PROFILE_PIC_FOLDER
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')

# --- JWT Config ---
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = False
app.config['JWT_ACCESS_COOKIE_PATH'] = '/'
app.config['JWT_COOKIE_CSRF_PROTECT'] = False

db = SQLAlchemy(app)
jwt = JWTManager(app)

# --- MODIFIED: Detector initialized later ---
detector = None
person_data = {"person_details": {}, "global_metrics": {}}
active_video_source = None

# --- DATABASE MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    profile_pic = db.Column(db.String(120), nullable=False, default='default.png')
    
    # --- REMOVED: User-specific settings columns ---
    
    # --- NEW: Role for Admin ---
    role = db.Column(db.String(50), nullable=False, default='user')
    
    # Relationship to alerts
    alerts = db.relationship('AlertHistory', backref='user', lazy=True, cascade="all, delete-orphan")

class AlertHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    alert_type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255), nullable=False)

# --- NEW: System-wide settings table ---
class SystemSettings(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.String(100), nullable=False)

# --- HELPER FUNCTIONS ---

def get_system_settings_from_db():
    """Fetches system settings from DB or returns defaults."""
    try:
        settings = SystemSettings.query.all()
        settings_dict = {s.key: int(s.value) for s in settings}
        defaults = {
            'person_threshold': settings_dict.get('person_threshold', 10),
            'zone_threshold': settings_dict.get('zone_threshold', 5),
            'overall_threshold': settings_dict.get('overall_threshold', 20)
        }
        return defaults
    except Exception as e:
        logger.error(f"Error reading system settings from DB: {e}. Using hardcoded defaults.")
        return {
            'person_threshold': 10,
            'zone_threshold': 5,
            'overall_threshold': 20
        }

def initialize_system_settings():
    """Ensures default settings exist in the SystemSettings table."""
    defaults = {
        'person_threshold': '10',
        'zone_threshold': '5',
        'overall_threshold': '20'
    }
    try:
        for key, value in defaults.items():
            exists = SystemSettings.query.filter_by(key=key).first()
            if not exists:
                new_setting = SystemSettings(key=key, value=value)
                db.session.add(new_setting)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Could not initialize system settings: {e}")

# --- NEW: Admin Decorator ---
def admin_required():
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") == 'admin':
                return fn(*args, **kwargs)
            else:
                flash("Admins only! Access denied.")
                return redirect(url_for('overview'))
        return decorator
    return wrapper

# --- APP INITIALIZATION ---
def create_app():
    with app.app_context():
        db.create_all()
        initialize_system_settings()
        
        # --- MODIFIED: Initialize detector with settings from DB ---
        global detector
        system_settings = get_system_settings_from_db()
        detector = PersonTracker(system_settings=system_settings)
        logger.info(f"Detector initialized with settings: {system_settings}")
    return app

# --- USER & CONTEXT ---

@app.before_request
def load_user():
    """Load user object from JWT if present."""
    try:
        verify_jwt_in_request(optional=True)
        username = get_jwt_identity()
        if username:
            g.user = User.query.filter_by(username=username).first()
        else:
            g.user = None
    except Exception as e:
        logger.warning(f"Error loading user from JWT: {e}")
        g.user = None

@app.context_processor
def inject_user():
    return dict(user=g.get('user'))

@jwt.unauthorized_loader
def unauthorized(callback):
    flash('Please log in to access this page.')
    return redirect(url_for('login'))

# --- AUTH ROUTES (Login, Register, Logout) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            # --- NEW: Add user role to JWT claims ---
            access_token = create_access_token(
                identity=username, 
                additional_claims={'role': user.role}
            )
            # ---
            
            # --- MODIFIED: Redirect to overview ---
            resp = redirect(url_for('overview'))
            set_access_cookies(resp, access_token)
            flash('Login successful!')
            return resp
        else:
            flash('Invalid username or password.')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists.')
        else:
            password_hash = generate_password_hash(password)
            
            # --- NEW: Make the first user an admin ---
            is_first_user = User.query.count() == 0
            role = 'admin' if is_first_user else 'user'
            # ---
            
            new_user = User(username=username, password_hash=password_hash, role=role)
            db.session.add(new_user)
            db.session.commit()
            
            if is_first_user:
                flash('Admin account created! Please log in.')
            else:
                flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@jwt_required()
def logout():
    """Handle user logout."""
    resp = redirect(url_for('login'))
    unset_jwt_cookies(resp)
    flash('Logged out successfully.')
    return resp

# --- CORE APP ROUTES (Dashboard, Overview, etc.) ---

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/dashboard')
@jwt_required()
def dashboard():
    """Render the 'New Analysis' page."""
    return render_template('dashboard.html')

@app.route('/overview')
@jwt_required()
def overview():
    """Render the main dashboard page with video feed."""
    global active_video_source
    return render_template('overview.html', video_source=active_video_source)

@app.route('/summary')
@jwt_required()
def summary():
    """Render the summary dashboard page with charts."""
    return render_template('summary.html')

@app.route('/history')
@jwt_required()
def history():
    """Render the user's personal alert history."""
    try:
        if g.user:
            alerts = AlertHistory.query.filter_by(user_id=g.user.id).order_by(AlertHistory.timestamp.desc()).all()
            return render_template('history.html', alerts=alerts)
        else:
            flash("User not found.")
            return redirect(url_for('login'))
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        flash("Error fetching alert history.")
        return render_template('history.html', alerts=[])

@app.route('/download_history')
@jwt_required()
def download_history():
    """Download the logged-in user's alert history as a CSV file."""
    try:
        if not g.user:
            flash("User not found.")
            return redirect(url_for('login'))
        
        # --- NEW: Call helper function ---
        csv_output = generate_user_csv(g.user.id)
        if csv_output is None:
            flash("No alerts found to download.")
            return redirect(url_for('history'))

        return Response(
            csv_output,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment;filename=alert_history_{g.user.username}.csv",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )
    except Exception as e:
        logger.error(f"Error generating CSV download: {e}")
        flash("Could not generate CSV file.")
        return redirect(url_for('history'))

# --- NEW: Helper for CSV generation (for admin and user) ---
def generate_user_csv(user_id: int):
    """Generates a CSV byte string for a given user ID."""
    alerts = AlertHistory.query.filter_by(user_id=user_id).order_by(AlertHistory.timestamp.asc()).all()
    if not alerts:
        return None
        
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['Timestamp (UTC)', 'Alert Type', 'Message'])
    for alert in alerts:
        cw.writerow([
            alert.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            alert.alert_type,
            alert.message
        ])
    return si.getvalue().encode('utf-8')
# ---

# --- PROFILE & SETTINGS ROUTES ---

@app.route('/profile', methods=['GET', 'POST'])
@jwt_required()
def profile():
    """Render the profile page and handle updates."""
    if not g.user:
        flash("User not found.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            g.user.first_name = request.form.get('first_name')
            g.user.last_name = request.form.get('last_name')
            
            new_email = request.form.get('email')
            if new_email != g.user.email:
                existing_email = User.query.filter_by(email=new_email).first()
                if existing_email:
                    flash('That email address is already in use.', 'error')
                    return redirect(url_for('profile'))
            g.user.email = new_email

            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            
            if password:
                if password == confirm_password:
                    g.user.password_hash = generate_password_hash(password)
                    flash('Password updated successfully!')
                else:
                    flash('Passwords do not match.', 'error')
                    return redirect(url_for('profile'))

            if 'profile_pic' in request.files:
                file = request.files['profile_pic']
                if file.filename != '':
                    _, ext = os.path.splitext(file.filename)
                    filename = secure_filename(f"user_{g.user.id}{ext}")
                    filepath = os.path.join(app.config['PROFILE_PIC_FOLDER'], filename)
                    
                    if g.user.profile_pic != 'default.png':
                        old_pic_path = os.path.join(app.config['PROFILE_PIC_FOLDER'], g.user.profile_pic)
                        if os.path.exists(old_pic_path):
                            os.remove(old_pic_path)

                    file.save(filepath)
                    g.user.profile_pic = filename

            db.session.commit()
            flash('Profile updated successfully!')
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating profile: {e}")
            flash(f"Error updating profile: {e}", 'error')
        return redirect(url_for('profile'))

    return render_template('profile.html')

@app.route('/delete_profile', methods=['POST'])
@jwt_required()
def delete_profile():
    """Delete the user's account (self-delete)."""
    try:
        user_to_delete = g.user
        if not user_to_delete:
            flash("User not found.")
            return redirect(url_for('login'))
        
        # Prevent admin from self-deleting if they are the only admin
        if user_to_delete.role == 'admin':
            admin_count = User.query.filter_by(role='admin').count()
            if admin_count <= 1:
                flash('You are the only admin. Cannot delete account. Promote another user first.', 'error')
                return redirect(url_for('profile'))

        # cascade="all, delete-orphan" on User.alerts handles deleting alerts
        
        if user_to_delete.profile_pic != 'default.png':
            pic_path = os.path.join(app.config['PROFILE_PIC_FOLDER'], user_to_delete.profile_pic)
            if os.path.exists(pic_path):
                os.remove(pic_path)

        db.session.delete(user_to_delete)
        db.session.commit()
        
        flash('Your account has been permanently deleted.')
        resp = redirect(url_for('login'))
        unset_jwt_cookies(resp)
        return resp
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting profile: {e}")
        flash('Error deleting your account.')
        return redirect(url_for('profile'))

# --- REMOVED: /settings route ---

# --- VIDEO ANALYSIS ROUTES ---

def log_alerts(new_alerts: list, user_id: int):
    """Saves a list of new alerts to the database."""
    try:
        if not user_id:
            logger.warning("Could not log alert: No user_id provided.")
            return
        if new_alerts:
            for alert in new_alerts:
                db_alert = AlertHistory(
                    user_id=user_id,
                    alert_type=alert['type'],
                    message=alert['message']
                )
                db.session.add(db_alert)
            db.session.commit()
            logger.info(f"Logged {len(new_alerts)} new alerts for user {user_id}")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error logging alerts to database: {e}")

def generate_live_frames(user_id: int) -> Generator[bytes, None, None]:
    """Generate video frames for streaming from the webcam."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Failed to open webcam.")
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            processed, data, new_alerts = detector.process_frame(frame)
            
            if new_alerts:
                with app.app_context():
                    log_alerts(new_alerts, user_id)

            global person_data
            person_data = data 

            _, buffer = cv2.imencode('.jpg', processed)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    except Exception as e:
        logger.error(f"Error in live frame generation: {e}")
    finally:
        cap.release()
        logger.info("Webcam released.")

def generate_video_frames(filename: str, user_id: int) -> Generator[bytes, None, None]:
    """Generate video frames for streaming from a video file."""
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logger.error(f"Failed to open video file: {video_path}")
        return

    try:
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            processed, data, new_alerts = detector.process_frame(frame)
            
            if new_alerts:
                with app.app_context():
                    log_alerts(new_alerts, user_id)

            global person_data
            person_data = data

            _, buffer = cv2.imencode('.jpg', processed)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    except Exception as e:
        logger.error(f"Error in video file frame generation: {e}")
    finally:
        cap.release()
        logger.info("Video file released.")

@app.route('/live')
@jwt_required()
def live():
    """Start live webcam analysis session."""
    detector.reset() # Reset tracker for a new session
    global person_data
    person_data = {"person_details": {}, "global_metrics": {}}

    # --- REMOVED: apply_user_settings block ---
    # Detector now uses system defaults automatically
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Failed to open webcam.")
        return "Error: Could not open webcam.", 500

    cv2.namedWindow("Draw Zone on Webcam")
    cv2.setMouseCallback("Draw Zone on Webcam", detector.mouse_callback)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        if not detector.red_zone.ready:
             cv2.putText(frame, "Draw RED Zone with mouse, then press ANY key to start",
                         (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        else:
             detector.red_zone.draw(frame)
             cv2.putText(frame, "Zone set. Press ANY key to start analysis.",
                         (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("Draw Zone on Webcam", frame)
        
        if cv2.waitKey(1) != -1 and detector.red_zone.ready:
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    global active_video_source
    active_video_source = url_for('video_feed_live')
    
    return render_template('analysis.html', video_source=url_for('video_feed_live'))

@app.route('/upload', methods=['POST'])
@jwt_required()
def upload_video():
    """Handle video file upload."""
    if 'video' not in request.files:
        return "No video file part", 400
    file = request.files['video']
    if file.filename == '':
        return "No selected file", 400
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return redirect(url_for('analyze_video', filename=filename))
    return "File upload failed", 500

@app.route('/analyze_video/<filename>')
@jwt_required()
def analyze_video(filename: str):
    """Start video file analysis session."""
    detector.reset() # Reset tracker
    global person_data
    person_data = {"person_details": {}, "global_metrics": {}}

    # --- REMOVED: apply_user_settings block ---
    # Detector now uses system defaults automatically
    
    video_source = url_for('video_feed_file', filename=filename)
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    cap = cv2.VideoCapture(video_path)
    
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            cv2.namedWindow("Draw Zone on Video")
            cv2.setMouseCallback("Draw Zone on Video", detector.mouse_callback)
            
            while True:
                display_frame = frame.copy()
                if not detector.red_zone.ready:
                    cv2.putText(display_frame, "Draw RED Zone with mouse, then press ANY key to start", 
                                (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                else:
                    detector.red_zone.draw(display_frame)
                    cv2.putText(display_frame, "Zone set. Press ANY key to start analysis.",
                                (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                cv2.imshow("Draw Zone on Video", display_frame)
                
                if cv2.waitKey(1) != -1 and detector.red_zone.ready:
                    break
            
            cv2.destroyWindow("Draw Zone on Video")
        cap.release()
        
    global active_video_source
    active_video_source = video_source

    return render_template('analysis.html', video_source=video_source)

@app.route('/video_feed_live')
@jwt_required()
def video_feed_live():
    """Stream live webcam feed."""
    try:
        if not g.user:
            return "Unauthorized", 401
        return Response(generate_live_frames(g.user.id), mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        logger.error(f"Error in video_feed_live: {e}")
        return "Internal Server Error", 500

@app.route('/video_feed_file/<filename>')
@jwt_required()
def video_feed_file(filename: str):
    """Stream uploaded video feed."""
    try:
        if not g.user:
            return "Unauthorized", 401
        return Response(generate_video_frames(filename, g.user.id), mimetype='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        logger.error(f"Error in video_feed_file: {e}")
        return "Internal Server Error", 500

@app.route('/person_data')
@jwt_required()
def get_data():
    """Return current person tracking data for JS frontend."""
    return jsonify(person_data)

@app.route('/download_pdf/<person_id>')
@jwt_required()
def download_pdf(person_id: str):
    """Generate and download a PDF report for a person."""
    if person_id not in person_data.get("person_details", {}):
        return jsonify({"error": "Person not found"}), 404
    try:
        person_info = person_data["person_details"][person_id]
        filepath = generate_pdf(person_id, person_info)
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        logger.error(f"Error generating PDF for {person_id}: {e}")
        return jsonify({"error": "Failed to generate PDF"}), 500

@app.route('/reset')
@jwt_required()
def reset():
    """Reset tracker and clear video source."""
    try:
        detector.reset()
        global person_data
        person_data = {"person_details": {}, "global_metrics": {}}
        global active_video_source
        active_video_source = None
        logger.info("Tracker and zones reset")
        return jsonify({"status": "Tracker and zones reset"})
    except Exception as e:
        logger.error(f"Error resetting tracker: {e}")
        return jsonify({"error": "Failed to reset tracker"}), 500

# --- ADMIN PANEL ROUTES ---

@app.route('/admin')
@admin_required()
def admin_panel():
    """Render the main admin panel page."""
    try:
        all_users = User.query.all()
        # Get 100 most recent alerts from all users
        all_alerts = AlertHistory.query.order_by(AlertHistory.timestamp.desc()).limit(100).all()
        
        # Get system settings to pre-fill the form
        settings = get_system_settings_from_db()

        return render_template(
            'adminpanel.html', 
            all_users=all_users, 
            all_alerts=all_alerts,
            settings=settings
        )
    except Exception as e:
        logger.error(f"Error loading admin panel: {e}")
        flash("Error loading admin panel.", "error")
        return redirect(url_for('overview'))

@app.route('/admin/data/alert_stats')
@admin_required()
def admin_alert_stats():
    """API endpoint to get alert counts for all users."""
    try:
        # Query to count alerts per user
        stats = db.session.query(
            User.username, 
            func.count(AlertHistory.id)
        ).join(
            AlertHistory, User.id == AlertHistory.user_id, isouter=True
        ).group_by(User.username).all()
        
        # Format for Chart.js
        labels = [s[0] for s in stats]
        data = [s[1] for s in stats]
        
        return jsonify(labels=labels, data=data)
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@admin_required()
def admin_delete_user(user_id):
    """Admin action to delete a user."""
    user_to_delete = User.query.get(user_id)
    if not user_to_delete:
        flash("User not found.", "error")
        return redirect(url_for('admin_panel'))

    # Prevent deleting the last admin
    if user_to_delete.role == 'admin':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            flash('Cannot delete the last admin.', 'error')
            return redirect(url_for('admin_panel'))
            
    try:
        # Delete profile pic
        if user_to_delete.profile_pic != 'default.png':
            pic_path = os.path.join(app.config['PROFILE_PIC_FOLDER'], user_to_delete.profile_pic)
            if os.path.exists(pic_path):
                os.remove(pic_path)
        
        # Alerts are deleted by cascade="all, delete-orphan"
        db.session.delete(user_to_delete)
        db.session.commit()
        flash(f"User '{user_to_delete.username}' deleted successfully.")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting user: {e}")
        flash(f"Error deleting user: {e}", "error")
    
    return redirect(url_for('admin_panel'))

@app.route('/admin/user/<int:user_id>/toggle_admin', methods=['POST'])
@admin_required()
def admin_toggle_admin(user_id):
    """Admin action to promote or demote a user."""
    user_to_toggle = User.query.get(user_id)
    if not user_to_toggle:
        flash("User not found.", "error")
        return redirect(url_for('admin_panel'))
    
    try:
        if user_to_toggle.role == 'user':
            user_to_toggle.role = 'admin'
            flash(f"User '{user_to_toggle.username}' promoted to Admin.")
        else:
            # Prevent demoting the last admin
            if user_to_toggle.id == g.user.id:
                flash("Cannot demote yourself.", "error")
                return redirect(url_for('admin_panel'))
                
            admin_count = User.query.filter_by(role='admin').count()
            if admin_count <= 1:
                flash('Cannot demote the last admin.', 'error')
                return redirect(url_for('admin_panel'))
                
            user_to_toggle.role = 'user'
            flash(f"User '{user_to_toggle.username}' demoted to User.")
            
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error toggling admin status: {e}")
        flash(f"Error toggling admin status: {e}", "error")

    return redirect(url_for('admin_panel'))

@app.route('/admin/download_csv/<int:user_id>')
@admin_required()
def admin_download_csv(user_id):
    """Admin action to download any user's CSV."""
    user = User.query.get(user_id)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for('admin_panel'))
        
    try:
        csv_output = generate_user_csv(user_id)
        if csv_output is None:
            flash(f"User '{user.username}' has no alerts to download.")
            return redirect(url_for('admin_panel'))

        return Response(
            csv_output,
            mimetype="text/csv",
            headers={
                "Content-Disposition": f"attachment;filename=alert_history_{user.username}.csv",
                "Content-Type": "text/csv; charset=utf-8"
            }
        )
    except Exception as e:
        logger.error(f"Error generating admin CSV download: {e}")
        flash("Could not generate CSV file.")
        return redirect(url_for('admin_panel'))

@app.route('/admin/settings', methods=['POST'])
@admin_required()
def admin_update_settings():
    """Admin action to update system-wide default settings."""
    try:
        keys = ['person_threshold', 'zone_threshold', 'overall_threshold']
        for key in keys:
            setting = SystemSettings.query.filter_by(key=key).first()
            form_value = request.form.get(key)
            if setting and form_value:
                setting.value = form_value
        
        db.session.commit()
        
        # --- IMPORTANT: Reload detector with new settings ---
        global detector
        system_settings = get_system_settings_from_db()
        detector = PersonTracker(system_settings=system_settings)
        # ---
        
        flash("System-wide alert settings updated. Detector has been reloaded.")
        logger.info(f"Admin updated system settings to: {system_settings}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating system settings: {e}")
        flash(f"Error updating system settings: {e}", "error")
        
    return redirect(url_for('admin_panel'))

# --- MAIN ---

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)