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
├── assets/
│   └── css/
│       ├── light.qss            # Light theme (#f8f9fa bg, #2563eb accent)
│       ├── dark.qss             # Dark theme (#1e1e1e bg, #4fc3f7 accent)
│       ├── blue.qss             # Blue theme (#e8f0fe bg, #1a73e8 accent)
│       └── high_contrast.qss    # High contrast (black bg, #ffd700 accent)
│
├── models/
│   ├── device_camera_startup.py # QThread: opens cv2.VideoCapture, emits change_pixmap_signal(QPixmap)
│   └── image_model.py           # Stub: will load images/video, run diff, heatmap, measurement
│
├── presenters/
│   ├── login_presenter.py       # Wires LoginView.login_requested → on_login_success callback
│   ├── main_presenter.py        # Connects MainView signals → MainApplication methods
│   ├── device_camera_presenter.py # Full camera: connect, snapshot, recording, FPS
│   ├── comparison_presenter.py  # Empty stub
│   └── settings_presenter.py    # Wires SettingsView → ThemeManager.apply_theme()
│
├── utils/
│   ├── image_utils.py           # TypeCapture(Enum), TypePlatform(Enum); diff helpers pending
│   └── theme_manager.py         # Scans assets/css/*.qss, applies QSS to QApplication.instance()
│
└── views/
    ├── main_view.py             # MainView(QMainWindow): loads main_window.ui, emits signals for all sidebar buttons
    ├── login_view.py            # LoginView: loads login.ui, emits login_requested on btnLogin
    ├── device_camera_view.py    # DeviceCameraView: full camera UI with combo population, connect/snapshot/record
    ├── settings_view.py         # SettingsView(QDialog): modal theme selector with Apply/Cancel
    ├── image_panel.py           # Empty stub (CanvasLabel for measurement clicks)
    └── ui/
        ├── main_window.ui              # QMainWindow: sidebar (Images, Video, Measure, Settings) + QMdiArea
        ├── login.ui                    # QWidget: username, password, show-pwd checkbox, error label
        ├── camera_view_widget.ui       # QWidget: cmbCamera, btnConnect, lblFeed, btnSnapshot, btnRecord, lblTimer
        ├── settings_dialog.ui          # QDialog: theme title, QGroupBox with QComboBox, preview, Apply/Cancel
        ├── image_comparison_widget.ui  # Two image slots, diff + heatmap results
        ├── video_comparison_widget.ui  # Video loader, two frame pickers, diff/heatmap output
        └── length_measurement_widget.ui # Canvas + scale calibration + measurements table
```

## Main Window Flow

```
QApplication
  └── MainApplication (creates ThemeManager, applies "light" theme on startup)
        ├── LoginView (QWidget shown as top-level window, already themed)
        │     └── LoginPresenter → on_login_success()
        └── MainView (QMainWindow with QMdiArea)
              ├── btnVideo   → opens DeviceCameraView as QMdiSubWindow  [DONE]
              ├── btnImages  → reserved for ImageComparisonWidget        [NOT WIRED]
              ├── btnMeasure → reserved for LengthMeasurementWidget      [NOT WIRED]
              └── btnSettings → opens SettingsView as QDialog modal      [DONE]
```

## UI / Styling

- Global QSS applied via `ThemeManager` from `src/assets/css/*.qss` files.
- 4 themes available: **Light**, **Dark**, **Blue**, **High Contrast**.
- Theme applied to `QApplication.instance().setStyleSheet()` so it covers all widgets including login.
- Adding a new theme: create a new `.qss` file in `src/assets/css/` — `ThemeManager` detects it automatically.
- Key `objectName` values (CSS selectors):
  - Sidebar: `#sidebar`, `#btnImages`, `#btnVideo`, `#btnMeasure`, `#btnSettings`
  - Camera: `#cmbCamera`, `#btnConnect`, `#lblFeed`, `#btnSnapshot`, `#btnRecord`, `#lblTimer`, `#lblFps`, `#lblResolution`
  - Login: `#lineEditUsername`, `#lineEditPassword`, `#chkShowPassword`, `#lblError`, `#btnLogin`
  - Settings: `#cmbTheme`, `#btnApply`, `#btnCancel`

## Key Constraints

- **No business logic in views.** If a view file imports from `models/`, that is a bug.
- **No Qt widgets in models.** QThread is allowed in models; QWidget is not.
- **`.ui` files are the source of truth for layout.**
- **Camera capture runs on a QThread** (`DeviceCameraStartup`). Frame emission must happen inside `run()`, not called from the presenter on the main thread.
- **Themes are `.qss` files in `src/assets/css/`**, not inline styles or Python strings.

## Current State (June 2026)

| Component | Status |
|---|---|
| `main_application.py` | Done |
| `login.ui` + `LoginView` | Done |
| `LoginPresenter` | Done — no credential validation yet |
| `main_window.ui` + `MainView` | Done — sidebar with Images, Video, Measure, Settings + QMdiArea |
| `MainPresenter` | Done — connects video and settings signals |
| `camera_view_widget.ui` | Done |
| `DeviceCameraView` | Done — camera enumeration, connect/disconnect, snapshot, recording |
| `DeviceCameraStartup` (QThread) | Done — capture loop inside `run()`, emits pixmap and raw frames |
| `DeviceCameraPresenter` | Done — full camera lifecycle, FPS display, snapshot to `~/Pictures`, recording with timer |
| `ThemeManager` | Done — scans `*.qss` from `assets/css/`, applies globally |
| `settings_dialog.ui` + `SettingsView` | Done — QDialog modal with theme combo and Apply/Cancel |
| `SettingsPresenter` | Done — connects view selection → `ThemeManager.apply_theme()` |
| `light.qss`, `dark.qss`, `blue.qss`, `high_contrast.qss` | Done — 4 themes, Light applied by default |
| `image_comparison_widget.ui` | Done |
| `video_comparison_widget.ui` | Done |
| `length_measurement_widget.ui` | Done |
| `ImageModel` | Stub |
| `ComparisonPresenter` | Empty |
| `image_panel.py` (CanvasLabel) | Empty |

## Pending Work

### Image Comparison module (btnImages)
- [ ] Implement `ImageModel`: load with OpenCV, compute per-pixel diff, heatmap colormap.
- [ ] Implement `image_utils.py` helper functions.
- [ ] Create `ImageComparisonView` that loads `image_comparison_widget.ui`.
- [ ] Implement `ComparisonPresenter`.
- [ ] Wire `MainView.btnImages` → `MainPresenter` → `MainApplication`.

### Video Comparison module
- [ ] Create `VideoComparisonView` that loads `video_comparison_widget.ui`.
- [ ] Create `VideoComparisonPresenter`.

### Length Measurement module (btnMeasure)
- [ ] Implement `CanvasLabel` (promoted widget with mouse-click tracking) in `image_panel.py`.
- [ ] Create `LengthMeasurementView` that loads `length_measurement_widget.ui`.
- [ ] Create `LengthMeasurementPresenter`.
- [ ] Wire `MainView.btnMeasure` → `MainPresenter` → `MainApplication`.

### Auth
- [ ] Add credential validation to `LoginPresenter._handle_login` (currently lets anyone in).
