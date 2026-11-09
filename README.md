# Light Microscope

Desktop application (Python + PyQt6) for inspecting small parts under a microscope: compare images, detect and measure contours, and train YOLO models to recognise parts.

## Features

- **Part Inspection** (batch OK / NG): save one or more *golden* images of a good part, draw areas to inspect or ignore, set pass/fail rules, then point it at a folder of part images. Parts are auto-aligned to the reference (so they don't need to be placed perfectly), lighting changes and sensor noise are compensated, and every part is judged OK or NG. NG parts are copied to a separate folder with a marked-up difference image, plus a `results.csv`.
- **History & Statistics**: every batch is stored in a local SQLite database. A dashboard shows parts per day, reject rate and the worst references; browse and filter all inspections, export CSV, and generate a **PDF report** per batch (summary, rejected parts, defect images).
- **Users and roles**: first launch asks you to create the administrator account. Roles: *operator* (run inspections, view history), *supervisor* (+ edit references and rules, reports, AI Studio, audit log), *admin* (+ manage users, delete history). Passwords are salted PBKDF2; accounts lock for a minute after 5 failed attempts; important actions are written to an audit log.
- **Recipes**: a reference (golden images + areas + rules) can be exported to one `.zip` and imported on another machine.
- **Image Comparison**: compare two images (the second is auto-aligned onto the first, any size) and get the difference, a heatmap, the changed contours and a verdict.
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

The history database is `~/.light_microscope/light_microscope.db`. Golden references are stored in `~/.light_microscope/references/<name>/` (images + `reference.json` with areas and rules).

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
    ├── data/               # SQLite database, users/roles/auth, history & statistics, session
    ├── inspection/         # Inspection engine (align, diff, OK/NG), reference store, batch runner (no Qt)
    ├── models/             # Camera thread, inference + batch workers, YOLO train/infer, cloud export
    ├── presenters/         # Logic between views and models
    ├── utils/              # image_utils, yolo_utils, theme/settings/logging helpers
    ├── views/              # Qt widgets (+ ui/ Qt Designer files)
    └── assets/css/         # QSS themes
```

The project follows Model-View-Presenter: views hold widgets only, presenters react to view signals and drive models. See `CONTEXT.md` for contributor details.
