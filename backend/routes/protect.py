"""
DIGIARMOR AI - Image Protection Routes
Handles the full protection pipeline:
1. Adversarial noise injection
2. Steganographic ID embedding
3. Geometric biometric watermarking
4. Deepfake resistance comparison
"""
from flask import Blueprint, request, jsonify, send_file, current_app
import os
import uuid
import cv2
from datetime import datetime

protect_bp = Blueprint('protect', __name__)


def get_mongo():
    from app import mongo
    return mongo


def get_user_id():
    """Extract user_id from JWT token."""
    import jwt
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(
                token, current_app.config['SECRET_KEY'], algorithms=['HS256']
            )
            return payload.get('user_id', 'anonymous')
        except Exception:
            pass
    return 'anonymous'


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@protect_bp.route('/image', methods=['POST'])
def protect_image():
    """
    Full protection pipeline for face photos.
    Applies adversarial noise + dual-layer watermarking.
    """
    try:
        from utils.adversarial import apply_adversarial_protection, simulate_deepfake_resistance
        from utils.watermark import embed_hidden_id, encode_geometric_watermark
        from models.db_models import (protected_image_doc, generate_unique_id, 
                                       compute_image_hash, PROTECTED_IMAGES_COLLECTION)
        import numpy as np
        
        if 'image' not in request.files:
            return jsonify({"error": "No image uploaded"}), 400
        
        file = request.files['image']
        if not file or not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type. Use JPG, PNG, or WebP."}), 400
        
        epsilon = float(request.form.get('epsilon', 0.00002))
        epsilon = max(0.001, min(0.01, epsilon))  # Clamp to safe range
        
        user_id = get_user_id()
        
        # Save original
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        original_name = f"orig_{uuid.uuid4().hex}.{file_ext}"
        original_path = os.path.join(current_app.config['UPLOAD_FOLDER'], original_name)
        file.save(original_path)
        
        # Generate unique ID for this image
        unique_id = generate_unique_id()
        
        # Step 1: Adversarial protection
        adv_name = f"adv_{uuid.uuid4().hex}.jpg"
        adv_path = os.path.join(current_app.config['UPLOAD_FOLDER'], adv_name)
        adv_metadata = apply_adversarial_protection(original_path, adv_path, epsilon)
        
        # Step 2: Load adversarial image and embed hidden ID
        adv_img = cv2.imread(adv_path)
        id_embedded = embed_hidden_id(adv_img, unique_id)
        
        # Step 3: Geometric biometric watermarking
        geo_watermarked, landmark_sig = encode_geometric_watermark(id_embedded, unique_id)
        
        # Save final protected image
        protected_name = f"protected_{uuid.uuid4().hex}.png"
        protected_path = os.path.join(
            current_app.config['PROTECTED_FOLDER'], protected_name
        )
        cv2.imwrite(
    protected_path,
    geo_watermarked,
    [cv2.IMWRITE_PNG_COMPRESSION, 1]
)
        
        # Step 4: Simulate deepfake resistance comparison
        resistance_data = simulate_deepfake_resistance(original_path, protected_path)
        
        # Compute image hash
        img_hash = compute_image_hash(original_path)
        
        # Store in database
        protection_meta = {
            **adv_metadata,
            "image_hash": img_hash,
            "epsilon": epsilon,
            "resistance": resistance_data
        }
        
        doc = protected_image_doc(
            user_id=user_id,
            original_filename=file.filename,
            original_path=original_path,
            protected_path=protected_path,
            unique_id=unique_id,
            landmark_signature=landmark_sig,
            protection_metadata=protection_meta,
            image_type="photo"
        )
        
        mongo = get_mongo()
        mongo.db[PROTECTED_IMAGES_COLLECTION].insert_one(doc)
        
        return jsonify({
            "success": True,
            "unique_id": unique_id,
            "protected_image_name": protected_name,
            "psnr": adv_metadata.get("psnr"),
            "protection_metrics": {
                "adversarial_applied": True,
                "hidden_id_embedded": True,
                "geometric_watermark_applied": landmark_sig.get("encoded", False),
                "landmarks_encoded": landmark_sig.get("n_landmarks", 0)
            },
            "deepfake_resistance": resistance_data,
            "message": f"Image protected with ID: {unique_id}"
        }), 200
        
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@protect_bp.route('/check-misuse', methods=['POST'])
def check_misuse():
    """
    Check if a query image matches any protected image in the database.
    Dual-layer verification: hidden ID + landmark comparison.
    """
    try:
        from utils.watermark import extract_hidden_id, compare_landmark_signatures
        from models.db_models import (PROTECTED_IMAGES_COLLECTION, MISUSE_ALERTS_COLLECTION,
                                       misuse_alert_doc)
        
        if 'image' not in request.files:
            return jsonify({"error": "No image uploaded"}), 400
        
        file = request.files['image']
        if not file or not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type"}), 400
        
        user_id = get_user_id()
        
        # Save query image
        query_name = f"query_{uuid.uuid4().hex}.jpg"
        query_path = os.path.join(current_app.config['UPLOAD_FOLDER'], query_name)
        file.save(query_path)
        
        # Load image
        import numpy as np
        query_img = cv2.imread(query_path)
        if query_img is None:
            return jsonify({"error": "Cannot process image"}), 400
        
        mongo = get_mongo()
        
        # Layer 1: Extract hidden ID
        extracted_id = extract_hidden_id(query_img)
        
        match_result = {
            "misuse_detected": False,
            "match_method": None,
            "protected_image_id": None,
            "confidence": 0,
            "hidden_id_found": extracted_id is not None,
            "extracted_id": extracted_id
        }
        
        if extracted_id:
            # Direct ID match
            protected_doc = mongo.db[PROTECTED_IMAGES_COLLECTION].find_one(
                {"unique_id": extracted_id}
            )
            
            if protected_doc:
                match_result.update({
                    "misuse_detected": True,
                    "match_method": "hidden_id",
                    "protected_image_id": extracted_id,
                    "confidence": 0.99,
                    "owner_user_id": protected_doc.get("user_id"),
                    "protected_at": str(protected_doc.get("created_at")),
                    "original_filename": protected_doc.get("original_filename")
                })
                
                # Log misuse alert
                alert = misuse_alert_doc(
                    protected_image_id=extracted_id,
                    detected_by=user_id,
                    confidence=0.99,
                    match_method="hidden_id",
                    query_image_path=query_path
                )
                mongo.db[MISUSE_ALERTS_COLLECTION].insert_one(alert)
                
                # Update misuse count
                mongo.db[PROTECTED_IMAGES_COLLECTION].update_one(
                    {"_id": extracted_id},
                    {"$inc": {"misuse_count": 1}, "$set": {"misuse_detected": True}}
                )
                
                return jsonify(match_result), 200
        
        # Layer 2: Landmark signature comparison (scan all protected images)
        all_protected = list(mongo.db[PROTECTED_IMAGES_COLLECTION].find(
            {"landmark_signature.encoded": True},
            {"unique_id": 1, "landmark_signature": 1, "user_id": 1, 
             "original_filename": 1, "created_at": 1}
        ).limit(500))
        
        best_match = None
        best_confidence = 0
        
        for doc in all_protected:
            sig = doc.get("landmark_signature", {})
            result = compare_landmark_signatures(sig, query_img)
            
            if result["match"] and result["confidence"] > best_confidence:
                best_confidence = result["confidence"]
                best_match = doc
        
        if best_match and best_confidence > 0.75:
            protected_id = best_match.get("unique_id")
            match_result.update({
                "misuse_detected": True,
                "match_method": "geometric_landmark",
                "protected_image_id": protected_id,
                "confidence": round(best_confidence, 3),
                "owner_user_id": best_match.get("user_id"),
                "protected_at": str(best_match.get("created_at")),
                "original_filename": best_match.get("original_filename")
            })
            
            # Log alert
            alert = misuse_alert_doc(
                protected_image_id=protected_id,
                detected_by=user_id,
                confidence=best_confidence,
                match_method="geometric_landmark",
                query_image_path=query_path
            )
            mongo.db[MISUSE_ALERTS_COLLECTION].insert_one(alert)
        
        return jsonify(match_result), 200
        
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@protect_bp.route('/images', methods=['GET'])
def list_protected_images():
    """List all protected images for the current user."""
    try:
        from models.db_models import PROTECTED_IMAGES_COLLECTION
        
        user_id = get_user_id()
        mongo = get_mongo()
        
        docs = list(mongo.db[PROTECTED_IMAGES_COLLECTION].find(
            {"user_id": user_id},
            {"original_path": 0, "protected_path": 0, "landmark_signature": 0}
        ).sort("created_at", -1).limit(50))
        
        # Convert datetime objects
        for doc in docs:
            if "created_at" in doc:
                doc["created_at"] = str(doc["created_at"])
        
        return jsonify({"images": docs, "count": len(docs)}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@protect_bp.route('/download/<filename>', methods=['GET'])
def download_protected(filename):
    """Serve a protected image file."""
    try:
        safe_filename = os.path.basename(filename)
        file_path = os.path.join(current_app.config['PROTECTED_FOLDER'], safe_filename)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "File not found"}), 404
        
        return send_file(
    file_path,
    mimetype='image/jpeg',
    as_attachment=True,
    download_name=safe_filename
)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
