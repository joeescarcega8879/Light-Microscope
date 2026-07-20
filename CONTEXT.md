# Project Context

Technical reference for contributors and AI assistants working on this codebase.

## Purpose

Desktop tool for researchers who work with light microscopes. Core workflows:

1. Live camera feed from the microscope with snapshot and video recording.
2. Comparing two images of the same specimen to detect changes or defects.
3. Comparing two frames within a video recording (e.g., before/after stimulus).
4. Measuring real-world distances in microscope images using a calibrated pixel-to-unit scale.

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
- **Models** (`src/models/`) handle data and hardware. No Qt widgets (QThread allowed).
- **Presenters** (`src/presenters/`) connect signals, call model methods, push results back to view.

## Navigation Pattern

The app uses a **dashboard + standalone windows** pattern. No MDI.

```
Login → Dashboard (MainView) hidden ──┐
             ↑                        │ button click
             │ view_closed signal     ↓
             └──────────── Secondary view (standalone QWidget window)
```

- `MainApplication` owns the show/hide logic. When a secondary view opens, the dashboard calls `hide()`; when the view emits `view_closed` (from `closeEvent`), the dashboard calls `show()` again.
- Every secondary view **must** declare `view_closed = pyqtSignal()` and emit it in `closeEvent`.
- `SettingsView` is a `QDialog` (modal) — no hide/show needed.

## File Map

