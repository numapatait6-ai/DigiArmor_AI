"""
DIGIARMOR AI - Authentication Routes
"""
from flask import Blueprint, request, jsonify, current_app
import bcrypt
import jwt
from datetime import datetime, timedelta
from models.db_models import user_doc, USERS_COLLECTION
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

auth_bp = Blueprint('auth', __name__)


def get_mongo():
    from app import mongo
    return mongo


@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not all([name, email, password]):
            return jsonify({"error": "Name, email and password are required"}), 400

        if len(password) < 8:
            return jsonify({"error": "Password must be at least 8 characters"}), 400

        mongo = get_mongo()
        
        # Check if user exists
        existing = mongo.db[USERS_COLLECTION].find_one({"email": email})
        if existing:
            return jsonify({"error": "Email already registered"}), 409

        # Hash password
        pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Create user
        user = user_doc(email, pw_hash, name)
        mongo.db[USERS_COLLECTION].insert_one(user)

        return jsonify({
            "message": "Registration successful",
            "user_id": user["_id"],
            "name": name
        }), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')

        if not all([email, password]):
            return jsonify({"error": "Email and password required"}), 400

        mongo = get_mongo()
        user = mongo.db[USERS_COLLECTION].find_one({"email": email})

        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        if not bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            return jsonify({"error": "Invalid credentials"}), 401

        # Update last login
        mongo.db[USERS_COLLECTION].update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login": datetime.utcnow()}}
        )

        # Generate JWT
        payload = {
            "user_id": user["_id"],
            "email": user["email"],
            "name": user["name"],
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')

        return jsonify({
            "token": token,
            "user_id": user["_id"],
            "name": user["name"],
            "email": user["email"]
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route('/verify', methods=['GET'])
def verify_token():
    try:
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"valid": False, "error": "No token provided"}), 401

        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])

        return jsonify({"valid": True, "user": payload}), 200

    except jwt.ExpiredSignatureError:
        return jsonify({"valid": False, "error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"valid": False, "error": "Invalid token"}), 401


def require_auth(f):
    """Decorator for protected routes."""
    from functools import wraps
    
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Authentication required"}), 401
        
        token = auth_header.split(' ')[1]
        try:
            payload = jwt.decode(
                token, current_app.config['SECRET_KEY'], algorithms=['HS256']
            )
            request.user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401
        
        return f(*args, **kwargs)
    
    return decorated
