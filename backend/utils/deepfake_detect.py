"""
DigiArmor AI - Still-image deepfake detection (face-focused ensemble).

Pipeline:
  image -> validate/convert to RGB -> MTCNN face detection -> square crop with margin
        -> exact model preprocessing -> ViT classifiers -> softmax
        -> verified fake probability -> weighted average -> risk classification

Every number returned comes from model inference or from the face detector.
"""
import os
import logging
import threading
import io

from typing import Dict, List, Optional

import numpy as np
import torch
import cv2

from PIL import Image, ImageOps
from transformers import ViTForImageClassification
from scipy.fftpack import dct

logger = logging.getLogger("digiarmor.deepfake")

# =====================================================================
# CONFIGURATION (all tunable)
# =====================================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
CACHE_DIR = os.path.join(BASE_DIR, "model_cache")

# Risk thresholds on the ensemble fake-probability estimate
HIGH_RISK_THRESHOLD = 0.80
SUSPICIOUS_THRESHOLD = 0.40

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MIN_IMAGE_SIDE = 64            # px; smaller images are rejected
MAX_DETECTION_SIDE = 1280      # large images are downscaled ONLY for face detection
FACE_MIN_CONFIDENCE = 0.90     # MTCNN confidence required to count a face
MIN_FACE_SIDE_PX = 48          # smaller faces are analysed but flagged
MAX_FACES = 5                  # max faces analysed per image
CROP_SCALE = 1.3               # square crop side = 1.3 x longest side of the face box
AGGREGATION = "max"            # "max": verdict from the face with highest fake prob
                               # "main": verdict from the largest face only
MODEL_DISAGREEMENT_WARN = 0.40 # warn if the two models differ by more than this
SUM_TOLERANCE = 1e-4

# Verified from each repo's config.json / preprocessor_config.json (see report).
# Labels are NOT hardcoded: the fake index is derived from config.id2label at load time.
MODEL_SPECS = [
    {
        "key": "dima806_vit",
        "display_name": "dima806/deepfake_vs_real_image_detection",
        "repo_id": "dima806/deepfake_vs_real_image_detection",
        "revision": "29e4cf9efc543845610045f6ba7e88e5cf9d9301",
        "input_size": 224,
        "mean": (0.5, 0.5, 0.5),
        "std": (0.5, 0.5, 0.5),
        "weight": 0.5,
        "enabled": True,
        # Only used if a model has a single output logit (not the case here):
        "single_logit_is_fake": None,
    },
    {
        "key": "prithiv_vit_v2",
        "display_name": "prithivMLmods/Deep-Fake-Detector-v2-Model",
        "repo_id": "prithivMLmods/Deep-Fake-Detector-v2-Model",
        "revision": "3a99ae26f52c7ac7c3a53103b6cf3a8b617f7093",
        "input_size": 224,
        "mean": (0.5, 0.5, 0.5),
        "std": (0.5, 0.5, 0.5),
        "weight": 0.5,
        "enabled": True,
        "single_logit_is_fake": None,
    },
]

PREPROCESSING_DESC = (
    "EXIF-corrected RGB -> MTCNN face detection -> square face crop (x%.1f margin) -> "
    "bilinear resize 224x224 -> scale 1/255 -> normalize mean=0.5, std=0.5"
) % CROP_SCALE

_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_LOAD_LOCK = threading.Lock()
_MODELS: Optional[List[dict]] = None
_MTCNN = None


class InvalidImageError(Exception):
    pass


class DeepfakeModelError(Exception):
    pass


# =====================================================================
# MODEL LOADING
# =====================================================================
def _resolve_label_indices(id2label: dict):
    """Derive (fake_idx, real_idx) from the model config. Refuse to guess."""
    if len(id2label) != 2:
        raise DeepfakeModelError(f"Expected 2 labels, config has: {id2label}")
    fake = [int(i) for i, l in id2label.items() if "fake" in str(l).lower()]
    real = [int(i) for i, l in id2label.items() if "fake" not in str(l).lower()]
    if len(fake) != 1 or len(real) != 1:
        raise DeepfakeModelError(f"Cannot unambiguously identify FAKE label in: {id2label}")
    return fake[0], real[0]


