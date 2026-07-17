"""
Modal app for cloud GPU YOLOv8 training.

Usage (from CloudYoloTrainer via subprocess):
    modal run src/models/modal_trainer.py \
        --model-name yolov8n \
        --epochs 50 \
        --val-split 0.2 \
        --run-name run_1718000000

Pre-requisites (one-time user setup):
    pip install modal
    modal setup
"""
import modal
import os

# ── Volume names ───────────────────────────────────────────────
DATA_VOLUME    = "yolo-microscope-data"
WEIGHTS_VOLUME = "yolo-microscope-weights"

# ── App ────────────────────────────────────────────────────────
app = modal.App("yolo-microscope-trainer")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(["ultralytics", "numpy", "pyyaml"])
)

data_volume    = modal.Volume.from_name(DATA_VOLUME,    create_if_missing=True)
weights_volume = modal.Volume.from_name(WEIGHTS_VOLUME, create_if_missing=True)


# ── Remote training function ───────────────────────────────────
@app.function(
    gpu="A10G",
    image=image,
    volumes={
        "/data":    data_volume,
        "/weights": weights_volume,
    },
    timeout=7200,  # 2 hours max
)
def train_yolo(
    model_name: str = "yolov8n",
    epochs: int = 50,
    val_split: float = 0.2,
    run_name: str = "run",
) -> str:
    """
    Reads /data/dataset.zip from the data Volume, trains YOLOv8 on GPU,
    saves best.pt to the weights Volume at /{run_name}/weights/best.pt.
    Progress lines are printed to stdout so the local subprocess can parse them.
    Returns the in-volume path to best.pt.
    """
    import zipfile
    import tempfile
    from ultralytics import YOLO

    print(f"[INFO] Starting: model={model_name} epochs={epochs} "
          f"val_split={val_split} run={run_name}", flush=True)

    with tempfile.TemporaryDirectory() as dataset_dir:
        # 1. Extract dataset
        print("[INFO] Extracting dataset...", flush=True)
        with zipfile.ZipFile("/data/dataset.zip") as zf:
            zf.extractall(dataset_dir)

        # 2. Prepare YOLO folder structure + data.yaml
        yaml_path = _prepare_dataset(dataset_dir, val_split)

        # 3. Train
        output_base = f"/weights/{run_name}"
        model = YOLO(f"{model_name}.pt")
        total = epochs

        def _on_epoch_end(trainer):
            epoch   = trainer.epoch + 1
            metrics = trainer.metrics or {}
            map50   = float(metrics.get("metrics/mAP50(B)", 0.0))
            loss_v  = trainer.loss
            loss    = float(loss_v.item()) if hasattr(loss_v, "item") else float(loss_v)
            # Parseable format for CloudYoloTrainer
            print(f"[EPOCH] {epoch}/{total} mAP50={map50:.4f} loss={loss:.4f}", flush=True)

        model.add_callback("on_train_epoch_end", _on_epoch_end)
        model.train(
            data=yaml_path,
            epochs=epochs,
            imgsz=640,
            device=0,          # GPU
            project=output_base,
            name="weights",
            exist_ok=True,
            verbose=False,
        )

        # 4. Persist to volume
        weights_volume.commit()

    best_volume_path = f"{run_name}/weights/weights/best.pt"
    print(f"[DONE] {best_volume_path}", flush=True)
    return best_volume_path


# ── Dataset preparation (mirrors YoloUtils.prepare_dataset) ────
def _prepare_dataset(source_dir: str, val_split: float = 0.2) -> str:
    import shutil
    import random
    import yaml

    # Load class names
    classes_file = os.path.join(source_dir, "classes.txt")
    if not os.path.exists(classes_file):
        raise FileNotFoundError("classes.txt not found in dataset zip.")
    with open(classes_file) as f:
        class_names = [line.strip() for line in f if line.strip()]
    if not class_names:
        raise ValueError("classes.txt is empty.")

    # Collect images
    images = [
        fn for fn in os.listdir(source_dir)
        if fn.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
    ]
    if not images:
        raise ValueError("No images found in dataset zip.")

    random.shuffle(images)
    val_n      = max(1, int(len(images) * val_split))
    val_imgs   = images[:val_n]
    train_imgs = images[val_n:]

    dataset_out = os.path.join(source_dir, "yolo_dataset")
    for split, imgs in [("train", train_imgs), ("val", val_imgs)]:
        img_dir = os.path.join(dataset_out, split, "images")
        lbl_dir = os.path.join(dataset_out, split, "labels")
        os.makedirs(img_dir, exist_ok=True)
        os.makedirs(lbl_dir, exist_ok=True)
        for img in imgs:
            shutil.copy(os.path.join(source_dir, img), img_dir)
            label_file = os.path.splitext(img)[0] + ".txt"
            label_src  = os.path.join(source_dir, label_file)
            if os.path.exists(label_src):
                shutil.copy(label_src, lbl_dir)

    yaml_path = os.path.join(dataset_out, "data.yaml")
    data = {
        "path":  dataset_out,
        "train": "train/images",
        "val":   "val/images",
        "nc":    len(class_names),
        "names": class_names,
    }
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)

    return yaml_path


# ── Local entrypoint (called by `modal run modal_trainer.py`) ──
@app.local_entrypoint()
def main(
    model_name: str = "yolov8n",
    epochs: int = 50,
    val_split: float = 0.2,
    run_name: str = "run",
):
    """
    Called by CloudYoloTrainer via:
        modal run src/models/modal_trainer.py \
            --model-name yolov8n --epochs 50 \
            --val-split 0.2 --run-name run_<timestamp>
    """
    print(f"[INFO] Dispatching to Modal cloud GPU (A10G)...", flush=True)
    result = train_yolo.remote(
        model_name=model_name,
        epochs=int(epochs),
        val_split=float(val_split),
        run_name=run_name,
    )
    print(f"[DONE] {result}", flush=True)
