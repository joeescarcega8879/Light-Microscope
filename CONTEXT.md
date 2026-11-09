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
│   ├── inference_worker.py      # InferenceWorker (QThread): runs YoloInferencer.predict_frame off the GUI thread; keeps only the latest frame; emits result_ready(frame, detections)
│
├── presenters/
│   ├── login_presenter.py              # Wires LoginView.login_requested → on_login_success callback
│   ├── main_presenter.py               # Connects MainView signals → MainApplication methods
│   ├── device_camera_presenter.py      # Full camera: connect, snapshot, recording, FPS, live YOLO detection overlay (throttled every N frames); reference capture + anomaly/mismatch comparison against the reference (compute_diff on matched crops); stops capture on view_closed
│   ├── image_comparison_presenter.py   # Loads images, runs compute_diff + draw_contours, calls main_app.open_comparison_result_view()
│       ├── yolo_studio_presenter.py        # Annotation: load folder, navigate images, draw/save YOLO-segmentation labels (polygons), confirm/discard the canvas's pending contour; Training: dispatches to YoloTrainer (local), CloudYoloTrainer (Modal), or ColabExporter (Colab export)
│   ├── settings_presenter.py           # Wires SettingsView → ThemeManager.apply_theme()
│   ├── length_measurement_presenter.py # Handles measurement_completed from canvas, scale calibration (px→unit factor), table sync, CSV export
│   └── contour_detection_presenter.py  # Loads a single image, runs ImageUtils.detect_contours() or ImageUtils.detect_shapes() (Hough circles/lines) on param changes, pushes result + stats to view
│
├── utils/
│   ├── image_utils.py           # ImageUtils: compute_diff(), draw_contours(), qpixmap_to_numpy(), open_image_file_dialog(); TypeCapture/TypePlatform enums
│   ├── yolo_utils.py            # YoloUtils: load_labels(), save_labels(), prepare_dataset(), load_class_names(), save_class_names()
│   └── theme_manager.py         # Scans assets/css/*.qss, applies QSS to QApplication.instance()
│
└── views/
    ├── main_view.py                    # MainView(QMainWindow): loads main_window.ui (dashboard grid), emits signals for all buttons
    ├── login_view.py                   # LoginView: loads login.ui, emits login_requested on btnLogin
    ├── device_camera_view.py           # DeviceCameraView: camera UI, live YOLO detection toggle + model loader, reference capture (`reference_requested`) + anomaly check toggle (`anomaly_check_toggled`), emits view_closed on close
    ├── settings_view.py                # SettingsView(QDialog): modal theme selector with Apply/Cancel
    ├── image_comparison_view.py        # ImageComparisonView: loads A/B images, slider, Compare button; emits view_closed
    ├── image_comparison_result_view.py # ImageComparisonResultView: shows diff (grayscale), heatmap (JET), contours (green on img A), stats, Save button
    ├── yolo_studio_view.py             # YoloStudioView: two-tab UI (Annotate + Train); contains LabelingCanvas (custom QWidget — live whole-image contour preview, tunable threshold/Canny, click a contour → polygon annotation, not boxes)
    ├── length_measurement_view.py      # LengthMeasurementView: loads length_measurement_widget.ui, promotes lblCanvas → MeasurementCanvas, wires zoom/scale/table/export; emits view_closed
    ├── image_panel.py                  # MeasurementCanvas(QWidget): paints image + click-to-measure points/lines, zoom in/out/fit, emits measurement_completed(x1,y1,x2,y2) + mouse_moved(x,y)
    ├── contour_detection_view.py       # ContourDetectionView: loads contour_detection_widget.ui, Load Image + threshold/min-area/Hough shape controls, displays result + stats, Save Result; emits view_closed (Canny + min-area controls exist in code/`.ui` but are hidden — `visible: false` — see Known issues)
    └── ui/
        ├── main_window.ui                      # QMainWindow: dashboard grid (Images, Video, Measure, AI Studio, Settings)
        ├── login.ui                            # QWidget: username, password, show-pwd checkbox, error label
        ├── camera_view_widget.ui               # QWidget: cmbCamera, btnConnect, lblFeed, btnSnapshot, btnRecord, lblTimer, btnLoadModelCamera, btnToggleDetection, lblDetectionModel, lblDetectCount, btnSetReference, lblReferenceStatus, sliderAnomalySensitivity, lblAnomalySensitivityValue, btnToggleAnomalyCheck, lblAnomalyStats
        ├── settings_dialog.ui                  # QDialog: theme title, QGroupBox with QComboBox, preview, Apply/Cancel
        ├── image_comparison_widget.ui          # lblImageA/B, btnLoadA/B, btnCompare, sliderThreshold, lblThresholdValue
        ├── image_comparison_result_widget.ui   # lblDiff, lblHeatmap, lblContours, lblStats, btnSaveResult
        ├── yolo_studio_widget.ui               # Two-tab QWidget: Annotate (canvasFrame, lstClasses, lstAnnotations, groupContourParams: rdoAnnThreshold/rdoAnnCanny + threshold/canny/min-area sliders, btnAddAnnotation/btnDiscardAnnotation) + Train (backend selector, model [-seg variants], epochs, val split, progress, log)
        ├── length_measurement_widget.ui        # Canvas (lblCanvas placeholder, promoted to MeasurementCanvas in code) + scale calibration + measurements table
        └── contour_detection_widget.ui         # lblImage, btnLoadImage, method radios (rdoThreshold/rdoCanny/rdoShapes), threshold/canny/min-area/circle-radius/line-length sliders, lblStats, btnSaveResult
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