```
main_application.py             # Entry point: QApplication, login → dashboard flow, opens all secondary views

src/
├── assets/
│   └── css/
│       ├── light.qss            # Light theme (#f8f9fa bg, #2563eb accent)
│       ├── dark.qss             # Dark theme (#1e1e1e bg, #4fc3f7 accent)
│       ├── blue.qss             # Blue theme (#e8f0fe bg, #1a73e8 accent)
│       └── high_contrast.qss    # High contrast (black bg, #ffd700 accent)
│
├── models/
│   ├── device_camera_startup.py # QThread: opens cv2.VideoCapture, emits change_pixmap_signal(QPixmap) and raw_frame_signal
│   ├── yolo_trainer.py          # QThread: runs YOLOv8 training via ultralytics; emits epoch_ended, training_finished, training_failed, log_message
│   ├── cloud_yolo_trainer.py    # QThread: trains YOLOv8 on Modal cloud GPU (A10G); same signals as YoloTrainer; zip→upload→run→download
│   ├── modal_trainer.py         # Modal app definition: train_yolo() remote function + local_entrypoint(); GPU A10G, Volumes: yolo-microscope-data / yolo-microscope-weights
│   ├── colab_exporter.py        # ColabExporter.export(): zips dataset + generates pre-configured colab_trainer.ipynb; no QThread (runs on main thread)
│   ├── yolo_inferencer.py       # YoloInferencer: load_model(path), predict(image_path), predict_frame(np_frame); wraps ultralytics YOLO for inference (no QThread)
│   └── image_model.py           # Stub: will load images/video, run diff, heatmap, measurement
│
├── presenters/
│   ├── login_presenter.py              # Wires LoginView.login_requested → on_login_success callback
│   ├── main_presenter.py               # Connects MainView signals → MainApplication methods
│   ├── device_camera_presenter.py      # Full camera: connect, snapshot, recording, FPS, live YOLO detection overlay (throttled every N frames); stops capture on view_closed
│   ├── image_comparison_presenter.py   # Loads images, runs compute_diff + draw_contours, calls main_app.open_comparison_result_view()
│       ├── yolo_studio_presenter.py        # Annotation: load folder, navigate images, draw/save YOLO labels, run detection on current image (YoloInferencer) to pre-fill boxes; Training: dispatches to YoloTrainer (local), CloudYoloTrainer (Modal), or ColabExporter (Colab export)
│   ├── settings_presenter.py           # Wires SettingsView → ThemeManager.apply_theme()
│   ├── length_measurement_presenter.py # Handles measurement_completed from canvas, scale calibration (px→unit factor), table sync, CSV export
│   └── contour_detection_presenter.py  # Loads a single image, runs ImageUtils.detect_contours() on param changes (threshold/canny/min-area), pushes result + stats to view
│
├── utils/
│   ├── image_utils.py           # ImageUtils: compute_diff(), draw_contours(), qpixmap_to_numpy(), open_image_file_dialog(); TypeCapture/TypePlatform enums
│   ├── yolo_utils.py            # YoloUtils: load_labels(), save_labels(), prepare_dataset(), load_class_names(), save_class_names()
│   └── theme_manager.py         # Scans assets/css/*.qss, applies QSS to QApplication.instance()
│
└── views/
    ├── main_view.py                    # MainView(QMainWindow): loads main_window.ui (dashboard grid), emits signals for all buttons
    ├── login_view.py                   # LoginView: loads login.ui, emits login_requested on btnLogin
    ├── device_camera_view.py           # DeviceCameraView: camera UI, live YOLO detection toggle + model loader, emits view_closed on close
    ├── settings_view.py                # SettingsView(QDialog): modal theme selector with Apply/Cancel
    ├── image_comparison_view.py        # ImageComparisonView: loads A/B images, slider, Compare button; emits view_closed
    ├── image_comparison_result_view.py # ImageComparisonResultView: shows diff (grayscale), heatmap (JET), contours (green on img A), stats, Save button
    ├── yolo_studio_view.py             # YoloStudioView: two-tab UI (Annotate + Train); contains LabelingCanvas (custom QWidget)
    ├── length_measurement_view.py      # LengthMeasurementView: loads length_measurement_widget.ui, promotes lblCanvas → MeasurementCanvas, wires zoom/scale/table/export; emits view_closed
    ├── image_panel.py                  # MeasurementCanvas(QWidget): paints image + click-to-measure points/lines, zoom in/out/fit, emits measurement_completed(x1,y1,x2,y2) + mouse_moved(x,y)
    ├── contour_detection_view.py       # ContourDetectionView: loads contour_detection_widget.ui, Load Image + threshold/canny/min-area controls, displays result + stats, Save Result; emits view_closed
    └── ui/
        ├── main_window.ui                      # QMainWindow: dashboard grid (Images, Video, Measure, AI Studio, Settings)
        ├── login.ui                            # QWidget: username, password, show-pwd checkbox, error label
        ├── camera_view_widget.ui               # QWidget: cmbCamera, btnConnect, lblFeed, btnSnapshot, btnRecord, lblTimer, btnLoadModelCamera, btnToggleDetection, lblDetectionModel, lblDetectCount
        ├── settings_dialog.ui                  # QDialog: theme title, QGroupBox with QComboBox, preview, Apply/Cancel
        ├── image_comparison_widget.ui          # lblImageA/B, btnLoadA/B, btnCompare, sliderThreshold, lblThresholdValue
        ├── image_comparison_result_widget.ui   # lblDiff, lblHeatmap, lblContours, lblStats, btnSaveResult
        ├── yolo_studio_widget.ui               # Two-tab QWidget: Annotate (canvasFrame, lstClasses, lstAnnotations, btnLoadModel, sliderConfidence, btnDetect) + Train (backend selector, model, epochs, val split, progress, log)
        ├── video_comparison_widget.ui          # Video loader, two frame pickers, diff/heatmap output
        ├── length_measurement_widget.ui        # Canvas (lblCanvas placeholder, promoted to MeasurementCanvas in code) + scale calibration + measurements table
        └── contour_detection_widget.ui         # lblImage, btnLoadImage, method radios (rdoThreshold/rdoCanny), threshold/canny/min-area sliders, lblStats, btnSaveResult
```

## Application Flow

```
QApplication
  └── MainApplication (creates ThemeManager, applies "light" theme on startup)
        ├── LoginView (top-level window)
        │     └── LoginPresenter → _initialize_main_window()
        └── MainView — Dashboard (2×2 button grid, no MDI)
              ├── btnVideo    → hides dashboard → opens DeviceCameraView (standalone)     [DONE]
              ├── btnImages   → hides dashboard → opens ImageComparisonView (standalone)  [DONE]
              │                                         └── btnCompare → opens ImageComparisonResultView (standalone, on top)
              ├── btnMeasure  → hides dashboard → opens LengthMeasurementView (standalone) [DONE]
              ├── btnAiStudio → hides dashboard → opens YoloStudioView (standalone)       [DONE]
              ├── btnContours → hides dashboard → opens ContourDetectionView (standalone) [DONE]
              └── btnSettings → opens SettingsView as QDialog modal (no hide)             [DONE]
```

