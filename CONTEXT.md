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

## File Map

```
main_application.py             # Entry point: creates QApplication, runs login → main window flow

src/
├── models/
│   ├── device_camera_startup.py  # QThread: opens cv2.VideoCapture, emits change_pixmap_signal(QPixmap)
│   └── image_model.py            # Stub: will load images/video, run diff, heatmap, measurement
│
├── presenters/
│   ├── login_presenter.py        # Wires LoginView.login_requested → on_login_success callback
│   ├── device_camera_presenter.py # Wires DeviceCameraView ↔ DeviceCameraStartup (skeleton)
│   └── comparison_presenter.py   # Empty stub
│
├── utils/
│   └── image_utils.py            # TypeCapture(Enum), TypePlatform(Enum); diff helpers pending
│
└── views/
    ├── main_window.py            # MainWindow: loads .ui, emits video_capture_requested on btnVideo
    ├── login_view.py             # LoginView: loads login.ui, emits login_requested on btnLogin
    ├── device_camera_view.py     # DeviceCameraView: loads camera_view_widget.ui (btnConnect not wired)
    ├── image_panel.py            # Empty stub (CanvasLabel for measurement clicks)
    └── ui/
        ├── main_window.ui              # QMainWindow: sidebar + QMdiArea (dark bg #1e1e1e)
        ├── login.ui                    # QWidget: username, password, show-pwd checkbox, error label
        ├── camera_view_widget.ui       # QWidget: cmbCamera, btnConnect, lblFeed, btnSnapshot, btnRecord, lblTimer
        ├── image_comparison_widget.ui  # Two image slots, diff + heatmap results
        ├── video_comparison_widget.ui  # Video loader, two frame pickers, diff/heatmap output
        └── length_measurement_widget.ui # Canvas + scale calibration + measurements table
```

## Main Window Flow

```
QApplication
  └── MainApplication
        ├── LoginView (QWidget shown as top-level window)
        │     └── LoginPresenter → on_login_success()
        └── MainWindow (QMainWindow with QMdiArea)
              ├── btnVideo   → opens DeviceCameraView as QMdiSubWindow  [NOT WIRED YET]
              ├── btnImages  → opens ImageComparisonWidget as QMdiSubWindow [NOT WIRED YET]
              └── btnMeasure → opens LengthMeasurementWidget as QMdiSubWindow [NOT WIRED YET]
```

## UI / Styling

- All `.ui` files are **structure only** — no hardcoded colors or fonts.
- Global QSS stylesheet pending (Light clean theme: `#f8f9fa` background, `#2563eb` accent).
- Key `objectName` values (CSS selectors):
  - Sidebar: `#sidebar`, `#btnImages`, `#btnVideo`, `#btnMeasure`
  - Camera: `#cmbCamera`, `#btnConnect`, `#lblFeed`, `#btnSnapshot`, `#btnRecord`, `#lblTimer`, `#lblFps`, `#lblResolution`
  - Login: `#lineEditUsername`, `#lineEditPassword`, `#chkShowPassword`, `#lblError`, `#btnLogin`

## Key Constraints

- **No business logic in views.** If a view file imports from `models/`, that is a bug.
- **No Qt widgets in models.** QThread is allowed in models; QWidget is not.
- **`.ui` files are the source of truth for layout.**
- **Camera capture runs on a QThread** (`DeviceCameraStartup`). Frame emission must happen inside `run()`, not called from the presenter on the main thread.

## Current State (May 2026)

| Component | Status |
|---|---|
| `main_application.py` | Done |
| `login.ui` + `LoginView` | Done |
| `LoginPresenter` | Done — no credential validation yet |
| `main_window.ui` + `MainWindow` | Done — sidebar + QMdiArea |
| `camera_view_widget.ui` | Done |
| `DeviceCameraView` | Skeleton — `btnConnect` not connected |
| `DeviceCameraStartup` (QThread) | Done — needs `general_capture()` moved inside `run()` |
| `DeviceCameraPresenter` | Skeleton — has bugs (see Pending Work) |
| `image_comparison_widget.ui` | Done |
| `video_comparison_widget.ui` | Done |
| `length_measurement_widget.ui` | Done |
| `ImageModel` | Stub |
| `ComparisonPresenter` | Empty |
| `image_panel.py` (CanvasLabel) | Empty |
| Global QSS theme | Not started |

## Pending Work

### Camera module (btnVideo)
- [ ] Fix `DeviceCameraStartup.run()`: call `general_capture()` inside `run()` instead of returning after setup.
- [ ] Fix `DeviceCameraPresenter._start_video_capture`: signal emits no args, method signature has `type_capture` — mismatch.
- [ ] Fix `DeviceCameraPresenter.update_image`: call `self.view.lblFeed.setPixmap(pixmap)` not `self.view.setPixmap(pixmap)`.
- [ ] Wire `DeviceCameraView.btnConnect` → signal → `DeviceCameraPresenter`.
- [ ] Wire `MainWindow.btnVideo` → open `DeviceCameraView` as `QMdiSubWindow`.
- [ ] Instantiate `DeviceCameraPresenter` somewhere (currently created nowhere).
- [ ] Implement snapshot (`btnSnapshot`) and recording (`btnRecord` + `lblTimer`).
- [ ] Populate `cmbCamera` with available devices on startup.

### Image Comparison module (btnImages)
- [ ] Implement `ImageModel`: load with OpenCV, compute per-pixel diff, heatmap colormap.
- [ ] Implement `image_utils.py` helper functions.
- [ ] Create `ImageComparisonView` that loads `image_comparison_widget.ui`.
- [ ] Implement `ComparisonPresenter`.
- [ ] Wire `MainWindow.btnImages` → open as `QMdiSubWindow`.

### Video Comparison module
- [ ] Create `VideoComparisonView` that loads `video_comparison_widget.ui`.
- [ ] Create `VideoComparisonPresenter`.

### Length Measurement module (btnMeasure)
- [ ] Implement `CanvasLabel` (promoted widget with mouse-click tracking) in `image_panel.py`.
- [ ] Create `LengthMeasurementView` that loads `length_measurement_widget.ui`.
- [ ] Create `LengthMeasurementPresenter`.
- [ ] Wire `MainWindow.btnMeasure` → open as `QMdiSubWindow`.

### Auth
- [ ] Add credential validation to `LoginPresenter._handle_login` (currently lets anyone in).

### Styling
- [ ] Write and apply global QSS stylesheet.