## Live Detection & Anomaly Check Flow

```
DeviceCameraView (Create Video and Images)
  ├── btnLoadModelCamera → load_model_requested → DeviceCameraPresenter._load_detection_model()
  │     └── YoloInferencer.load_model(path) → enables btnToggleDetection + btnSetReference
  ├── btnToggleDetection → detection_toggled → live YOLO overlay, throttled every _INFERENCE_EVERY_N_FRAMES raw frames
  │     └── YoloInferencer.predict_frame(frame) → self._last_detections → drawn via _draw_detections()
  ├── btnSetReference → reference_requested → DeviceCameraPresenter._on_set_reference()
  │     └── runs one synchronous (non-throttled) predict_frame() on the current raw frame
  │     └── stores reference_frame (copy) + reference_detections → enables btnToggleAnomalyCheck
  │     └── view.set_reference_status("Reference: N piece(s)" / "0 pieces (empty scene)")
  ├── btnToggleAnomalyCheck → anomaly_check_toggled → enables per-frame comparison
  ├── sliderAnomalySensitivity → pixel-diff threshold (1–100, same convention as sliderThreshold elsewhere)
  └── Each throttled inference cycle, when anomaly check is enabled:
        DeviceCameraPresenter._compare_to_reference(frame, detections, reference_frame, reference_detections, sensitivity)
              ↓ groups live + reference detections by class_id
              ↓ nearest-centroid matching per class (cutoff: _MATCH_DISTANCE_CUTOFF)
              ↓ unmatched live detection  → "mismatch" (extra/wrong-class piece)
              ↓ unmatched reference boxes → counted as "missing" (nothing to draw)
              ↓ matched pair → _classify_crop(): crops both frames to the box, ImageUtils.compute_diff() on the crops
              │     → "anomaly" if % changed pixels > _ANOMALY_PIXEL_PCT_CUTOFF, else "ok"
              ↓ view.set_anomaly_stats(f"{ok} ok · {anomaly} anomaly · {mismatch} mismatch · {missing} missing")
        _draw_detections() colors boxes per status: ok = per-class palette, mismatch = red, anomaly = yellow,
              with a "[MISMATCH]"/"[ANOMALY]" label suffix.
  Reference + anomaly state resets on disconnect (_stop_capture) — a reconnect may be a different camera or
  drifted lighting, so the user must click Set Reference again after reconnecting.
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
| `detect_shapes` | `(img, min_radius=10, max_radius=100, min_line_length=30, circle_color=(0,255,0), line_color=(0,0,255), thickness=2)` | `(shapes_img, circles, lines)` — Hough Circle + Probabilistic Hough Line Transform |
| `qpixmap_to_numpy` | `(pixmap: QPixmap)` | `np.ndarray BGR` |
| `open_image_file_dialog` | `()` | `str` file path |

## YoloUtils API

| Method | Signature | Returns |
|---|---|---|
| `load_labels` | `(label_path: str)` | `list[tuple]` — list of `(class_id, points)`, `points` a list of normalized `(x, y)` pairs (YOLO-segmentation `.txt` format: `class_id x1 y1 x2 y2 ... xn yn`) |
| `save_labels` | `(labels: list[tuple], label_path: str)` | `None` — writes YOLO-segmentation `.txt` format |
| `prepare_dataset` | `(source_dir, class_names, val_split=0.2)` | `str` — path to generated `data.yaml` |
| `load_class_names` | `(source_dir: str)` | `list[str]` — reads `classes.txt`, empty list if not found |
| `save_class_names` | `(class_names: list[str], source_dir: str)` | `None` — writes `classes.txt` |

## AI Studio Flow

```
YoloStudioView (two tabs)
  │
  ├── Tab: Annotate
  │     LabelingCanvas (custom QWidget — live contour preview over the whole image, click to pick one)
  │       ├── _recompute_contours(): runs ImageUtils.detect_contours() on the ENTIRE current
  │       │     image (_cv_image, via ImageUtils.qpixmap_to_numpy) — same as the standalone
  │       │     Contour Detection module — and draws every contour found (cyan outline), live
  │       ├── set_contour_params() — pushed in from the sliders below on every change (including
  │       │     mid-drag), so moving Threshold/Canny/min-area re-detects instantly, same as
  │       │     ContourDetectionPresenter's live re-run on `detection_params_changed`
  │       ├── Each contour simplified via cv2.approxPolyDP() → normalized polygon points
  │       ├── mousePressEvent → _contour_at(pos): cv2.pointPolygonTest() against every detected
  │       │     contour; the smallest one containing the click is selected (highlighted yellow)
  │       ├── confirm_pending_annotation() / discard_pending_annotation() — commit the
  │       │     selected polygon as (class_id, points) or deselect it
  │       ├── Per-class color palette (8 colors, cycles)
  │       └── annotation_added / annotation_removed / pending_contour_changed signals
  │     Controls: btnLoadFolder, btnPrev, btnNext, btnSaveLabels
  │               lstClasses (add/remove), lineClassName, btnAddClass, btnRemoveClass
  │               lstAnnotations (shows point count per polygon), btnDeleteAnnotation
  │     Contour Detection (tunable, mirrors the standalone Contour Detection module):
  │               rdoAnnThreshold / rdoAnnCanny + sliderAnnThreshold / sliderAnnCannyLow /
  │               sliderAnnCannyHigh / sliderAnnMinArea — live-updates the whole-image preview
  │               lblContourStatus — "Adjust the threshold..." / "Contour selected — click Add Annotation."
  │               btnAddAnnotation / btnDiscardAnnotation — commit or deselect the clicked contour
  │     (The old "Detect with a trained .pt model" button was removed — it duplicated the
  │      live-detection feature already in "Create Video and Images" / DeviceCameraView.)
  │
   └── Tab: Train
        groupBackend — rdoLocal | rdoModal | rdoColab  (training backend selector)
        lblBackendHint — contextual hint per backend (auto-updates on selection)
        cmbModel     — YOLOv8 Nano-Seg | YOLOv8 Small-Seg (segmentation checkpoints — labels
                       are polygons, not boxes; YoloTrainer/CloudYoloTrainer/ColabExporter are
                       unchanged, ultralytics infers task="segment" from the -seg checkpoint)
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
                          ↓ zip dataset_dir → <system temp>/yolo_microscope_upload.zip
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
        btnOpenModelFolder → open_folder() (QDesktopServices) output_dir/run  (or colab_export/ after export)
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
  - Camera: `#cmbCamera`, `#btnConnect`, `#lblFeed`, `#btnSnapshot`, `#btnRecord`, `#lblTimer`, `#lblFps`, `#lblResolution`, `#btnLoadModelCamera`, `#btnToggleDetection`, `#btnSetReference`, `#lblReferenceStatus`, `#sliderAnomalySensitivity`, `#lblAnomalySensitivityValue`, `#btnToggleAnomalyCheck`, `#lblAnomalyStats`
  - Login: `#lineEditUsername`, `#lineEditPassword`, `#chkShowPassword`, `#lblError`, `#btnLogin`
  - Settings: `#cmbTheme`, `#btnApply`, `#btnCancel`
  - Image comparison: `#btnLoadA`, `#btnLoadB`, `#btnCompare`, `#sliderThreshold`, `#lblThresholdValue`
  - Comparison results: `#lblDiff`, `#lblHeatmap`, `#lblContours`, `#lblStats`, `#btnSaveResult`
  - Contour detection: `#btnLoadImage`, `#lblImage`, `#rdoThreshold`, `#rdoCanny`, `#rdoShapes`, `#sliderThreshold`, `#sliderCannyLow`, `#sliderCannyHigh`, `#sliderMinArea`, `#sliderMinRadius`, `#sliderMaxRadius`, `#sliderMinLineLength`, `#lblStats`, `#btnSaveResult`
  - AI Studio Train tab: `#groupBackend`, `#rdoLocal`, `#rdoModal`, `#rdoColab`, `#lblBackendHint`, `#btnStartTraining`, `#btnExportColab`

