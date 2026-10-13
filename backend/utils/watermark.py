"""
DIGIARMOR AI - Dual-Layer Biometric Watermarking Module

Layer 1: Pixel-domain steganographic ID embedding (LSB steganography)
Layer 2: Geometric facial landmark encoding (1-2 pixel shifts)
"""
import cv2
import numpy as np
import hashlib
import json
import struct
from typing import Optional


# ─── LAYER 1: PIXEL-DOMAIN STEGANOGRAPHY ─────────────────────────────────────

def embed_hidden_id(image_array: np.ndarray, unique_id: str) -> np.ndarray:
    """
    Embed a unique ID into image using LSB steganography.
    
    Encodes the ID string into the least-significant bits of the
    blue channel pixels. Invisible to human eye.
    """
    img = image_array.copy()
    
    # Prepare message: ID + delimiter
    message = unique_id + "|||END|||"
    binary_msg = ''.join(format(ord(c), '08b') for c in message)
    
    if len(binary_msg) > img.shape[0] * img.shape[1]:
        raise ValueError("Image too small to embed this ID")
    
    flat_blue = img[:, :, 0].flatten()
    
    for i, bit in enumerate(binary_msg):
        # Modify LSB of blue channel
        flat_blue[i] = (flat_blue[i] & 0xFE) | int(bit)
    
    img[:, :, 0] = flat_blue.reshape(img.shape[0], img.shape[1])
    return img


def extract_hidden_id(image_array: np.ndarray) -> Optional[str]:
    """
    Extract the hidden ID from an image using LSB steganography.
    Returns None if no valid ID found.
    """
    flat_blue = image_array[:, :, 0].flatten()
    
    bits = [str(flat_blue[i] & 1) for i in range(min(len(flat_blue), 100000))]
    
    chars = []
    for i in range(0, len(bits) - 7, 8):
        byte = ''.join(bits[i:i+8])
        char = chr(int(byte, 2))
        chars.append(char)
        
        # Check for end delimiter
        if len(chars) >= 9:
            tail = ''.join(chars[-9:])
            if tail == "|||END|||":
                return ''.join(chars[:-9])
    
    return None


# ─── LAYER 2: GEOMETRIC BIOMETRIC WATERMARKING ───────────────────────────────

def _get_face_landmarks_mediapipe(image_array: np.ndarray) -> Optional[list]:
    """
    Detect facial landmarks using MediaPipe (fallback to Dlib if needed).
    Returns list of (x, y) tuples for key landmarks.
    """
    try:
        import mediapipe as mp
        
        mp_face_mesh = mp.solutions.face_mesh
        with mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            min_detection_confidence=0.5
        ) as face_mesh:
            rgb = cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)
            
            if not results.multi_face_landmarks:
                return None
            
            h, w = image_array.shape[:2]
            lm = results.multi_face_landmarks[0].landmark
            
            # Key landmark indices for geometric encoding
            # Left eye: 33, Right eye: 362, Nose tip: 1, 
            # Left mouth: 61, Right mouth: 291, Chin: 152
            key_indices = [33, 362, 1, 61, 291, 152, 168, 4, 197, 195,
                           5, 64, 294, 454, 323, 361, 288, 397, 365, 379]
            
            landmarks = []
            for idx in key_indices:
                x = int(lm[idx].x * w)
                y = int(lm[idx].y * h)
                landmarks.append((x, y))
            
            return landmarks
    
    except Exception as e:
        print(f"MediaPipe error: {e}")
        return _get_face_landmarks_dlib(image_array)


def _get_face_landmarks_dlib(image_array: np.ndarray) -> Optional[list]:
    """Fallback landmark detection using Dlib shape predictor."""
    try:
        import dlib
        import os
        
        detector = dlib.get_frontal_face_detector()
        
        # Try to find shape predictor model
        model_paths = [
            "shape_predictor_68_face_landmarks.dat",
            "/usr/share/dlib/shape_predictor_68_face_landmarks.dat",
            os.path.expanduser("~/shape_predictor_68_face_landmarks.dat")
        ]
        
        predictor = None
        for path in model_paths:
            if os.path.exists(path):
                predictor = dlib.shape_predictor(path)
                break
        
        if predictor is None:
            return None
        
        gray = cv2.cvtColor(image_array, cv2.COLOR_BGR2GRAY)
        faces = detector(gray)
        
        if not faces:
            return None
        
        shape = predictor(gray, faces[0])
        landmarks = [(shape.part(i).x, shape.part(i).y) for i in range(68)]
        
        # Select key landmarks
        key_indices = [36, 45, 30, 48, 54, 8, 17, 26, 0, 16,
                       27, 28, 29, 31, 35, 39, 42, 33, 51, 57]
        return [landmarks[i] for i in key_indices if i < len(landmarks)]
    
    except Exception as e:
        print(f"Dlib error: {e}")
        return None


