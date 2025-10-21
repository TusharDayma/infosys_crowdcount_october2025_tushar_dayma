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
    def __init__(self, config_path: str = "config.yaml"):
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
        try:
            self.model = YOLO(self.config['model']['path'])
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
        self.red_zone = Zone('red', (0, 0, 255), self.config['zones']['red']['label'])
        self.alert_threshold = self.config['alert_threshold']
        self.drawing = False
        self.start_point: Optional[Tuple[int, int]] = None
        self.track_data: Dict[int, Dict] = {}

    def mouse_callback(self, event: int, x: int, y: int, flags: int, param: any) -> None:
        """Handle mouse events to draw the red zone."""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.start_point = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and self.drawing:
            self.drawing = False
            self.red_zone.set_points(self.start_point, (x, y))

    def reset(self) -> None:
        """Reset red zone and tracking data."""
        self.red_zone.points = None
        self.red_zone.ready = False
        self.track_data.clear()
        logger.info("Tracker and red zone reset")

    def process_frame(self, frame: np.ndarray) -> Tuple[np.ndarray, Dict]:
        """Process a frame to detect and track people, calculate zone times, and generate alerts."""
        annotated = frame.copy()
        data_summary = {}

        if not self.red_zone.ready:
            cv2.putText(annotated, "Draw RED Zone with mouse", (40, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            return annotated, data_summary

        self.red_zone.draw(annotated)

        try:
            results = self.model.track(annotated, persist=True, verbose=False, classes=[0])
        except Exception as e:
            logger.error(f"Error in YOLO tracking: {e}")
            return annotated, data_summary

        current_time = time.time()
        if results[0].boxes.id is not None:
            ids = results[0].boxes.id.cpu().numpy().astype(int)
            boxes = results[0].boxes.xyxy.cpu().numpy()

            for i, box in enumerate(boxes):
                x1, y1, x2, y2 = map(int, box)
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                track_id = ids[i]
                label = "person"

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

                if person["times"]["red"] > self.alert_threshold and not person["alerted"]:
                    person["alerted"] = True
                    logger.warning(f"Alert: Person {track_id} in red zone for {person['times']['red']:.2f}s")

                color = (0, 0, 255) if current_zone == "red" else (0, 255, 0)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                cv2.putText(annotated, f"P{track_id}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
                if person["alerted"]:
                    cv2.putText(annotated, "ALERT!", (x1, y1 - 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                data_summary[f"P{track_id}"] = {
                    "Label": label,
                    "Current Zone": person["current_zone"],
                    "Red Zone Time (s)": round(person["times"]["red"], 2),
                    "Green Zone Time (s)": round(person["times"]["green"], 2),
                    "Total Time (s)": round(sum(person["times"].values()), 2),
                    "Alert": "Yes" if person["alerted"] else "No"
                }

        return annotated, data_summary