## Image Comparison Flow

```
ImageComparisonView
  (load A, load B, set threshold, click Compare)
        ↓ compare_images_requested signal
  ImageComparisonPresenter._process_images()
        ↓ ImageUtils.compute_diff()  → (diff, binary_mask, heatmap)
        ↓ ImageUtils.draw_contours() → contour_img (img_a + green contours)
        ↓ computes stats: changed px / total px (%)
        ↓ main_app.open_comparison_result_view(diff, heatmap, contour_img, stats_text)
  ImageComparisonResultView
        ├── lblDiff     — grayscale absolute difference
        ├── lblHeatmap  — JET colormap heatmap
        ├── lblContours — Image A with green contours of differing regions
        ├── lblStats    — "Changed pixels: N / M  (X%)"
        └── btnSaveResult — saves heatmap pixmap via QFileDialog
```

## ImageUtils API

| Method | Signature | Returns |
|---|---|---|
| `compute_diff` | `(img_a, img_b, threshold=0)` | `(diff: uint8 2D, binary_mask: uint8 2D, heatmap: uint8 3D BGR)` |
| `draw_contours` | `(base_img, binary_mask, color=(0,255,0), thickness=2)` | `np.ndarray BGR` — copy of base_img with contours drawn |
| `detect_contours` | `(img, threshold=127, use_canny=False, canny_low=50, canny_high=150, min_area=0, color=(0,255,0), thickness=2)` | `(contour_img, contours, mask)` — blurs + thresholds/Cannys img, finds contours, filters by min_area, draws them |
| `qpixmap_to_numpy` | `(pixmap: QPixmap)` | `np.ndarray BGR` |
| `open_image_file_dialog` | `()` | `str` file path |

## YoloUtils API

| Method | Signature | Returns |
|---|---|---|
| `load_labels` | `(label_path: str)` | `list[tuple]` — list of `(class_id, cx, cy, w, h)` |
| `save_labels` | `(labels: list[tuple], label_path: str)` | `None` — writes YOLO `.txt` format |
| `prepare_dataset` | `(source_dir, class_names, val_split=0.2)` | `str` — path to generated `data.yaml` |
| `load_class_names` | `(source_dir: str)` | `list[str]` — reads `classes.txt`, empty list if not found |
| `save_class_names` | `(class_names: list[str], source_dir: str)` | `None` — writes `classes.txt` |

## AI Studio Flow

