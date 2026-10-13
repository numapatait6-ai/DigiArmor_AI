"""
DIGIARMOR AI - Secure Sharing Routes
Generates expiring, view-only links for protected images.
"""
from flask import Blueprint, request, jsonify, send_file, current_app
from datetime import datetime
import os
import uuid
import secrets
from mimetypes import guess_type

share_bp = Blueprint('share', __name__)


def get_mongo():
    from app import mongo
    return mongo


@share_bp.route('/create', methods=['POST'])
def create_share_link():
    """Create a secure expiring share link for a protected image."""
    try:
        from models.db_models import (share_link_doc, SHARE_LINKS_COLLECTION, 
                                       PROTECTED_IMAGES_COLLECTION)
        
        data = request.get_json()
        image_id = data.get('image_id')
        expiry_hours = int(data.get('expiry_hours', 24))
        
        if not image_id:
            return jsonify({"error": "image_id required"}), 400
        
        expiry_hours = max(1, min(168, expiry_hours))  # 1 hour to 7 days
        
        mongo = get_mongo()
        
        # Verify image exists
        img_doc = mongo.db[PROTECTED_IMAGES_COLLECTION].find_one({"_id": image_id})
        if not img_doc:
            return jsonify({"error": "Protected image not found"}), 404
        
        # Generate secure token
        token = secrets.token_urlsafe(32)
        
        # Create share link doc
        link_doc = share_link_doc(
            image_id=image_id,
            user_id=img_doc.get("user_id", "anonymous"),
            token=token,
            expiry_hours=expiry_hours
        )
        
        mongo.db[SHARE_LINKS_COLLECTION].insert_one(link_doc)
        
        base_url = request.host_url.rstrip('/')
        share_url = f"{base_url}/api/share/view/{token}"
        
        return jsonify({
            "success": True,
            "token": token,
            "share_url": share_url,
            "expires_at": link_doc["expires_at"].isoformat() + "Z",
            "expiry_hours": expiry_hours,
            "max_views": link_doc["max_views"]
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@share_bp.route('/view/<token>', methods=['GET'])
def view_shared_image(token):
    """View a shared image via its token (enforces expiry + view limits)."""
    try:
        from models.db_models import (SHARE_LINKS_COLLECTION, PROTECTED_IMAGES_COLLECTION)
        
        mongo = get_mongo()
        
        # Find link
        link = mongo.db[SHARE_LINKS_COLLECTION].find_one({"token": token})
        
        if not link:
            return jsonify({"error": "Share link not found"}), 404
        
        if not link.get("is_active"):
            return jsonify({"error": "This link has been deactivated"}), 410
        
        # Check expiry
        if datetime.utcnow() > link["expires_at"]:
            mongo.db[SHARE_LINKS_COLLECTION].update_one(
                {"token": token}, {"$set": {"is_active": False}}
            )
            return jsonify({"error": "This share link has expired"}), 410
        
        # Check view count
        if link.get("view_count", 0) >= link.get("max_views", 10):
            return jsonify({"error": "Maximum view count reached"}), 410
        
        # Find image
        img_doc = mongo.db[PROTECTED_IMAGES_COLLECTION].find_one(
            {"_id": link["image_id"]}
        )
        
        if not img_doc:
            return jsonify({"error": "Image not found"}), 404
        
        # Increment view count
        mongo.db[SHARE_LINKS_COLLECTION].update_one(
            {"token": token}, {"$inc": {"view_count": 1}}
        )
        
        # Serve file
        protected_path = img_doc.get("protected_path")
        if not protected_path or not os.path.exists(protected_path):
            return jsonify({"error": "Protected image file not found"}), 404
    
        mime_type = guess_type(protected_path)[0] or 'application/octet-stream'
        return send_file(
    protected_path,
    mimetype=mime_type
)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@share_bp.route('/info/<token>', methods=['GET'])
def share_link_info(token):
    """Get metadata about a share link without incrementing view count."""
    try:
        from models.db_models import SHARE_LINKS_COLLECTION
        
        mongo = get_mongo()
        link = mongo.db[SHARE_LINKS_COLLECTION].find_one({"token": token})
        
        if not link:
            return jsonify({"error": "Share link not found"}), 404
        
        is_expired = datetime.utcnow() > link["expires_at"]
        views_remaining = max(0, link.get("max_views", 10) - link.get("view_count", 0))
        
        return jsonify({
            "token": token,
            "is_active": link.get("is_active") and not is_expired,
            "is_expired": is_expired,
            "expires_at": str(link["expires_at"]),
            "view_count": link.get("view_count", 0),
            "views_remaining": views_remaining,
            "created_at": str(link.get("created_at"))
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@share_bp.route('/revoke/<token>', methods=['DELETE'])
def revoke_share_link(token):
    """Revoke/deactivate a share link."""
    try:
        from models.db_models import SHARE_LINKS_COLLECTION
        
        mongo = get_mongo()
        result = mongo.db[SHARE_LINKS_COLLECTION].update_one(
            {"token": token},
            {"$set": {"is_active": False}}
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Share link not found"}), 404
        
        return jsonify({"success": True, "message": "Share link revoked"}), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
