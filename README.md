# Light Microscope

Desktop application for microscopy image and video analysis. Built with Python and PyQt6.

## Features

- **Image Comparison** — Load two images side by side, detect pixel-level differences, and view a difference heatmap with adjustable sensitivity.
- **Video Comparison** — Load a video and select two frames to compare with the same diff/heatmap engine.
- **Length Measurement** — Mark two points on a microscope image and get the real-world distance after calibrating the pixel-to-unit scale (µm, mm, nm, px).

## Requirements

- Python 3.10+
- PyQt6
- OpenCV (`opencv-python`)
- NumPy

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd Light-Microscope

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

Use the sidebar icons to switch between the three analysis panels.

## Project Structure

```
Light-Microscope/
├── main.py                        # Entry point
├── requirements.txt
└── src/
    ├── models/
    │   └── image_model.py         # Image/video data and processing logic
    ├── presenters/
    │   └── comparison_presenter.py # Mediates between views and models
    ├── utils/
    │   └── image_utils.py         # OpenCV helpers (diff, heatmap, scale)
    └── views/
        ├── main_window.py         # Main window shell, sidebar navigation
        ├── image_panel.py         # Custom canvas widget for measurement
        └── ui/
            ├── main_window.ui
            ├── image_comparison_widget.ui
            ├── video_comparison_widget.ui
            └── length_measurement_widget.ui
```

## Architecture

The project follows the **Model-View-Presenter (MVP)** pattern:

| Layer | Responsibility |
|---|---|
| **Model** | Data structures, image loading, diff computation |
| **View** | Qt widgets, `.ui` files, no business logic |
| **Presenter** | Reacts to view events, updates models, pushes results back to views |