def load_models() -> List[dict]:
    """Load (once) all enabled models. Raises DeepfakeModelError on any failure."""
    global _MODELS
    if _MODELS is not None:
        return _MODELS
    with _LOAD_LOCK:
        if _MODELS is not None:
            return _MODELS
        os.makedirs(CACHE_DIR, exist_ok=True)
        bundles = []
        for spec in MODEL_SPECS:
            if not spec["enabled"]:
                continue
            try:
                model = ViTForImageClassification.from_pretrained(
                    spec["repo_id"],
                    revision=spec["revision"],
                    cache_dir=CACHE_DIR,
                    use_safetensors=True,
                )
            except Exception as exc:
                raise DeepfakeModelError(
                    f"Failed to load model '{spec['repo_id']}' (rev {spec['revision'][:8]}): {exc}"
                ) from exc
            model.to(_DEVICE).eval()
            cfg_size = int(getattr(model.config, "image_size", -1))
            if cfg_size != spec["input_size"]:
                raise DeepfakeModelError(
                    f"{spec['repo_id']}: config image_size={cfg_size}, expected {spec['input_size']}"
                )
            id2label = {int(k): v for k, v in model.config.id2label.items()}
            fake_idx, real_idx = _resolve_label_indices(id2label)
            logger.info("Loaded %s | labels=%s | fake_idx=%d", spec["repo_id"], id2label, fake_idx)
            bundles.append({
                "spec": spec,
                "model": model,
                "id2label": id2label,
                "fake_idx": fake_idx,
                "real_idx": real_idx,
            })
        if not bundles:
            raise DeepfakeModelError("No models enabled in MODEL_SPECS.")
        _MODELS = bundles
        return _MODELS


def get_model_info() -> dict:
    bundles = load_models()
    return {
        "model_name": " + ".join(b["spec"]["display_name"] for b in bundles),
        "model_type": ("Ensemble of %d ViT-B/16 image classifiers" % len(bundles))
        if len(bundles) > 1 else "ViT-B/16 image classifier",
        "input_size": [bundles[0]["spec"]["input_size"]] * 2 + [3],
        "preprocessing": PREPROCESSING_DESC,
        "device": str(_DEVICE),
        "models": [
            {
                "name": b["spec"]["display_name"],
                "revision": b["spec"]["revision"],
                "labels": b["id2label"],
                "fake_index": b["fake_idx"],
                "weight": b["spec"]["weight"],
            }
            for b in bundles
        ],
    }


def _get_mtcnn():
    global _MTCNN
    if _MTCNN is None:
        with _LOAD_LOCK:
            if _MTCNN is None:
                from facenet_pytorch import MTCNN
                _MTCNN = MTCNN(
                    keep_all=True, device="cpu", min_face_size=40,
                    thresholds=[0.6, 0.7, 0.7], post_process=False,
                )
    return _MTCNN


# =====================================================================
# IMAGE LOADING / VALIDATION
# =====================================================================
def load_image_rgb(path: str) -> Image.Image:
    if not path or not os.path.isfile(path):
        raise InvalidImageError("Image file not found.")
    ext = os.path.splitext(path)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InvalidImageError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )
    try:
        with Image.open(path) as probe:
            probe.verify()  # detects truncated/corrupt files
        with Image.open(path) as im:
            fmt = im.format
            if fmt not in ALLOWED_FORMATS:
                raise InvalidImageError(f"Unsupported image format '{fmt}'.")
            im.load()
            im = ImageOps.exif_transpose(im)  # respect camera rotation
            has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
            if has_alpha:
                rgba = im.convert("RGBA")
                bg = Image.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.split()[-1])
                rgb = bg
            else:
                rgb = im.convert("RGB")  # handles L (grayscale), P, CMYK, etc.
    except InvalidImageError:
        raise
    except Exception as exc:
        raise InvalidImageError(f"Image is corrupted or unreadable: {exc}") from exc

    w, h = rgb.size
    if min(w, h) < MIN_IMAGE_SIDE:
        raise InvalidImageError(
            f"Image too small ({w}x{h}). Minimum side is {MIN_IMAGE_SIDE}px."
        )
    return rgb


