import cv2
import time
from ultralytics import YOLO
import yaml
import logging
from typing import Tuple, Dict, Optional, List
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Zone:
    """Manages a rectangular zone for tracking purposes."""
    def __init__(self, name: str, color: Tuple[int, int, int], label: str):
        self.name = name
        self.color = color
        self.label = label
        self.points: Optional[Tuple[Tuple[int, int], Tuple[int, int]]] = None
        self.ready = False

    def set_points(self, start: Tuple[int, int], end: Tuple[int, int]) -> None:
        """Set zone coordinates and mark as ready."""
        self.points = (start, end)
        self.ready = True
        logger.info(f"{self.label} zone defined: {self.points}")

    def is_inside(self, x: int, y: int) -> bool:
        """Check if a point is inside the zone."""
        if not self.points or not self.ready:
            return False
        (x1, y1), (x2, y2) = self.points
        return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)

    def draw(self, frame: np.ndarray) -> None:
        """Draw the zone on the frame."""
        if self.ready:
            cv2.rectangle(frame, self.points[0], self.points[1], self.color, 2)
            cv2.putText(frame, self.label, (self.points[0][0], self.points[0][1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, self.color, 2)

class PersonTracker:
    """Tracks people and their time spent in red or green zones."""
    
    # --- MODIFIED: Init now only takes system settings from DB ---
    def __init__(self, system_settings: dict, config_path: str = "config.yaml"):
        
        # 1. Load config.yaml for non-DB settings (model path, heatmap)
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to load config.yaml: {e}. Using defaults.")
            self.config = {
                'model': {'path': 'yolov8n.pt'},
                'zones': {'red': {'label': 'Danger Zone'}},
                'heatmap_alpha': 0.4
            }
            
        try:
            self.model = YOLO(self.config['model']['path'])
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
            
        self.red_zone = Zone('red', (0, 0, 255), self.config['zones']['red']['label'])
        self.heatmap_alpha = self.config.get('heatmap_alpha', 0.4)
        
        # 2. Load system-wide thresholds directly
        self.person_alert_threshold = system_settings.get('person_threshold', 10)
        self.zone_population_threshold = system_settings.get('zone_threshold', 5)
        self.overall_population_threshold = system_settings.get('overall_threshold', 20)
        
        # 3. Initialize state
        self.drawing = False
        self.start_point: Optional[Tuple[int, int]] = None
        self.track_data: Dict[int, Dict] = {}
        self.heatmap_points: List[Tuple[int, int]] = []
        self.zone_alert_active = False
        self.overall_alert_active = False
        
        logger.info(f"Detector initialized with settings: Person={self.person_alert_threshold}, Zone={self.zone_population_threshold}, Overall={self.overall_population_threshold}")
        # --- END OF MODIFIED INIT ---

    def mouse_callback(self, event: int, x: int, y: int, flags: int, param: any) -> None:
        """Handle mouse events to draw the red zone."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and self.drawing:
            self.drawing = False
            self.red_zone.set_points(self.start_point, (x, y))

    # --- REMOVED: apply_user_settings method ---

    def reset(self) -> None:
        """Reset red zone and tracking data."""
        self.red_zone.points = None
        self.red_zone.ready = False
        self.track_data.clear()
        self.heatmap_points.clear()
        self.zone_alert_active = False
        self.overall_alert_active = False
        
        # --- REMOVED: apply_user_settings call ---
        
        logger.info("Tracker, red zone, and heatmap reset")

    def _apply_heatmap(self, frame: np.ndarray) -> np.ndarray:
        """Applies a heatmap overlay based on accumulated points."""
        if not self.heatmap_points:
            return frame
        
        try:
            heatmap_acc = np.zeros((frame.shape[0], frame.shape[1]), dtype=np.float32)
            for x, y in self.heatmap_points:
                if 0 <= y < frame.shape[0] and 0 <= x < frame.shape[1]:
                    heatmap_acc[y, x] += 1
            
            heatmap_blurred = cv2.GaussianBlur(heatmap_acc, (91, 91), 0)
            heatmap_norm = cv2.normalize(heatmap_blurred, None, 0, 255, cv2.NORM_MINMAX, dtype=np.CV_8U)
            heatmap_color = cv2.applyColorMap(heatmap_norm, cv2.COLORMAP_JET)
            mask = cv2.inRange(heatmap_color, np.array([0,0,0]), np.array([0,0,0]))
            mask_inv = cv2.bitwise_not(mask)
            heatmap_masked = cv2.bitwise_and(heatmap_color, heatmap_color, mask=mask_inv)
            overlay = cv2.addWeighted(frame, 1 - self.heatmap_alpha, heatmap_masked, self.heatmap_alpha, 0)
            
            self.heatmap_points = self.heatmap_points[-500:] # Keep last 500 points
            
            return overlay
        except Exception as e:
            logger.error(f"Error applying heatmap: {e}")
            return frame

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict, List[Dict]]:
        """Process a frame to detect and track people, calculate zone times, and generate alerts."""
        annotated = frame.copy()
        person_details_summary = {}
        frame_height, frame_width = frame.shape[:2]
        new_alerts_to_log: List[Dict] = []

        if not self.red_zone.ready:
            cv2.putText(annotated, "Draw RED Zone with mouse", (40, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            return annotated, {"person_details": {}, "global_metrics": {}}, []

        self.red_zone.draw(annotated)

        try:
            results = self.model.track(annotated, persist=True, verbose=False, classes=[0])
        except Exception as e:
            logger.error(f"Error in YOLO tracking: {e}")
            return annotated, {"person_details": {}, "global_metrics": {}}, []

        current_time = time.time()
        total_count = 0
        red_zone_count = 0
        
        if results[0].boxes.id is not None:
            ids = results[0].boxes.id.cpu().numpy().astype(int)
            boxes = results[0].boxes.xyxy.cpu().numpy()
            total_count = len(ids)

            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box)
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                track_id = ids[i]
                label = "person"
                
                self.heatmap_points.append((cx, y2))

                if track_id not in self.track_data:
                    self.track_data[track_id] = {
                        "label": label,
                        "times": {"red": 0.0, "green": 0.0},
                        "current_zone": "green",
                        "last_time": current_time,
                        "alerted": False
                    }

                person = self.track_data[track_id]
                elapsed = current_time - person["last_time"]
                person["last_time"] = current_time

                current_zone = "red" if self.red_zone.is_inside(cx, cy) else "green"
                person["times"][current_zone] += elapsed
                person["current_zone"] = current_zone
                
                if current_zone == "red":
                    red_zone_count += 1 

                if person["times"]["red"] > self.person_alert_threshold and not person["alerted"]:
                    person["alerted"] = True
                    msg = f"ALERT: Person {track_id} in danger zone too long!"
                    new_alerts_to_log.append({'type': 'Per-Person', 'message': msg})
                    logger.warning(msg)

                color = (0, 0, 255) if current_zone == "red" else (0, 255, 0)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                cv2.putText(annotated, f"P{track_id}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                if person["alerted"]:
                    cv2.putText(annotated, "ALERT!", (x1, y1 - 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                person_details_summary[f"P{track_id}"] = {
                    "Label": label,
                    "Current Zone": person["current_zone"],
                    "Red Zone Time (s)": round(person["times"]["red"], 2),
                    "Green Zone Time (s)": round(person["times"]["green"], 2),
                    "Total Time (s)": round(sum(person["times"].values()), 2),
                    "Alert": "Yes" if person["alerted"] else "No",
                    "Location": (cx, cy)
                }
        
        green_zone_count = total_count - red_zone_count
        
        # --- Zone Population Alert ---
        population_alert = red_zone_count > self.zone_population_threshold
        if population_alert and not self.zone_alert_active:
            self.zone_alert_active = True
            msg = f"ZONE POPULATION ALERT: {red_zone_count} people in Red Zone!"
            new_alerts_to_log.append({'type': 'Zone Population', 'message': msg})
        elif not population_alert and self.zone_alert_active:
            self.zone_alert_active = False
            
        if population_alert:
            cv2.putText(annotated, f"ZONE POPULATION ALERT: {red_zone_count} in Zone!", (40, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)

        # --- Overall Population Alert ---
        overall_population_alert = total_count > self.overall_population_threshold
        if overall_population_alert and not self.overall_alert_active:
            self.overall_alert_active = True
            msg = f"OVERALL POPULATION ALERT: {total_count} people in frame!"
            new_alerts_to_log.append({'type': 'Overall Population', 'message': msg})
        elif not overall_population_alert and self.overall_alert_active:
            self.overall_alert_active = False
            
        if overall_population_alert:
            cv2.putText(annotated, f"OVERALL POPULATION ALERT: {total_count} people!", (40, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 255), 3)

        annotated = self._apply_heatmap(annotated)
        
        final_data = {
            "person_details": person_details_summary,
            "global_metrics": {
                "total_count": total_count,
                "red_zone_count": red_zone_count,
                "green_zone_count": green_zone_count,
                "population_alert": population_alert,
                "overall_population_alert": overall_population_alert,
                "frame_width": frame_width,
                "frame_height": frame_height
            }
        }

        return annotated, final_data, new_alerts_to_log