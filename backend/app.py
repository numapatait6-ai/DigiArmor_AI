"""
DIGIARMOR AI - Main Application Entry Point
"""
import os
from flask import Flask
from flask_cors import CORS
from flask_pymongo import PyMongo
from dotenv import load_dotenv

load_dotenv()

# Initialize Flask
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Config
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/digiarmor")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "digiarmor-secret-key-2024")
app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "uploads")
app.config["PROTECTED_FOLDER"] = os.path.join(os.path.dirname(__file__), "protected")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB max

# Ensure folders exist
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["PROTECTED_FOLDER"], exist_ok=True)

# MongoDB
mongo = PyMongo(app)

# Register Blueprints
from routes.auth import auth_bp
from routes.protect import protect_bp
from routes.detect import detect_bp
from routes.share import share_bp
from routes.redact import redact_bp

app.register_blueprint(auth_bp, url_prefix="/api/auth")
app.register_blueprint(protect_bp, url_prefix="/api/protect")
app.register_blueprint(detect_bp, url_prefix="/api/detect")
app.register_blueprint(share_bp, url_prefix="/api/share")
app.register_blueprint(redact_bp, url_prefix="/api/redact")

@app.route("/api/health")
def health():
    return {"status": "DIGIARMOR AI is running", "version": "1.0.0"}

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
