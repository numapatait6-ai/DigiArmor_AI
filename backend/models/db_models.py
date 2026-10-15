"""
DIGIARMOR AI - Database Models
MongoDB document schemas and helper functions.
"""
from datetime import datetime, timedelta
import uuid
import hashlib


# ─── COLLECTION NAMES ────────────────────────────────────────────────────────
USERS_COLLECTION = "users"
PROTECTED_IMAGES_COLLECTION = "protected_images"
SHARE_LINKS_COLLECTION = "share_links"
MISUSE_ALERTS_COLLECTION = "misuse_alerts"
DETECTION_LOGS_COLLECTION = "detection_logs"


# ─── DOCUMENT SCHEMAS ────────────────────────────────────────────────────────

def user_doc(email: str, password_hash: str, name: str) -> dict:
    return {
        "_id": str(uuid.uuid4()),
        "email": email.lower().strip(),
        "password_hash": password_hash,
        "name": name,
        "created_at": datetime.utcnow(),
        "last_login": None,
        "protected_images_count": 0,
        "is_active": True
    }


def protected_image_doc(
    user_id: str,
    original_filename: str,
    original_path: str,
    protected_path: str,
    unique_id: str,
    landmark_signature: dict,
    protection_metadata: dict,
    image_type: str = "photo"  # 'photo', 'aadhaar', 'pan'
) -> dict:
    return {
        "_id": unique_id,
        "user_id": user_id,
        "original_filename": original_filename,
        "original_path": original_path,
        "protected_path": protected_path,
        "unique_id": unique_id,
        "image_type": image_type,
        "landmark_signature": landmark_signature,
        "protection_metadata": protection_metadata,
        "created_at": datetime.utcnow(),
        "accessed_count": 0,
        "misuse_detected": False,
        "misuse_count": 0,
        
        # Image fingerprint for duplicate detection
        "image_hash": protection_metadata.get("image_hash", ""),
    }


def share_link_doc(
    image_id: str,
    user_id: str,
    token: str,
    expiry_hours: int = 24
) -> dict:
    return {
        "_id": token,
        "image_id": image_id,
        "user_id": user_id,
        "token": token,
        "created_at": datetime.utcnow(),
        "expires_at": datetime.utcnow() + timedelta(hours=expiry_hours),
        "is_active": True,
        "view_count": 0,
        "max_views": 10,  # Optional view limit
    }


def misuse_alert_doc(
    protected_image_id: str,
    detected_by: str,  # user_id who uploaded suspicious image
    confidence: float,
    match_method: str,  # 'hidden_id', 'landmark', 'both'
    query_image_path: str
) -> dict:
    return {
        "_id": str(uuid.uuid4()),
        "protected_image_id": protected_image_id,
        "detected_by": detected_by,
        "confidence": confidence,
        "match_method": match_method,
        "query_image_path": query_image_path,
        "detected_at": datetime.utcnow(),
        "alert_sent": False,
        "resolved": False
    }


def detection_log_doc(
    user_id: str,
    image_path: str,
    detection_type: str,  # 'deepfake', 'tamper', 'misuse'
    result: dict
) -> dict:
    return {
        "_id": str(uuid.uuid4()),
        "user_id": user_id,
        "image_path": image_path,
        "detection_type": detection_type,
        "result": result,
        "created_at": datetime.utcnow()
    }


# ─── HELPER FUNCTIONS ────────────────────────────────────────────────────────

def compute_image_hash(image_path: str) -> str:
    """Compute perceptual hash of image for duplicate detection."""
    try:
        import cv2
        import numpy as np
        
        img = cv2.imread(image_path)
        if img is None:
            return ""
        
        # Resize to 8x8 and convert to grayscale
        small = cv2.resize(img, (8, 8))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        
        # Average hash
        avg = gray.mean()
        bits = (gray > avg).flatten()
        hash_str = ''.join(['1' if b else '0' for b in bits])
        
        return hex(int(hash_str, 2))[2:].zfill(16)
    
    except Exception:
        return ""


def generate_unique_id() -> str:
    """Generate a unique image ID."""
    return f"DA-{uuid.uuid4().hex[:12].upper()}"