```
YoloStudioView (two tabs)
  │
  ├── Tab: Annotate
  │     LabelingCanvas (custom QWidget — draw bounding boxes with mouse)
  │       ├── mousePressEvent / mouseMoveEvent / mouseReleaseEvent → drag-to-draw rect
  │       ├── Converts screen rect → YOLO normalized coords (cx, cy, w, h)
  │       ├── Per-class color palette (8 colors, cycles)
  │       └── annotation_added / annotation_removed signals
  │     Controls: btnLoadFolder, btnPrev, btnNext, btnSaveLabels
  │               lstClasses (add/remove), lineClassName, btnAddClass, btnRemoveClass
  │               lstAnnotations, btnDeleteAnnotation
  │     Detect (pre-fill boxes with a trained model):
  │               btnLoadModel → YoloStudioPresenter._load_model() → YoloInferencer.load_model(path)
  │               sliderConfidence / lblConfidence — confidence threshold (0–100%)
  │               btnDetect → YoloStudioPresenter._run_detection()
  │                     ↓ YoloInferencer.predict(current image path, confidence)
  │                     ↓ converts detections → (class_id, cx, cy, w, h) tuples
  │                     ↓ canvas.set_annotations() + canvas.set_class_names() → boxes drawn on canvas
  │                     ↓ view.refresh_annotations_list() + set_detect_result(count)
  │
   └── Tab: Train
        groupBackend — rdoLocal | rdoModal | rdoColab  (training backend selector)
        lblBackendHint — contextual hint per backend (auto-updates on selection)
        cmbModel     — YOLOv8 Nano | YOLOv8 Small
        sliderEpochs / sliderValSplit (with live labels)
        lineDatasetPath / lineOutputDir (auto-filled from Annotate tab)
        btnStartTraining → YoloStudioPresenter._start_training()  [Local + Modal]
              ↓ backend == "local"
              │     ↓ YoloUtils.prepare_dataset() → yolo_dataset/data.yaml
              │     ↓ YoloTrainer(QThread).start()
              │           ↓ ultralytics YOLO.train() with on_train_epoch_end callback
              │           ↓ epoch_ended → view.set_training_progress()
              │           ↓ log_message → view.append_log()
              │           ↓ training_finished(best.pt path) → view.set_training_finished()
              │           ↓ training_failed(msg)            → view.set_training_failed()
              └─ backend == "modal"
                    ↓ CloudYoloTrainer(QThread).start()
                          ↓ check modal CLI + auth
                          ↓ zip dataset_dir → /tmp/yolo_microscope_upload.zip
                          ↓ modal volume put yolo-microscope-data → /dataset.zip
                          ↓ modal run modal_trainer.py (subprocess, stdout parsed line by line)
                          │     → [EPOCH] lines → epoch_ended signal (progress bar updates live)
                          │     → all lines    → log_message signal
                          ↓ modal volume get yolo-microscope-weights → local output_dir/best.pt
                          ↓ training_finished(local best.pt) → view.set_training_finished()
        btnExportColab → YoloStudioPresenter._export_for_colab()  [Colab backend only]
              ↓ ColabExporter.export()
                    ↓ zips images + labels + classes.txt → dataset.zip
                    ↓ generates colab_trainer.ipynb (model/epochs/val_split pre-filled)
                    ↓ saves both to colab_export/ inside user-chosen folder
                    ↓ log area shows step-by-step instructions for the user
        btnOpenModelFolder → xdg-open output_dir/run  (or colab_export/ after export)
```

## Length Measurement Flow

```
LengthMeasurementView
  ├── btnLoadImage → ImageUtils.open_image_file_dialog() → canvas.set_image(path)
  ├── MeasurementCanvas (custom QWidget, promoted from lblCanvas placeholder in .ui)
  │     ├── paintEvent draws image scaled by zoom + measurement points/lines
  │     ├── click 1 → pending point (orange) ; click 2 → measurement_completed(x1,y1,x2,y2)
  │     └── mouseMoveEvent → mouse_moved(x,y) → lblCoords
  ├── btnZoomIn / btnZoomOut / btnZoomFit → canvas.zoom_in()/zoom_out()/zoom_fit()
  ├── btnSetScale → LengthMeasurementPresenter._on_set_scale()
  │     └── scale_factor = real_length / known_pixels  → lblScaleInfo, recomputes table unit column
  ├── measurement_completed → presenter computes px_length (hypot), appends table row
  ├── btnDeleteMeasurement → removes selected table row + matching canvas measurement
  ├── btnClearAll → clears table + canvas
  └── btnExportCSV → writes #, Length(px), Length(unit) rows via QFileDialog.getSaveFileName
```

## Contour Detection Flow

```
ContourDetectionView
  ├── btnLoadImage → load_image_requested → ContourDetectionPresenter._on_load_image()
  │     └── cv2.imread(path) → self._image, then runs detection
  ├── groupMethod: rdoThreshold | rdoCanny (mutually exclusive, same QGroupBox parent)
  ├── sliderThreshold / sliderCannyLow / sliderCannyHigh / sliderMinArea
  │     └── valueChanged → detection_params_changed → presenter re-runs detection live
  ├── ContourDetectionPresenter._run_detection()
  │     ↓ ImageUtils.detect_contours(image, threshold, use_canny, canny_low, canny_high, min_area)
  │     ↓ view.display_result(contour_img) — image scaled into lblImage, keeps aspect ratio
  │     ↓ view.set_stats(f"Contours: N   Total area: X px²")
  └── btnSaveResult → saves the displayed result pixmap via QFileDialog (view-local, like ImageComparisonResultView)
```