# =====================================================================
# FACE DETECTION / CROPPING
# =====================================================================
def _detect_faces(img: Image.Image) -> List[dict]:
    """Return all faces above FACE_MIN_CONFIDENCE, sorted by area (largest first)."""
    w, h = img.size
    scale = min(1.0, MAX_DETECTION_SIDE / float(max(w, h)))
    det_img = img if scale == 1.0 else img.resize(
        (max(1, round(w * scale)), max(1, round(h * scale))), Image.Resampling.BILINEAR
    )
    boxes, probs = _get_mtcnn().detect(det_img)
    faces = []
    if boxes is None or probs is None:
        return faces
    for b, p in zip(boxes, probs):
        if p is None or float(p) < FACE_MIN_CONFIDENCE:
            continue
        x1, y1, x2, y2 = [float(v) / scale for v in b]
        if (x2 - x1) < 2 or (y2 - y1) < 2:
            continue
        faces.append({"box": (x1, y1, x2, y2), "confidence": float(p)})
    faces.sort(key=lambda f: (f["box"][2] - f["box"][0]) * (f["box"][3] - f["box"][1]), reverse=True)
    return faces


def _crop_square(img: Image.Image, box):
    """Square crop around the face (no aspect distortion), kept fully inside the image."""
    W, H = img.size
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    side = min(max(x2 - x1, y2 - y1) * CROP_SCALE, float(W), float(H))
    left = min(max(cx - side / 2.0, 0.0), W - side)
    top = min(max(cy - side / 2.0, 0.0), H - side)
    l, t = int(round(left)), int(round(top))
    s = max(1, min(int(round(side)), W - l, H - t))
    return img.crop((l, t, l + s, t + s)), (l, t, l + s, t + s)


# =====================================================================
# INFERENCE
# =====================================================================
def _preprocess(face: Image.Image, spec: dict) -> torch.Tensor:
    size = spec["input_size"]
    img = face.resize((size, size), Image.Resampling.BILINEAR)  # resample=2 in preprocessor_config
    arr = np.asarray(img, dtype=np.float32) / 255.0
    mean = np.array(spec["mean"], dtype=np.float32)
    std = np.array(spec["std"], dtype=np.float32)
    arr = (arr - mean) / std
    return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).contiguous()


def _logits_to_probs(logits: torch.Tensor, bundle: dict):
    """Convert raw output to (fake_p, real_p). Supports 2-class softmax and 1-logit sigmoid."""
    if not torch.isfinite(logits).all():
        raise DeepfakeModelError("Model produced non-finite output.")
    if logits.numel() == 2:
        p = torch.softmax(logits, dim=0)
        return float(p[bundle["fake_idx"]]), float(p[bundle["real_idx"]])
    if logits.numel() == 1:
        flag = bundle["spec"]["single_logit_is_fake"]
        if flag is None:
            raise DeepfakeModelError("Single-logit model with unverified output semantics.")
        p1 = float(torch.sigmoid(logits[0]))
        return (p1, 1.0 - p1) if flag else (1.0 - p1, p1)
    raise DeepfakeModelError(f"Unexpected output shape: {tuple(logits.shape)}")


def _run_model(bundle: dict, face: Image.Image) -> dict:
    x = _preprocess(face, bundle["spec"]).to(_DEVICE)
    with torch.inference_mode():
        logits = bundle["model"](pixel_values=x).logits[0].float().cpu()
    fake_p, real_p = _logits_to_probs(logits, bundle)
    if not (0.0 <= fake_p <= 1.0 and 0.0 <= real_p <= 1.0) or abs(fake_p + real_p - 1.0) > SUM_TOLERANCE:
        raise DeepfakeModelError(f"Invalid probabilities: fake={fake_p}, real={real_p}")
    return {
        "raw_logits": [round(float(v), 6) for v in logits],
        "fake_probability": fake_p,
        "real_probability": real_p,
    }