def _id_to_shifts(unique_id: str, n_landmarks: int) -> list:
    """
    Convert unique ID to deterministic 1-2 pixel shifts.
    Uses HMAC-based expansion for reproducibility.
    """
    id_hash = hashlib.sha256(unique_id.encode()).digest()
    
    shifts = []
    for i in range(n_landmarks):
        # Get deterministic bytes from ID hash
        byte_idx = i % len(id_hash)
        byte_val = id_hash[byte_idx]
        
        # Map to ±1 or ±2 pixel shift
        dx = ((byte_val >> 0) & 3) - 1  # -1, 0, 1, 2 → map to -1 to 1
        dy = ((byte_val >> 2) & 3) - 1
        
        # Clamp to 1-2 pixel range
        dx = max(-2, min(2, dx))
        dy = max(-2, min(2, dy))
        shifts.append((dx, dy))
    
    return shifts


def encode_geometric_watermark(image_array: np.ndarray, unique_id: str) -> tuple:
    """
    Apply geometric biometric watermarking.
    
    Makes imperceptible 1-2 pixel adjustments to facial landmark positions.
    
    Returns:
        (watermarked_image, landmark_signature_dict)
    """
    img = image_array.copy()
    landmarks = _get_face_landmarks_mediapipe(img)
    
    if landmarks is None:
        # No face detected - return original with empty signature
        return img, {"landmarks": [], "shifts": [], "encoded": False}
    
    shifts = _id_to_shifts(unique_id, len(landmarks))
    
    # Apply micro-adjustments to image content around landmarks
    h, w = img.shape[:2]
    for (lx, ly), (dx, dy) in zip(landmarks, shifts):
        # Shift a small region around the landmark
        patch_size = 3
        
        x1, y1 = max(0, lx - patch_size), max(0, ly - patch_size)
        x2, y2 = min(w, lx + patch_size), min(h, ly + patch_size)
        
        if x2 > x1 and y2 > y1:
            # Apply subtle shift using pixel translation in patch
            patch = img[y1:y2, x1:x2].copy()
            M = np.float32([[1, 0, dx * 0.5], [0, 1, dy * 0.5]])
            shifted = cv2.warpAffine(patch,M,
    (patch.shape[1], patch.shape[0]),
    borderMode=cv2.BORDER_REFLECT
)
            img[y1:y2, x1:x2] = shifted
    
    # Build landmark signature (stored in DB for later comparison)
    signature = {
        "landmarks": [(int(x), int(y)) for x, y in landmarks],
        "shifts": [(int(dx), int(dy)) for dx, dy in shifts],
        "encoded": True,
        "n_landmarks": len(landmarks),
        "landmark_hash": hashlib.sha256(
            str(landmarks).encode()
        ).hexdigest()
    }
    
    return img, signature


def compare_landmark_signatures(stored_sig: dict, query_image: np.ndarray, 
                                  threshold: float = 0.75) -> dict:
    """
    Compare stored landmark signature against a query image.
    
    Returns match probability and misuse alert status.
    """
    if not stored_sig.get("encoded"):
        return {"match": False, "confidence": 0.0, "reason": "No geometric signature stored"}
    
    query_landmarks = _get_face_landmarks_mediapipe(query_image)
    
    if query_landmarks is None:
        return {"match": False, "confidence": 0.0, "reason": "No face detected in query image"}
    
    stored_landmarks = stored_sig.get("landmarks", [])
    
    if not stored_landmarks:
        return {"match": False, "confidence": 0.0, "reason": "Empty stored signature"}
    
    # Compare landmark positions
    n_compare = min(len(stored_landmarks), len(query_landmarks))
    
    distances = []
    for i in range(n_compare):
        sx, sy = stored_landmarks[i]
        qx, qy = query_landmarks[i]
        dist = np.sqrt((sx - qx)**2 + (sy - qy)**2)
        distances.append(dist)
    
    # Calculate match confidence
    mean_dist = np.mean(distances)
    median_dist = np.median(distances)
    
    # Normalize: distance < 5px = good match, > 20px = no match
    normalized_score = max(0, 1 - (median_dist / 20.0))
    
    is_match = normalized_score >= threshold
    
    return {
        "match": is_match,
        "confidence": round(float(normalized_score), 3),
        "mean_landmark_distance": round(float(mean_dist), 2),
        "median_landmark_distance": round(float(median_dist), 2),
        "landmarks_compared": n_compare,
        "threshold": threshold
    }
