from flask import Flask, render_template, Response, jsonify, send_file, request, redirect, url_for
from detector import PersonTracker
from repoet_generator import generate_pdf
import cv2
import logging
from typing import Generator
import os
from werkzeug.utils import secure_filename

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Upload Folder
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
detector = PersonTracker()
person_data = {}

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

@app.route('/')
def index():
    """Render the main choice page."""
    return render_template('index.html')

@app.route('/live')
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
def video_feed_live():
    """Stream live webcam feed."""
    return Response(generate_live_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/video_feed_file/<filename>')
def video_feed_file(filename: str):
    """Stream uploaded video feed."""
    return Response(generate_video_frames(filename), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/person_data')
def get_data():
    """Return current person tracking data."""
    return jsonify(person_data)

@app.route('/download_pdf/<person_id>')
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

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)