def classify_risk(fake_probability: float):
    if fake_probability >= HIGH_RISK_THRESHOLD:
        return "HIGH RISK", "HIGH"
    if fake_probability >= SUSPICIOUS_THRESHOLD:
        return "SUSPICIOUS", "MEDIUM"
    return "LIKELY AUTHENTIC", "LOW"


_RECOMMENDATIONS = {
    "HIGH": "The model estimates a high probability that this face is AI-generated or manipulated. "
            "Do not rely on this image as proof of identity; verify the source independently. "
            "This is a probability estimate, not proof.",
    "MEDIUM": "The model found signs that may indicate manipulation or AI generation. "
              "Treat with caution and verify the source. This is a probability estimate, not proof.",
    "LOW": "No strong signs of manipulation were found by the model. This does not guarantee "
           "authenticity; newer generators can evade these detectors.",
}


# =====================================================================
# PUBLIC API
# =====================================================================
def _error_result(code: str, message: str) -> dict:
    return {
        "status": "error",
        "error_code": code,
        "message": message,
        "verdict": "ANALYSIS FAILED",
        "prediction": "ANALYSIS FAILED",
        "risk_level": "UNKNOWN",
        "deepfake_probability": None,
        "real_probability": None,
        "confidence": None,
        "confidence_score": None,
        "is_suspicious": None,
        "face_detected": None,
        "indicators": [],
        "recommendation": message,
    }


def run_full_deepfake_detection(image_path: str) -> dict:
    """Analyse a still image. Always returns a JSON-serialisable dict."""
    try:
        bundles = load_models()
        img = load_image_rgb(image_path)
        info = get_model_info()

        all_faces = _detect_faces(img)
        base = {
            "model_name": info["model_name"],
            "model_type": info["model_type"],
            "model_input_size": info["input_size"],
            "preprocessing": info["preprocessing"],
            "image_size": [img.size[0], img.size[1]],
            "thresholds": {"suspicious": SUSPICIOUS_THRESHOLD, "high_risk": HIGH_RISK_THRESHOLD},
        }

        if not all_faces:
            msg = "No face detected. Deepfake analysis could not be reliably performed."
            return {
                **base,
                "status": "no_face",
                "verdict": "NO FACE DETECTED",
                "prediction": "NO FACE DETECTED",
                "risk_level": "UNKNOWN",
                "deepfake_probability": None,
                "real_probability": None,
                "confidence": None,
                "confidence_score": None,
                "is_suspicious": None,
                "face_detected": False,
                "faces_detected": 0,
                "face_confidence": None,
                "message": msg,
                "indicators": [msg],
                "recommendation": "Upload an image containing a clearly visible face.",
            }

        total_faces = len(all_faces)
        analysed = all_faces[:MAX_FACES]
        wsum = sum(b["spec"]["weight"] for b in bundles)

        face_results = []
        for idx, f in enumerate(analysed):
            crop, crop_box = _crop_square(img, f["box"])
            per_model = {b["spec"]["key"]: _run_model(b, crop) for b in bundles}
            fake_p = sum(b["spec"]["weight"] * per_model[b["spec"]["key"]]["fake_probability"] for b in bundles) / wsum
            real_p = sum(b["spec"]["weight"] * per_model[b["spec"]["key"]]["real_probability"] for b in bundles) / wsum
            if abs(fake_p + real_p - 1.0) > SUM_TOLERANCE:
                raise DeepfakeModelError("Ensemble probabilities do not sum to 1.")
            fk = [per_model[k]["fake_probability"] for k in per_model]
            pred, risk = classify_risk(fake_p)
            fw = f["box"][2] - f["box"][0]
            fh = f["box"][3] - f["box"][1]
            face_results.append({
                "face_index": idx,
                "face_box": [round(v, 1) for v in f["box"]],
                "crop_box": list(crop_box),
                "face_confidence": round(f["confidence"], 4),
                "face_side_px": round(min(fw, fh), 1),
                "deepfake_probability": fake_p,
                "real_probability": real_p,
                "prediction": pred,
                "risk_level": risk,
                "model_disagreement": (max(fk) - min(fk)) if len(fk) > 1 else 0.0,
                "models": per_model,
            })

        # Deciding face
        if AGGREGATION == "main":
            main = face_results[0]
        else:
            main = max(face_results, key=lambda r: r["deepfake_probability"])

        fake_p, real_p = main["deepfake_probability"], main["real_probability"]
        pred, risk = main["prediction"], main["risk_level"]
        confidence = fake_p if risk != "LOW" else real_p

        indicators = [
            "%d face(s) detected by MTCNN; %d analysed; verdict based on %s."
            % (total_faces, len(analysed),
               "the face with the highest fake probability" if AGGREGATION == "max" else "the largest face"),
            "Deciding face: MTCNN confidence %.2f, side %.0f px." % (main["face_confidence"], main["face_side_px"]),
        ]
        for b in bundles:
            m = main["models"][b["spec"]["key"]]
            indicators.append("%s -> fake probability %.1f%%" % (b["spec"]["display_name"], m["fake_probability"] * 100))
        warnings = []
        if main["face_side_px"] < MIN_FACE_SIDE_PX:
            warnings.append("Face is very small (<%d px); result may be unreliable." % MIN_FACE_SIDE_PX)
        if main["model_disagreement"] > MODEL_DISAGREEMENT_WARN:
            warnings.append("The two detectors disagree by %.0f percentage points; treat this result as inconclusive."
                            % (main["model_disagreement"] * 100))
        if total_faces > len(analysed):
            warnings.append("Only the %d largest faces were analysed (%d found)." % (len(analysed), total_faces))
        indicators.extend(warnings)

        return {
            **base,
            "status": "success",
            "verdict": pred,
            "prediction": pred,
            "risk_level": risk,
            "deepfake_probability": fake_p,
            "real_probability": real_p,
            "confidence": confidence,
            "confidence_score": confidence,
            "is_suspicious": fake_p >= SUSPICIOUS_THRESHOLD,
            "face_detected": True,
            "faces_detected": total_faces,
            "face_confidence": main["face_confidence"],
            "faces": face_results,
            "warnings": warnings,
            "indicators": indicators,
            "recommendation": _RECOMMENDATIONS[risk],
            "note": "Probabilities are model estimates, not calibrated real-world accuracy.",
        }

    except InvalidImageError as exc:
        return _error_result("INVALID_IMAGE", str(exc))
    except DeepfakeModelError as exc:
        logger.error("Deepfake model error: %s", exc)
        return _error_result("MODEL_ERROR", str(exc))
    except Exception as exc:  # pragma: no cover
        logger.exception("Unexpected deepfake detection failure")
        return _error_result("INTERNAL_ERROR", f"Unexpected error: {exc}")