## Key Constraints

- **No business logic in views.** If a view file imports from `models/`, that is a bug.
- **No Qt widgets in models.** QThread is allowed in models; QWidget is not.
- **`.ui` files are the source of truth for layout.**
- **Camera capture runs on a QThread** (`DeviceCameraStartup`). Frame emission must happen inside `run()`, not called from the presenter on the main thread.
- **Themes are `.qss` files in `src/assets/css/`**, not inline styles or Python strings.
- **Every secondary view must emit `view_closed` in `closeEvent`** so `MainApplication` can show the dashboard again.

## Current State (July 2026)

| Component | Status |
|---|---|
| `main_application.py` | Done — login flow, dashboard, opens all secondary views, `open_comparison_result_view()` |
| `login.ui` + `LoginView` | Done |
| `LoginPresenter` | Done — no credential validation yet |
| `main_window.ui` + `MainView` | Done — dashboard grid (2×3, one cell open), no MDI |
| `MainPresenter` | Done — connects video, image comparison, measurement, AI Studio, contour detection, and settings signals |
| `camera_view_widget.ui` + `DeviceCameraView` | Done — camera enumeration, connect/disconnect, snapshot, recording, load detection model, toggle live detection, Set Reference + anomaly sensitivity slider + toggle anomaly check, `view_closed` |
| `DeviceCameraStartup` (QThread) | Done — capture loop inside `run()`, emits pixmap and raw frames |
| `DeviceCameraPresenter` | Done — full camera lifecycle, FPS display, snapshot to `~/Pictures`, recording with timer, live YOLO detection overlay (throttled), reference capture + per-frame mismatch/anomaly comparison (`_compare_to_reference`, `_classify_crop`) against the reference via `ImageUtils.compute_diff()`, stops capture + resets reference state on `view_closed` |
| `ThemeManager` | Done — scans `*.qss` from `assets/css/`, applies globally |
| `settings_dialog.ui` + `SettingsView` | Done — QDialog modal with theme combo and Apply/Cancel |
| `SettingsPresenter` | Done |
| `light.qss`, `dark.qss`, `blue.qss`, `high_contrast.qss` | Done — 4 themes, Light applied by default |
| `image_comparison_widget.ui` + `ImageComparisonView` | Done — loads A/B, slider with live label, Compare, `view_closed` |
| `image_comparison_result_widget.ui` + `ImageComparisonResultView` | Done — diff, heatmap, contours panels, stats, Save button |
| `ImageComparisonPresenter` | Done — null guard, compute_diff, draw_contours, stats, opens result view |
| `ImageUtils` | Done — `compute_diff()`, `draw_contours()`, `qpixmap_to_numpy()`, `open_image_file_dialog()` |
| `yolo_studio_widget.ui` + `YoloStudioView` | Done — two-tab UI, `LabelingCanvas` custom widget (drag region → tunable contour detection → confirm/discard polygon), backend selector (Local/Modal/Colab), `view_closed`. The old "Detect with a trained .pt model" button was removed (duplicated the camera's live detection). |
| `YoloStudioPresenter` | Done — folder loading, image navigation, polygon label save/load, class management, confirm/discard pending contour, training dispatch to all three backends |
| `YoloTrainer` (QThread) | Done — ultralytics YOLOv8 training, epoch callbacks, emits progress/finished/failed signals; unchanged for segmentation — task is inferred from the `-seg.pt` checkpoint passed in as `model_name` |
| `CloudYoloTrainer` (QThread) | Done — Modal cloud GPU training; zip→upload→run→download; emits same signals as `YoloTrainer`; unchanged for segmentation (same as above) |
| `modal_trainer.py` | Done — Modal app (A10G GPU); reads dataset from Volume, trains, emits `[EPOCH]` lines, saves weights to Volume; unchanged for segmentation |
| `ColabExporter` | Done — generates `dataset.zip` + pre-configured `colab_trainer.ipynb`; runs synchronously on main thread; unchanged for segmentation |
| `YoloInferencer` | Done — `load_model()`, `predict()` (image file), `predict_frame()` (numpy BGR); only used by camera live detection now (AI Studio's own "Detect" button was removed). Reads `result.boxes` only — works unchanged whether the loaded checkpoint is a detect or `-seg` model. |
| `YoloUtils` | Done — `load_labels()`, `save_labels()` (YOLO-segmentation polygon format: `class_id x1 y1 ... xn yn`), `prepare_dataset()`, `load_class_names()`, `save_class_names()` |
| `length_measurement_widget.ui` + `LengthMeasurementView` | Done — canvas promoted from `lblCanvas`, zoom in/out/fit, scale calibration, measurements table, CSV export, `view_closed` |
| `LengthMeasurementPresenter` | Done — scale factor calc, table sync, delete/clear, CSV export |
| `MeasurementCanvas` (`src/views/image_panel.py`) | Done — custom `QWidget` with `paintEvent`, click-to-measure two points, zoom, `measurement_completed`/`mouse_moved` signals |
| `contour_detection_widget.ui` + `ContourDetectionView` | Done — load image, threshold/Hough-shapes method toggle, circle radius + line length sliders, live-updating result + stats, Save Result, `view_closed`. Canny controls + the min-area "Filter" group are hidden (`visible: false`) but still fully wired in code — see Known issues. |
| `ContourDetectionPresenter` | Done — loads image via `cv2.imread`, re-runs `ImageUtils.detect_contours()` or `ImageUtils.detect_shapes()` on every param change |
| `ImageModel` | Stub |

## Pending Work

### AI Studio annotation — migrated to segmentation, 2026-07-23
`LabelingCanvas` no longer saves hand-dragged rectangles. It now runs `ImageUtils.detect_contours()`
on the whole current image live — same as the standalone Contour Detection module — via the new
`groupContourParams` panel (Binary Threshold / Canny + min-area sliders); every detected contour
is outlined on the canvas as you tune the threshold. Clicking a contour selects it
(`cv2.pointPolygonTest` picks the smallest one under the cursor); the resulting polygon
(simplified with `cv2.approxPolyDP`) becomes the annotation once confirmed via
`btnAddAnnotation`. Labels are now YOLO-segmentation format (`class_id x1 y1 ... xn yn`),
not boxes — see `YoloUtils.load_labels`/`save_labels`. The Train tab's model dropdown now
offers `yolov8n-seg`/`yolov8s-seg`; `YoloTrainer`, `CloudYoloTrainer`, `modal_trainer.py`, and
`ColabExporter` needed **no changes** — ultralytics infers `task="segment"` from the `-seg.pt`
checkpoint. The old "Detect with a trained .pt model" button (in Annotate) was also removed —
it duplicated the live-detection feature in "Create Video and Images"; `YoloInferencer` is now
only used by `DeviceCameraPresenter`, unaffected by this change since it only reads
`result.boxes` (present on both detect and segment results).

### Contour Detection — Canny/Filter Area hidden, 2026-07-23
`rdoCanny`, `sliderCannyLow/High`, and the `groupFilter` (min-area) box are set to
`visible: false` in `contour_detection_widget.ui` at the user's request — the underlying
Python code (`get_use_canny()`, `get_canny_low/high()`, `get_min_area()`,
`ImageUtils.detect_contours()`'s `use_canny`/`min_area` params) is untouched and still wired,
just unreachable from the UI. `rdoThreshold` is the only reachable method alongside
`rdoShapes` (Hough circles/lines).

### Video module — resolved 2026-07-21
Real-time model-based comparison landed inside the existing **"Create Video and Images"** module (`btnVideo` → `DeviceCameraView`/`DeviceCameraPresenter`) — see `## Live Detection & Anomaly Check Flow` above. No new view was added. The `video_comparison_widget.ui` file was removed; that recorded-video-frame-diff workflow was explicitly rejected in favor of the live reference/anomaly check.

### Auth
- [ ] Add credential validation to `LoginPresenter._handle_login` (currently lets anyone in).

### Known issues
- [ ] `ImageComparisonResultView._save_result()` hardcodes `~/Pictures/mis_monedas` as the save directory — should use `~/Pictures` or be configurable.
- [x] `src/presenters/comparison_presenter.py` was an empty (0-byte) dead file — deleted.
- [x] `yolov8n.pt` (base YOLOv8 weights, ~6.5MB) moved from the repo root to `models/yolov8n.pt`; `YoloTrainer` now resolves the weights path from that folder instead of the process cwd.
- [x] `length_measurement_widget.ui` used `<number>` (int) tags for `spinKnownPixels`/`spinRealLength` min/max/value, which are float properties on `QDoubleSpinBox` — PyQt6's `uic` raised `ValueError` trying to parse decimals. Changed to `<double>` tags.

## Infrastructure (Phase 0)

- **Live inference threading**: `DeviceCameraPresenter._on_raw_frame` only *submits* every Nth frame to `src/models/inference_worker.py` (`InferenceWorker`, a QThread that keeps just the latest frame). Results return via `result_ready(frame, detections)` → `_on_inference_result`, which also runs the reference/anomaly comparison on the frame the detections belong to. The worker starts when detection is enabled with a model loaded, and stops on disable / camera stop.
- **Logging**: `src/utils/logging_config.py` (`setup_logging()` in `main_application.py`) → console + rotating file `~/.light_microscope/logs/light_microscope.log`. Use `log = logging.getLogger(__name__)`, not `print`.
- **Settings**: `src/utils/app_settings.py` wraps `QSettings` (theme persisted; `get_last_dir`/`set_last_dir` helpers available).
- **Platform helpers**: `src/utils/platform_utils.py` — `open_folder()` (cross-platform) and `default_torch_device()` (cuda → mps → cpu), used by `YoloTrainer`.
- **Tests**: `tests/` (pytest, headless via `QT_QPA_PLATFORM=offscreen`); CI in `.github/workflows/ci.yml`. Weights (`*.pt`) are gitignored.

## Part Inspection (Phase 1)

Batch "compare against golden reference → OK/NG" workflow. Dashboard button `btnInspect` → `MainApplication.open_part_inspection_view`.

- **Engine** (`src/inspection/engine.py`, pure OpenCV/NumPy, no Qt): `align_image` (ORB + RANSAC similarity transform, ECC fallback for featureless images; scale sanity-checked; near-identity skips warping), `inspect_image` (align → ROI mask ∩ valid-warp mask → brightness/contrast match → blur → absdiff → threshold → morphological open → connected components filtered by `min_defect_area` → verdict), `inspect_against_references` (several goldens; a part passes if ANY matches; best = fewest defect px). `InspectionParams` (verdict rules: NG if `defects > max_defects` or area % > `max_defect_area_pct`) and `Roi` (normalized rects, `include`/`ignore`) serialize to JSON. Alignment failure is a *warning*, not a verdict change.
- **References** (`src/inspection/reference.py`): `ReferenceStore` keeps `~/.light_microscope/references/<name>/{golden_NNN.png, reference.json}`; names are sanitized (no path traversal).
- **Batch** (`src/inspection/batch.py`): `run_batch` → `BatchSummary`; NG originals + `<name>_diff.png` go to `<out>/NG/`, optional `<out>/OK/`, always `<out>/results.csv`. One unreadable file becomes an `ERROR` row, never aborts the batch. Runs off the GUI thread in `src/models/batch_inspection_worker.py`.
- **UI**: `PartInspectionView` (built in code, not a `.ui`) + `RoiCanvas` (drag = ROI in current mode, right-click = delete) + `PartInspectionPresenter`. The old `ImageComparisonPresenter` now calls `inspect_image` (image B aligned onto A; no more same-size error).
- Tests: `tests/test_inspection_*.py`, `tests/test_part_inspection_ui.py`. `tests/conftest.py` redirects `QSettings` to a temp file so tests never touch real user settings.

## Data, users and reporting (Phase 2)

- **Database** (`src/data/database.py`): SQLite at `~/.light_microscope/light_microscope.db`, versioned with `PRAGMA user_version` and the `_MIGRATIONS` list (append a new script to migrate; never edit old ones). Tables: `users`, `batches`, `inspections` (FK cascade on batch delete), `audit_log`. Timestamps are *local* time text so `date(ts)` groups by local day.
- **Auth** (`src/data/auth.py`): PBKDF2-SHA256 (240k iterations, per-user salt), same error for unknown user / wrong password, lock for 60 s after 5 failures, the last active admin cannot be demoted or disabled. `PERMISSIONS` maps permission → minimum role (`operator < supervisor < admin`); check with `session.can("...")`, never by comparing role strings in UI code.
- **Session** (`src/data/session.py`): the signed-in user + `audit(action, detail)`. `MainApplication.session` is replaced on login/sign-out; presenters receive it in their constructor.
- **History** (`src/data/history.py`): `record_batch` (one transaction), `query_inspections`/`list_batches` with `Filters`, `stats` (reject rate = NG / (OK+NG); errors excluded), CSV export neutralises spreadsheet formulas.
- **Login flow**: `LoginPresenter` switches `LoginView` to *setup mode* (confirm-password field) when there are no users, creating the first admin.
- **Permissions in the UI**: `MainView.apply_permissions`, `PartInspectionView.set_editing_enabled` (also stops operators persisting rule changes when they press Run), `HistoryView.set_can_export/set_can_delete/set_audit_visible`. The presenter re-checks the permission before acting; disabling a button is not security.
- **Reports** (`src/utils/pdf_report.py`): QTextDocument → QPdfWriter, no extra dependency. Do NOT call `doc.setPageSize(...)` with the writer's size (QPdfWriter is 1200 dpi; this shrinks everything to a sliver — there is a regression test). All dynamic text is HTML-escaped.
- **Recipes**: `ReferenceStore.export_zip/import_zip` (flat archive, only `golden_NNN.png` + `reference.json` are extracted — zip-slip safe).
- **Charts**: `src/views/charts.py` (`StackedBarChart`, `HBarChart`) painted with QPainter; no matplotlib.
- Tests: `test_data_layer.py`, `test_pdf_report.py`, `test_app_flow.py` (login → roles → batch → history → sign-out through the real `MainApplication`).
