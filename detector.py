import cv2
import numpy as np
from ultralytics import YOLO


class ProductDetector:
    """
    VisionWrap object detector using a pretrained YOLO model.

    Supports:
    - Image paths
    - NumPy images
    - OpenCV camera frames

    Returns detected objects with labels, confidence scores,
    bounding boxes, and mapped packaging categories.
    """

    def __init__(self, model_name="yolo11n.pt", confidence=0.15):
        self.model_name = model_name
        self.confidence = confidence

        # Load pretrained YOLO weights.
        # The weights download automatically on first use.
        self.model = YOLO(model_name)

        # COCO classes are used by the pretrained model.
        self.packaging_categories = {
            "cell phone": "electronics",
            "laptop": "electronics",
            "keyboard": "electronics_accessory",
            "mouse": "electronics_accessory",
            "remote": "electronics_accessory",
            "book": "rigid_item",
            "cup": "potentially_fragile",
            "bottle": "potentially_fragile",
            "wine glass": "fragile",
            "vase": "fragile",
            "scissors": "general_item",
            "suitcase": "general_item",
            "handbag": "general_item",
            "backpack": "general_item",
        }

    def detect(self, image):
        """
        Detect objects in an image.

        Args:
            image: Image file path or NumPy image.

        Returns:
            List of dictionaries containing detected object information.
        """

        if image is None:
            raise ValueError("No image was provided.")

        # Convert OpenCV/NumPy image if necessary.
        if isinstance(image, np.ndarray):
            if image.size == 0:
                raise ValueError("The provided image is empty.")

            # OpenCV images are normally BGR.
            # Convert to RGB for consistent model input.
            if len(image.shape) == 3 and image.shape[2] == 3:
                image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        results = self.model.predict(
            source=image,
            conf=self.confidence,
            verbose=False
        )

        detections = []

        for result in results:
            if result.boxes is None:
                continue

            for box in result.boxes:
                class_id = int(box.cls[0].item())
                confidence = float(box.conf[0].item())

                label = self.model.names[class_id]

                x1, y1, x2, y2 = (
                    int(value)
                    for value in box.xyxy[0].tolist()
                )

                category = self.packaging_categories.get(
                    label,
                    "general_item"
                )

                detections.append({
                    "label": label,
                    "class_name": label,
                    "category": category,
                    "confidence": round(confidence, 4),
                    "bbox": [x1, y1, x2, y2],
                    "width_px": max(0, x2 - x1),
                    "height_px": max(0, y2 - y1),
                })

        return detections

    def detect_objects(self, image):
        """
        Compatibility alias for code using detect_objects().
        """
        return self.detect(image)

    def detect_from_path(self, image_path):
        """
        Detect objects directly from an image file path.
        """
        return self.detect(image_path)

    def detect_from_frame(self, frame):
        """
        Detect objects from a camera frame.
        """
        return self.detect(frame)

    def draw_detections(self, image, detections):
        """
        Draw detection boxes and labels on an image.

        Returns:
            Image with bounding boxes and labels.
        """

        if image is None:
            raise ValueError("No image was provided.")

        output = image.copy()

        for detection in detections:
            x1, y1, x2, y2 = detection["bbox"]

            label = detection["label"]
            confidence = detection["confidence"]

            text = f"{label}: {confidence:.0%}"

            cv2.rectangle(
                output,
                (x1, y1),
                (x2, y2),
                (0, 200, 0),
                2
            )

            cv2.putText(
                output,
                text,
                (x1, max(20, y1 - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 200, 0),
                2,
                cv2.LINE_AA
            )

        return output