# Alias for older call sites
detect_deepfake = run_full_deepfake_detection


# =====================================================================
# DIGIARMOR AI - TAMPER DETECTION
# =====================================================================

import io
import cv2


def error_level_analysis(image_path: str, quality: int = 95) -> dict:
    """
    Detect possible image tampering using Error Level Analysis (ELA).
    """

    try:
        original = Image.open(image_path).convert("RGB")

        # Re-save at known JPEG quality
        buf = io.BytesIO()
        original.save(buf, "JPEG", quality=quality)
        buf.seek(0)

        resaved = Image.open(buf).convert("RGB")

        # Convert images to arrays
        orig_arr = np.array(original, dtype=float)
        resaved_arr = np.array(resaved, dtype=float)

        # Calculate pixel difference
        ela = np.abs(orig_arr - resaved_arr)

        # Scale difference for analysis
        ela_scaled = (
            ela * 10
        ).clip(0, 255).astype(np.uint8)

        # ELA statistics
        ela_mean = float(np.mean(ela))
        ela_max = float(np.max(ela))
        ela_std = float(np.std(ela))

        # Convert ELA image to grayscale
        gray_ela = cv2.cvtColor(
            ela_scaled,
            cv2.COLOR_RGB2GRAY
        )

        # Detect high-error regions
        _, thresh = cv2.threshold(
            gray_ela,
            30,
            255,
            cv2.THRESH_BINARY
        )

        tampered_ratio = (
            float(np.sum(thresh > 0))
            / (thresh.shape[0] * thresh.shape[1])
        )

        # Calculate tampering score
        tampering_score = min(
            1.0,
            (ela_mean / 15.0) * 0.4
            + tampered_ratio * 0.6
        )

        return {
            "ela_mean": round(ela_mean, 3),
            "ela_max": round(ela_max, 3),
            "ela_std": round(ela_std, 3),
            "tampered_ratio": round(tampered_ratio, 3),
            "tampering_score": round(tampering_score, 3),
            "tamper_detected": tampering_score > 0.35
        }

    except Exception as e:
        return {
            "error": str(e),
            "tamper_detected": False,
            "tampering_score": 0
        }


