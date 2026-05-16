# Project Context

Technical reference for contributors and AI assistants working on this codebase.

## Purpose

Desktop tool for researchers who work with light microscopes. The three core workflows are:

1. Comparing two images of the same specimen to detect changes or defects.
2. Comparing two frames within a video recording (e.g., before/after stimulus).
3. Measuring real-world distances in microscope images using a calibrated pixel-to-unit scale.

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.10+ | Rapid development, rich scientific libs |
| UI framework | PyQt6 | Mature, native widgets, Qt Designer support |
| Image processing | OpenCV + NumPy | Standard for scientific imaging |
| UI definition | Qt Designer `.ui` files | Clean separation of layout from logic |

## Architecture: MVP

The project uses **Model-View-Presenter**. Views and Models never talk to each other directly; the Presenter mediates.

```
User action → View → Presenter → Model
                ↑                  |
                └──── update ───────┘
```

- **Views** (`src/views/`) own only Qt widgets and emit signals. Zero business logic.
- **Models** (`src/models/`) are plain Python classes. No Qt imports.
- **Presenters** (`src/presenters/`) connect signals, call model methods, and push results back to the view.

## File Map

```
src/
├── models/
│   └── image_model.py          # ImageModel: loads images/video, runs diff, heatmap, measurement
├── presenters/
│   └── comparison_presenter.py # ComparisonPresenter: wires ImageComparisonWidget ↔ ImageModel
├── utils/
│   └── image_utils.py          # Pure functions: pixel diff, heatmap colormap, px→unit conversion
└── views/
    ├── main_window.py          # MainWindow: loads .ui, switches stackedWidget pages via sidebar
    ├── image_panel.py          # CanvasLabel (promoted widget): handles mouse clicks for measurement
    └── ui/
        ├── main_window.ui              # QMainWindow: sidebar (QWidget) + QStackedWidget
        ├── image_comparison_widget.ui  # Two image slots, controls bar, diff + heatmap results
        ├── video_comparison_widget.ui  # Video loader, two frame pickers, same diff/heatmap output
        └── length_measurement_widget.ui # Canvas + scale calibration panel + measurements table
```

## UI / Styling

- All `.ui` files are **structure only** — no hardcoded colors, borders, or fonts.
- A global Qt stylesheet (QSS) will be applied in Python at startup for the Light clean theme.
- Widget `objectName` values are stable and intended as CSS selectors:
  - Sidebar: `#sidebar`, `#lblAppTitle`, `#btnImages`, `#btnVideo`, `#btnMeasure`
  - Content groups: `#groupImageA`, `#groupImageB`, `#groupDiff`, `#groupHeatmap`, `#groupCalibration`, `#groupMeasurements`
  - Canvas: `#lblCanvas`

## Key Constraints

- **No business logic in views.** If a view file imports from `models/`, that is a bug.
- **No Qt in models.** Models must be testable without a QApplication instance.
- **`.ui` files are the source of truth for layout.** Do not recreate widget hierarchies in Python code — load the `.ui` and promote custom widgets where needed.
- **Pixel diff threshold** is exposed as an integer 1–100 in the UI. Internally it maps to an absolute pixel-channel difference (0–255); the conversion lives in `image_utils.py`.

## Current State (May 2025)

| Component | Status |
|---|---|
| `.ui` layout files | Done |
| MainWindow navigation skeleton | In progress |
| ImageModel | Stub |
| ComparisonPresenter | Stub |
| image_utils | Stub |
| CanvasLabel (measurement clicks) | Stub |
| Global QSS theme | Not started |

## Pending Work

- Implement `ImageModel`: load with OpenCV, compute per-pixel absolute diff, generate heatmap with a colormap, detect bounding boxes around changed regions.
- Implement `image_utils.py`: pure helper functions that the model delegates to.
- Wire `ComparisonPresenter` to `ImageComparisonWidget`.
- Clone the presenter pattern for video and measurement panels.
- Promote `lblCanvas` in `length_measurement_widget.ui` to `CanvasLabel` (custom widget with mouse-click tracking).
- Write and apply the global QSS stylesheet (Light clean theme: `#f8f9fa` background, `#2563eb` accent).
