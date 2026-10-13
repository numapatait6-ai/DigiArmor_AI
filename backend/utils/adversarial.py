"""
DIGIARMOR AI - Adversarial Image Protection (EfficientNetB0 surrogate)
Uses ART's FastGradientMethod with a lightweight ImageNet classifier.
"""
import os
import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications import EfficientNetB0
from tensorflow.keras.applications.efficientnet import preprocess_input
from art.estimators.classification import TensorFlowV2Classifier
from art.attacks.evasion import FastGradientMethod

# Lazy-load the surrogate model
_surrogate_model = None
_INPUT_SIZE = 224

def _get_model():
    global _surrogate_model
    if _surrogate_model is None:
        _surrogate_model = EfficientNetB0(
            weights='imagenet',
            include_top=True,
            input_shape=(_INPUT_SIZE, _INPUT_SIZE, 3)
        )
        _surrogate_model.trainable = False
    return _surrogate_model

def generate_adversarial_noise(
    image_array: np.ndarray,
    epsilon: float =  0.00002,
    target_class: int = None
) -> np.ndarray:
    """
    Apply FGSM while preserving the original image quality.
    The adversarial perturbation is generated at 224x224
    and then applied to the ORIGINAL resolution image.
    """

    # Convert BGR to RGB
    rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]

    # Resize only for the EfficientNet model
    resized = cv2.resize(rgb, (_INPUT_SIZE, _INPUT_SIZE))

    # Normalize to 0-1
    input_batch = np.expand_dims(
        resized.astype(np.float32) / 255.0,
        axis=0
    )

    model = _get_model()

    classifier = TensorFlowV2Classifier(
        model=model,
        loss_object=tf.keras.losses.CategoricalCrossentropy(from_logits=False),
        input_shape=(_INPUT_SIZE, _INPUT_SIZE, 3),
        nb_classes=1000,
        clip_values=(0.0, 1.0)
    )

    # Generate adversarial image
    if target_class is None:
        attack = FastGradientMethod(
            estimator=classifier,
            eps=epsilon,
            targeted=False
        )
        adv_batch = attack.generate(x=input_batch)
    else:
        attack = FastGradientMethod(
            estimator=classifier,
            eps=epsilon,
            targeted=True
        )

        y_target = np.zeros((1, 1000))
        y_target[0, target_class] = 1.0

        adv_batch = attack.generate(
            x=input_batch,
            y=y_target
        )

    # Get ONLY the adversarial perturbation
    perturbation = adv_batch[0] - input_batch[0]

    # Resize the perturbation to the ORIGINAL image resolution
    perturbation = cv2.resize(
        perturbation,
        (w, h),
        interpolation=cv2.INTER_LINEAR
    )

    # Apply tiny perturbation to ORIGINAL image
    original_float = rgb.astype(np.float32) / 255.0

    protected = original_float + perturbation

    # Keep valid pixel range
    protected = np.clip(protected, 0.0, 1.0)

    # Convert back to 0-255
    protected_255 = (protected * 255.0).astype(np.uint8)

    # Convert RGB back to BGR
    protected_bgr = cv2.cvtColor(
        protected_255,
        cv2.COLOR_RGB2BGR
    )

    return protected_bgr

def apply_adversarial_protection(
    image_path: str,
    output_path: str,
    epsilon: float = 0.0001
) -> dict:
    """Apply protection and return metrics."""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    protected = generate_adversarial_noise(img, epsilon)

    psnr = cv2.PSNR(img, protected)
    diff = np.abs(img.astype(np.float32) - protected.astype(np.float32))
    max_diff = float(np.max(diff))
    mean_diff = float(np.mean(diff))

    cv2.imwrite(
    output_path,
    protected,
    [cv2.IMWRITE_JPEG_QUALITY, 100]
)

    return {
        "psnr": round(psnr, 2),
        "max_perturbation": round(max_diff, 4),
        "mean_perturbation": round(mean_diff, 4),
        "epsilon": epsilon,
        "original_shape": list(img.shape),
        "protection_applied": True
    }

def simulate_deepfake_resistance(original_path: str, protected_path: str) -> dict:
    """Compare deepfake detection probabilities using the current DigiArmor detector."""

    from utils.deepfake_detect import run_full_deepfake_detection

    # Run the same Claude-selected ensemble on both images
    orig_result = run_full_deepfake_detection(original_path)
    prot_result = run_full_deepfake_detection(protected_path)

    # Get probabilities
    orig_prob = orig_result.get("deepfake_probability")
    prot_prob = prot_result.get("deepfake_probability")

    # If either image could not be analysed
    if orig_prob is None or prot_prob is None:
        return {
            "original_ai_reuse_percent": None,
            "protected_ai_reuse_percent": None,
            "reduction_percent": None,
            "protection_effectiveness": "UNABLE TO ANALYZE",
            "original_prediction": orig_result.get(
                "prediction", "UNKNOWN"
            ),
            "protected_prediction": prot_result.get(
                "prediction", "UNKNOWN"
            ),
            "original_status": orig_result.get("status"),
            "protected_status": prot_result.get("status"),
        }

    orig_prob = float(orig_prob)
    prot_prob = float(prot_prob)

    # Calculate reduction
    reduction = max(0.0, orig_prob - prot_prob)

    reduction_percent = (
        reduction / (orig_prob + 1e-8)
    ) * 100.0

    return {
        "original_ai_reuse_percent": round(
            orig_prob * 100, 1
        ),
        "protected_ai_reuse_percent": round(
            prot_prob * 100, 1
        ),
        "reduction_percent": round(
            min(100.0, reduction_percent), 1
        ),
        "protection_effectiveness": (
            "HIGH"
            if reduction_percent > 60
            else "MEDIUM"
            if reduction_percent > 30
            else "LOW"
        ),
        "original_prediction": orig_result.get(
            "prediction", "UNKNOWN"
        ),
        "protected_prediction": prot_result.get(
            "prediction", "UNKNOWN"
        ),
        "original_status": orig_result.get("status"),
        "protected_status": prot_result.get("status"),
    }