def run_tamper_detection(image_path: str) -> dict:
    """
    Tamper / manipulation analysis using the SAME Claude-selected
    two-model ViT ensemble used by deepfake detection.

    This does not load another model.

    Interpretation:
        < 40%  -> AUTHENTIC
        >= 40% -> POSSIBLY MANIPULATED
    """

    try:
        # Reuse the existing Claude detector.
        # This means the same models, MTCNN face detection,
        # preprocessing and ensemble are used.
        result = run_full_deepfake_detection(image_path)

        # ---------------------------------------------------------
        # Handle invalid image
        # ---------------------------------------------------------
        if result.get("status") == "invalid_image":
            return {
                "status": "error",
                "error": result.get(
                    "message",
                    "Cannot load image"
                ),
                "tamper_detected": False,
                "tamper_confidence": 0.0,
                "verdict": "UNABLE TO ANALYZE"
            }

        # ---------------------------------------------------------
        # Handle no-face image
        # ---------------------------------------------------------
        if result.get("status") == "no_face":
            return {
                "status": "no_face",
                "tamper_detected": False,
                "tamper_confidence": None,
                "verdict": "NO FACE DETECTED",
                "message": (
                    "No face detected. AI manipulation analysis "
                    "could not be reliably performed."
                ),
                "recommendation": (
                    "Upload an image containing a clear human face."
                )
            }

        # ---------------------------------------------------------
        # Get ensemble probability
        # ---------------------------------------------------------
        probability = result.get("deepfake_probability")

        if probability is None:
            return {
                "status": "error",
                "tamper_detected": False,
                "tamper_confidence": None,
                "verdict": "UNABLE TO ANALYZE",
                "error": (
                    "The manipulation probability was not "
                    "available."
                )
            }

        probability = float(probability)

        # ---------------------------------------------------------
        # Your requested 40% threshold
        # ---------------------------------------------------------
        if probability >= 0.40:

            tamper_detected = True
            verdict = "POSSIBLY MANIPULATED"
            risk_level = "MEDIUM"

            recommendation = (
                "The image shows a higher probability of "
                "AI-generated or manipulated facial content. "
                "Manual verification is recommended."
            )

        else:

            tamper_detected = False
            verdict = "AUTHENTIC"
            risk_level = "LOW"

            recommendation = (
                "The image has a lower probability of "
                "AI-generated or manipulated facial content. "
                "This does not guarantee authenticity."
            )

        # ---------------------------------------------------------
        # Return a tamper-specific response
        # ---------------------------------------------------------
        return {
            "status": "success",

            "tamper_detected": tamper_detected,

            "tamper_confidence": round(
                probability * 100,
                1
            ),

            "tamper_probability": round(
                probability,
                4
            ),

            "verdict": verdict,

            "risk_level": risk_level,

            "deepfake_probability": round(
                probability,
                4
            ),

            "faces_detected": result.get(
                "faces_detected",
                0
            ),

            "face_confidence": result.get(
                "face_confidence"
            ),

            "faces": result.get(
                "faces",
                []
            ),

            "model_results": result.get(
                "model_results",
                []
            ),

            "warnings": result.get(
                "warnings",
                []
            ),

            "indicators": result.get(
                "indicators",
                []
            ),

            "recommendation": recommendation
        }

    except Exception as e:

        import traceback

        return {
            "status": "error",
            "tamper_detected": False,
            "tamper_confidence": None,
            "verdict": "UNABLE TO ANALYZE",
            "error": str(e),
            "trace": traceback.format_exc()
        }