## UI / Styling

- Global QSS applied via `ThemeManager` from `src/assets/css/*.qss` files.
- 4 themes available: **Light**, **Dark**, **Blue**, **High Contrast**.
- Theme applied to `QApplication.instance().setStyleSheet()` so it covers all widgets including login.
- Adding a new theme: create a new `.qss` file in `src/assets/css/` — `ThemeManager` detects it automatically.
- Key `objectName` values (CSS selectors):
  - Dashboard: `#btnImages`, `#btnVideo`, `#btnMeasure`, `#btnAiStudio`, `#btnSettings`, `#lblTitle`, `#lblSubtitle`
  - Camera: `#cmbCamera`, `#btnConnect`, `#lblFeed`, `#btnSnapshot`, `#btnRecord`, `#lblTimer`, `#lblFps`, `#lblResolution`
  - Login: `#lineEditUsername`, `#lineEditPassword`, `#chkShowPassword`, `#lblError`, `#btnLogin`
  - Settings: `#cmbTheme`, `#btnApply`, `#btnCancel`
  - Image comparison: `#btnLoadA`, `#btnLoadB`, `#btnCompare`, `#sliderThreshold`, `#lblThresholdValue`
  - Comparison results: `#lblDiff`, `#lblHeatmap`, `#lblContours`, `#lblStats`, `#btnSaveResult`
  - Contour detection: `#btnLoadImage`, `#lblImage`, `#rdoThreshold`, `#rdoCanny`, `#sliderThreshold`, `#sliderCannyLow`, `#sliderCannyHigh`, `#sliderMinArea`, `#lblStats`, `#btnSaveResult`
  - AI Studio Train tab: `#groupBackend`, `#rdoLocal`, `#rdoModal`, `#rdoColab`, `#lblBackendHint`, `#btnStartTraining`, `#btnExportColab`

## Key Constraints

- **No business logic in views.** If a view file imports from `models/`, that is a bug.
- **No Qt widgets in models.** QThread is allowed in models; QWidget is not.
- **`.ui` files are the source of truth for layout.**
- **Camera capture runs on a QThread** (`DeviceCameraStartup`). Frame emission must happen inside `run()`, not called from the presenter on the main thread.
- **Themes are `.qss` files in `src/assets/css/`**, not inline styles or Python strings.
- **Every secondary view must emit `view_closed` in `closeEvent`** so `MainApplication` can show the dashboard again.

## Current State (June 2026)

