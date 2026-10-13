"""
DIGIARMOR AI - Detection Routes
Deepfake detection, tamper analysis, and scam message analysis.
"""
from flask import Blueprint, request, jsonify, current_app
import os
import uuid

detect_bp = Blueprint('detect', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@detect_bp.route('/deepfake', methods=['POST'])
def detect_deepfake():
    """Run deepfake detection on an uploaded image."""
    try:
        from utils.deepfake_detect import run_full_deepfake_detection
        from models.db_models import detection_log_doc, DETECTION_LOGS_COLLECTION
        
        if 'image' not in request.files:
            return jsonify({"error": "No image uploaded"}), 400
        
        file = request.files['image']
        if not file or not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type"}), 400
        
        # Save temp file
        temp_name = f"detect_{uuid.uuid4().hex}.jpg"
        temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], temp_name)
        file.save(temp_path)
        
        # Run detection
        result = run_full_deepfake_detection(temp_path)
        
        # Log result
        try:
            from app import mongo
            log = detection_log_doc(
                user_id="anonymous",
                image_path=temp_path,
                detection_type="deepfake",
                result=result
            )
            mongo.db[DETECTION_LOGS_COLLECTION].insert_one(log)
        except Exception:
            pass
        
        return jsonify(result), 200
        
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


@detect_bp.route('/tamper', methods=['POST'])
def detect_tamper():
    """Run tamper/manipulation detection on an uploaded image."""
    try:
        from utils.deepfake_detect import run_tamper_detection
        
        if 'image' not in request.files:
            return jsonify({"error": "No image uploaded"}), 400
        
        file = request.files['image']
        if not file or not allowed_file(file.filename):
            return jsonify({"error": "Invalid file type"}), 400
        
        temp_name = f"tamper_{uuid.uuid4().hex}.jpg"
        temp_path = os.path.join(current_app.config['UPLOAD_FOLDER'], temp_name)
        file.save(temp_path)
        
        result = run_tamper_detection(temp_path)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@detect_bp.route('/scam-message', methods=['POST'])
def analyze_scam_message():
    """
    Analyze a message for scam/phishing indicators.
    Uses heuristic pattern matching.
    """
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({"error": "No message provided"}), 400
        
        result = _analyze_scam_patterns(message)
        return jsonify(result), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def _analyze_scam_patterns(message: str) -> dict:
    """Heuristic scam detection."""
    import re
    
    message_lower = message.lower()
    
    indicators = []
    risk_score = 0
    
    # Urgency patterns
    urgency_words = ['urgent', 'immediately', 'act now', 'limited time', 'expires today',
                     'respond immediately', 'within 24 hours', 'asap', 'right now']
    for word in urgency_words:
        if word in message_lower:
            indicators.append(f"Urgency language: '{word}'")
            risk_score += 15
    
    # Financial bait
    financial_patterns = [
        r'you have won', r'congratulations.*prize', r'claim.*reward',
        r'lottery', r'jackpot', r'\blakh\b', r'crore.*transfer',
        r'bank.*details', r'account.*number', r'otp.*share',
        r'upi.*transfer', r'wallet.*credentials'
    ]
    for pattern in financial_patterns:
        if re.search(pattern, message_lower):
            indicators.append(f"Financial bait detected")
            risk_score += 20
    
    # Identity theft patterns
    identity_patterns = [
        r'aadhaar.*send', r'pan.*card.*photo', r'send.*id.*proof',
        r'upload.*documents', r'kyc.*pending', r'verification.*pending',
        r'account.*block', r'sim.*block'
    ]
    for pattern in identity_patterns:
        if re.search(pattern, message_lower):
            indicators.append("Identity document request detected")
            risk_score += 25
    
    # Impersonation indicators
    impersonation_patterns = [
        r'rbi', r'income tax', r'cyber crime', r'police',
        r'government.*official', r'bank.*manager', r'uidai'
    ]
    for pattern in impersonation_patterns:
        if re.search(pattern, message_lower):
            indicators.append("Possible government/authority impersonation")
            risk_score += 20
    
    # Suspicious links
    link_patterns = [
        r'bit\.ly', r'tinyurl', r'click here', r'follow.*link',
        r'http.*\.xyz', r'http.*\.tk', r'verify.*link'
    ]
    for pattern in link_patterns:
        if re.search(pattern, message_lower):
            indicators.append("Suspicious URL or link detected")
            risk_score += 20
    
    # Grammatical red flags
    if message.count('!') > 3:
        indicators.append("Excessive exclamation marks")
        risk_score += 5
    
    # Cap risk score
    risk_score = min(100, risk_score)
    
    if risk_score >= 60:
        verdict = "HIGH RISK - Likely Scam"
        risk_level = "HIGH"
    elif risk_score >= 35:
        verdict = "MEDIUM RISK - Suspicious"
        risk_level = "MEDIUM"
    else:
        verdict = "LOW RISK - Appears Legitimate"
        risk_level = "LOW"
    
    return {
        "verdict": verdict,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "indicators": list(set(indicators)),
        "recommendation": (
            "Do NOT share personal documents or OTPs. Report this message."
            if risk_score >= 60 else
            "Exercise caution and verify sender identity."
            if risk_score >= 35 else
            "Message appears safe, but always stay vigilant."
        )
    }
