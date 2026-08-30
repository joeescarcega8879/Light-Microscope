import cv2
import numpy as np
from enum import Enum
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QFileDialog


class ImageUtils:
    @staticmethod
    def compute_diff(img_a, img_b, threshold=0):
        """
        Compute the difference between two images.

        Returns a tuple (diff, binary_mask, heatmap):
          - diff: grayscale absolute difference (uint8)
          - binary_mask: pixels above threshold set to 255, rest to 0
          - heatmap: JET colormap applied to diff for visualization
        """
        gray_a = cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY)
        gray_b = cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY)

        if gray_a.shape != gray_b.shape:
            raise ValueError("Input images must have the same shape.")

        diff = cv2.absdiff(gray_a, gray_b)
        _, binary_mask = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
        heatmap = cv2.applyColorMap(diff, cv2.COLORMAP_JET)

        return diff, binary_mask, heatmap
    
    @staticmethod
    def draw_contours(base_img: np.ndarray, binary_mask: np.ndarray,
                      color: tuple = (0, 255, 0), thickness: int = 2) -> np.ndarray:
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result = base_img.copy()
        cv2.drawContours(result, contours, -1, color, thickness)
        return result

    @staticmethod
    def detect_contours(img: np.ndarray, threshold: int = 127, use_canny: bool = False,
                        canny_low: int = 50, canny_high: int = 150, min_area: int = 0,
                        color: tuple = (0, 255, 0), thickness: int = 2):
        """
        Detect contours in a single image via binary thresholding or Canny edge detection.

        Returns a tuple (contour_img, contours, mask):
          - contour_img: copy of img with contours (area >= min_area) drawn
          - contours: list of contours with area >= min_area
          - mask: the binary/edge image contours were found on
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        if use_canny:
            mask = cv2.Canny(blurred, canny_low, canny_high)
        else:
            _, mask = cv2.threshold(blurred, threshold, 255, cv2.THRESH_BINARY)

        all_contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [c for c in all_contours if cv2.contourArea(c) >= min_area]

        contour_img = img.copy()
        cv2.drawContours(contour_img, contours, -1, color, thickness)

        return contour_img, contours, mask

    @staticmethod
    def detect_shapes(img: np.ndarray, min_radius: int = 10, max_radius: int = 100,
                      min_line_length: int = 30, circle_color: tuple = (0, 255, 0),
                      line_color: tuple = (0, 0, 255), thickness: int = 2):
        """
        Detect circles (Hough Circle Transform) and straight line segments
        (Probabilistic Hough Line Transform) in a single image.

        Returns a tuple (shapes_img, circles, lines):
          - shapes_img: copy of img with circles (circle_color) and line
            segments (line_color) drawn
          - circles: np.ndarray of (x, y, radius) rows, or None
          - lines: np.ndarray of (x1, y1, x2, y2) rows, or None
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (9, 9), 2)

        circles = cv2.HoughCircles(
            blurred, cv2.HOUGH_GRADIENT, dp=1, minDist=max(min_radius * 2, 20),
            param1=100, param2=30, minRadius=min_radius, maxRadius=max_radius,
        )
        if circles is not None:
            circles = np.round(circles[0, :]).astype(int)

        edges = cv2.Canny(blurred, 50, 150)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180, threshold=50,
            minLineLength=min_line_length, maxLineGap=10,
        )
        if lines is not None:
            lines = lines[:, 0, :]

        shapes_img = img.copy()
        if circles is not None:
            for x, y, r in circles:
                cv2.circle(shapes_img, (x, y), r, circle_color, thickness)
                cv2.circle(shapes_img, (x, y), 2, circle_color, -1)
        if lines is not None:
            for x1, y1, x2, y2 in lines:
                cv2.line(shapes_img, (x1, y1), (x2, y2), line_color, thickness)

        return shapes_img, circles, lines

    @staticmethod
    def qpixmap_to_numpy(pixmap: QPixmap) -> np.ndarray:
        image = pixmap.toImage().convertToFormat(QImage.Format.Format_BGR888)
        width, height = image.width(), image.height()
        ptr = image.bits()
        ptr.setsize(height * width * 3)
        return np.frombuffer(ptr, dtype=np.uint8).reshape((height, width, 3)).copy()

    @staticmethod
    def open_image_file_dialog():
        """
        Open a file dialog to select an image file and return the selected file path.
        Returns:
        str: The file path of the selected image, or an empty string if no file was selected.
        """
        
        file_path, _ = QFileDialog.getOpenFileName(
            None,
            "Select Image",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )
        return file_path

class TypeCapture(Enum):
    Time        = "Time"
    Quantity    = "Quantity"
    General     = "General"

class TypePlatform(Enum):
    Windows     = "Windows"
    Linux       = "Linux"
    MacOS       = "Darwin"
    