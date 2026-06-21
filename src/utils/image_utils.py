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
    