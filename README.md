# Light Microscope

Desktop application (Python + PyQt6) for inspecting small parts under a microscope: compare images, detect and measure contours, and train YOLO models to recognise parts.

## Features

- **Image Comparison**: load two images, get the pixel difference, a heatmap and the changed contours, with adjustable sensitivity.
- **Live camera** ("Create Video and Images"): capture snapshots and video, run a trained YOLO model live (inference runs in a background thread), and flag pieces that differ from a reference frame.
- **AI Studio**: annotate parts (auto-detected contours become segmentation polygons), build a YOLO dataset and train it locally, on Modal cloud GPUs, or export a Google Colab notebook.
- **Contour Detection**: threshold or Canny contours with a minimum-area filter.
- **Length Measurement**: calibrate pixels to µm/mm/nm, measure by two clicks, export to CSV.
- **Themes**: light, dark, blue, high contrast (your choice is remembered).

## Requirements

- Python 3.10+ (developed on 3.11)
- Dependencies in `requirements.txt` (PyQt6, OpenCV, NumPy, PyYAML, ultralytics, modal)
- Optional: a CUDA GPU (local training picks `cuda`, then `mps`, then `cpu` automatically)

## Installation

```bash
git clone <repo-url>
cd Light-Microscope
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Or with conda: `conda env create -f environment.yml`.

## Usage

```bash
python main_application.py
```

YOLO base weights (`yolov8n.pt`, `yolov8s.pt`) are downloaded by ultralytics on first training and stored in `models/` (not tracked in git).

Logs are written to `~/.light_microscope/logs/light_microscope.log`. User settings (theme) are stored with `QSettings`.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Project structure

```
Light-Microscope/
├── main_application.py     # Entry point, window/navigation wiring
├── requirements.txt
├── tests/                  # pytest suite (runs headless)
└── src/
    ├── models/             # Camera thread, inference worker, YOLO train/infer, cloud export
    ├── presenters/         # Logic between views and models
    ├── utils/              # image_utils, yolo_utils, theme/settings/logging helpers
    ├── views/              # Qt widgets (+ ui/ Qt Designer files)
    └── assets/css/         # QSS themes
```

The project follows Model-View-Presenter: views hold widgets only, presenters react to view signals and drive models. See `CONTEXT.md` for contributor details.