| Component | Status |
|---|---|
| `main_application.py` | Done — login flow, dashboard, opens all secondary views, `open_comparison_result_view()` |
| `login.ui` + `LoginView` | Done |
| `LoginPresenter` | Done — no credential validation yet |
| `main_window.ui` + `MainView` | Done — dashboard grid (2×3, one cell open), no MDI |
| `MainPresenter` | Done — connects video, image comparison, measurement, AI Studio, contour detection, and settings signals |
| `camera_view_widget.ui` + `DeviceCameraView` | Done — camera enumeration, connect/disconnect, snapshot, recording, load detection model, toggle live detection, `view_closed` |
| `DeviceCameraStartup` (QThread) | Done — capture loop inside `run()`, emits pixmap and raw frames |
| `DeviceCameraPresenter` | Done — full camera lifecycle, FPS display, snapshot to `~/Pictures`, recording with timer, live YOLO detection overlay (throttled), stops capture on `view_closed` |
| `ThemeManager` | Done — scans `*.qss` from `assets/css/`, applies globally |
| `settings_dialog.ui` + `SettingsView` | Done — QDialog modal with theme combo and Apply/Cancel |
| `SettingsPresenter` | Done |
| `light.qss`, `dark.qss`, `blue.qss`, `high_contrast.qss` | Done — 4 themes, Light applied by default |
| `image_comparison_widget.ui` + `ImageComparisonView` | Done — loads A/B, slider with live label, Compare, `view_closed` |
| `image_comparison_result_widget.ui` + `ImageComparisonResultView` | Done — diff, heatmap, contours panels, stats, Save button |
| `ImageComparisonPresenter` | Done — null guard, compute_diff, draw_contours, stats, opens result view |
| `ImageUtils` | Done — `compute_diff()`, `draw_contours()`, `qpixmap_to_numpy()`, `open_image_file_dialog()` |
| `yolo_studio_widget.ui` + `YoloStudioView` | Done — two-tab UI, `LabelingCanvas` custom widget, backend selector (Local/Modal/Colab), `view_closed` |
| `YoloStudioPresenter` | Done — folder loading, image navigation, label save/load, class management, run detection to pre-fill boxes, training dispatch to all three backends |
| `YoloTrainer` (QThread) | Done — ultralytics YOLOv8 training, epoch callbacks, emits progress/finished/failed signals |
| `CloudYoloTrainer` (QThread) | Done — Modal cloud GPU training; zip→upload→run→download; emits same signals as `YoloTrainer` |
| `modal_trainer.py` | Done — Modal app (A10G GPU); reads dataset from Volume, trains, emits `[EPOCH]` lines, saves weights to Volume |
| `ColabExporter` | Done — generates `dataset.zip` + pre-configured `colab_trainer.ipynb`; runs synchronously on main thread |
| `YoloInferencer` | Done — `load_model()`, `predict()` (image file), `predict_frame()` (numpy BGR); used by camera live detection and AI Studio "Detect" button |
| `YoloUtils` | Done — `load_labels()`, `save_labels()`, `prepare_dataset()`, `load_class_names()`, `save_class_names()` |
| `video_comparison_widget.ui` | UI file exists, no view/presenter yet |
| `length_measurement_widget.ui` + `LengthMeasurementView` | Done — canvas promoted from `lblCanvas`, zoom in/out/fit, scale calibration, measurements table, CSV export, `view_closed` |
| `LengthMeasurementPresenter` | Done — scale factor calc, table sync, delete/clear, CSV export |
| `MeasurementCanvas` (`src/views/image_panel.py`) | Done — custom `QWidget` with `paintEvent`, click-to-measure two points, zoom, `measurement_completed`/`mouse_moved` signals |
| `contour_detection_widget.ui` + `ContourDetectionView` | Done — load image, threshold/Canny method toggle, min-area filter, live-updating result + stats, Save Result, `view_closed` |
| `ContourDetectionPresenter` | Done — loads image via `cv2.imread`, re-runs `ImageUtils.detect_contours()` on every param change |
| `ImageModel` | Stub |

## Pending Work

### Video Capture module
- [ ] `btnVideo` currently opens `DeviceCameraView` (live feed). Decide: keep as live camera or replace with video comparison.

### Video Comparison module
- [ ] Create `VideoComparisonView` loading `video_comparison_widget.ui`.
- [ ] Create `VideoComparisonPresenter`.
- [ ] Wire `MainView.btnVideo` → `MainApplication`.
- [ ] Add `view_closed` signal to the view.

### Auth
- [ ] Add credential validation to `LoginPresenter._handle_login` (currently lets anyone in).

### Known issues
- [ ] `ImageComparisonResultView._save_result()` hardcodes `~/Pictures/mis_monedas` as the save directory — should use `~/Pictures` or be configurable.
- [x] `src/presenters/comparison_presenter.py` was an empty (0-byte) dead file — deleted.
- [x] `yolov8n.pt` (base YOLOv8 weights, ~6.5MB) moved from the repo root to `models/yolov8n.pt`; `YoloTrainer` now resolves the weights path from that folder instead of the process cwd.
- [x] `length_measurement_widget.ui` used `<number>` (int) tags for `spinKnownPixels`/`spinRealLength` min/max/value, which are float properties on `QDoubleSpinBox` — PyQt6's `uic` raised `ValueError` trying to parse decimals. Changed to `<double>` tags.
