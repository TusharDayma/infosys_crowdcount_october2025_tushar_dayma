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
from flask_jwt_extended import JWTManager, create_access_token, set_access_cookies, unset_jwt_cookies, jwt_required, get_jwt_identity, verify_jwt_in_request
from dotenv import load_dotenv

# --- Load environment variables from .env file ---
load_dotenv()
# ---

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Upload Folder
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)

# --- Load configuration from .env file ---
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')

# Construct the database URI
DATABASE_URI = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
# --- END OF MODIFICATIONS ---

app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = False
app.config['JWT_ACCESS_COOKIE_PATH'] = '/'
app.config['JWT_COOKIE_CSRF_PROTECT'] = False

db = SQLAlchemy(app)
jwt = JWTManager(app)
detector = PersonTracker()
person_data = {}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    # --- MODIFIED: Increased length to 256 for longer password hashes ---
    password_hash = db.Column(db.String(256), nullable=False)


# Load user before each request
# Load user before each request
@app.before_request
def load_user():
    """Load user identity from JWT if present."""
    try:
        # verify_jwt_in_request(optional=True) will check for a token
        # and load it into context if it's valid. It won't
        # throw an error if no token is present.
        verify_jwt_in_request(optional=True)
        
        # Now, get_jwt_identity() will return the identity
        # if a token was found, or None if not.
        g.user = get_jwt_identity()
    except Exception:
        # Catch any other potential JWT errors
        g.user = None


# Context processor to inject user into templates
@app.context_processor
def inject_user():
    return dict(user=g.get('user'))


# Unauthorized handler
@jwt.unauthorized_loader
def unauthorized(callback):
    flash('Please log in to access this page.')
    return redirect(url_for('login'))


@app.route('/')
def index():
    """Redirect root URL to the login page."""
    return redirect(url_for('login'))


@app.route('/favicon.ico')
def favicon():
    return '', 204


def generate_live_frames() -> Generator[bytes, None, None]:
    """Generate video frames for streaming from the webcam."""
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        logger.error("Failed to open webcam. Ensure it is connected.")
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Failed to read frame from webcam")
                break

            processed, data = detector.process_frame(frame)
            global person_data
            person_data = data

            _, buffer = cv2.imencode('.jpg', processed)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    except Exception as e:
        logger.error(f"Error in live frame generation: {e}")
    finally:
        cap.release()
        logger.info("Webcam released.")


def generate_video_frames(filename: str) -> Generator[bytes, None, None]:
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
                logger.info(f"End of video file: {filename}")
                break

            processed, data = detector.process_frame(frame)
            global person_data
            person_data = data

            _, buffer = cv2.imencode('.jpg', processed)
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    except Exception as e:
        logger.error(f"Error in video file frame generation: {e}")
    finally:
        cap.release()
        logger.info("Video file released.")


@app.route('/dashboard')
@jwt_required()
def dashboard():
    """Render the dashboard page."""
    return render_template('dashboard.html')

# --- START OF NEW ROUTES ---

@app.route('/overview')
@jwt_required()
def overview():
    """Render the new overview/dashboard page."""
    return render_template('overview.html')

@app.route('/history')
@jwt_required()
def history():
    """Render the history page."""
    return render_template('history.html')

@app.route('/profile')
@jwt_required()
def profile():
    """Render the profile page."""
    return render_template('profile.html')

@app.route('/settings')
@jwt_required()
def settings():
    """Render the settings page."""
    return render_template('settings.html')

# --- END OF NEW ROUTES ---


@app.route('/live')
@jwt_required()
def live():
    """Open a window to draw a zone, then render the analysis page."""
    detector.reset() # Reset tracker for a new session
    global person_data
    person_data = {}

    # --- THIS IS THE NEW LOGIC FOR THE WEBCAM ---
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
        
        # Display instructions until the zone is set
        if not detector.red_zone.ready:
             cv2.putText(frame, "Draw RED Zone with mouse, then press ANY key to start",
                         (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        else:
             # Show the drawn zone for confirmation
             detector.red_zone.draw(frame)
             cv2.putText(frame, "Zone set. Press ANY key to start analysis.",
                         (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("Draw Zone on Webcam", frame)
        
        # Wait for a key press to exit the setup, but only if a zone has been drawn
        if cv2.waitKey(1) != -1 and detector.red_zone.ready:
            break
    
    cap.release()
    cv2.destroyAllWindows()
    # --- END OF THE NEW LOGIC ---

    return render_template('analysis.html', video_source=url_for('video_feed_live'))


@app.route('/upload', methods=['POST'])
@jwt_required()
def upload_video():
    """Handle video file upload and redirect to the analysis page."""
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
    """Render the analysis page for the uploaded video."""
    detector.reset() # Reset tracker for a new session
    global person_data
    person_data = {}
    video_source = url_for('video_feed_file', filename=filename)
    
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    cap = cv2.VideoCapture(video_path)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            cv2.namedWindow("Draw Zone on Video")
            cv2.setMouseCallback("Draw Zone on Video", detector.mouse_callback)
            while not detector.red_zone.ready:
                display_frame = frame.copy()
                cv2.putText(display_frame, "Draw RED Zone with mouse, then press ANY key to start", 
                            (40, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.imshow("Draw Zone on Video", display_frame)
                if cv2.waitKey(1) != -1:
                    break
            cv2.destroyWindow("Draw Zone on Video")
        cap.release()

    return render_template('analysis.html', video_source=video_source)


@app.route('/video_feed_live')
@jwt_required()
def video_feed_live():
    """Stream live webcam feed."""
    return Response(generate_live_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/video_feed_file/<filename>')
@jwt_required()
def video_feed_file(filename: str):
    """Stream uploaded video feed."""
    return Response(generate_video_frames(filename), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/person_data')
@jwt_required()
def get_data():
    """Return current person tracking data."""
    return jsonify(person_data)


@app.route('/download_pdf/<person_id>')
@jwt_required()
def download_pdf(person_id: str):
    """Generate and download a PDF report for a person."""
    if person_id not in person_data:
        logger.warning(f"Person {person_id} not found")
        return jsonify({"error": "Person not found"}), 404
    try:
        filepath = generate_pdf(person_id, person_data[person_id])
        return send_file(filepath, as_attachment=True)
    except Exception as e:
        logger.error(f"Error generating PDF for {person_id}: {e}")
        return jsonify({"error": "Failed to generate PDF"}), 500


@app.route('/reset')
@jwt_required()
def reset():
    """Reset tracker and zones."""
    try:
        detector.reset()
        global person_data
        person_data = {}
        logger.info("Tracker and zones reset")
        return jsonify({"status": "Tracker and zones reset"})
    except Exception as e:
        logger.error(f"Error resetting tracker: {e}")
        return jsonify({"error": "Failed to reset tracker"}), 500


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            access_token = create_access_token(identity=username)
            # --- MODIFIED: Redirect to the new 'overview' page after login ---
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
            new_user = User(username=username, password_hash=password_hash)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
    return render_template('register.html')

# --- NOTE: The duplicate /dashboard function was REMOVED from here ---
# --- NOTE: The duplicate /live function was REMOVED from here ---

# --- FIXED INDENTATION ---
@app.route('/logout')
@jwt_required()
def logout():
    """Handle user logout."""
    resp = redirect(url_for('login'))
    unset_jwt_cookies(resp)
    flash('Logged out successfully.')
    return resp


if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create database tables if they don't exist
    app.run(debug=True, host="0.0.0.0", port=5000)