"""
DIGIARMOR AI - Document Redaction Routes
OCR-based automatic redaction for Aadhaar and PAN cards.
"""

from flask import Blueprint, request, jsonify, send_file, current_app
import os
import uuid

redact_bp = Blueprint('redact', __name__)

ALLOWED_EXTENSIONS = {
    'png',
    'jpg',
    'jpeg',
    'webp',
    'bmp',
    'pdf'
}


def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


@redact_bp.route('/document', methods=['POST'])
def redact_document():
    """
    Redact sensitive information from identity documents.

    Supports:
    - JPG
    - JPEG
    - PNG
    - WEBP
    - BMP
    - PDF
    """

    try:

        # Import both redaction functions
        from utils.ocr_redact import (
            redact_document as do_redact,
            redact_pdf
        )

        # Check uploaded file
        if 'document' not in request.files:
            return jsonify({
                "error": "No document uploaded"
            }), 400

        file = request.files['document']

        if not file or not allowed_file(file.filename):
            return jsonify({
                "error": "Invalid file type. "
                         "Supported: JPG, JPEG, PNG, WEBP, BMP, PDF"
            }), 400

        # Get settings
        doc_type = request.form.get(
            'doc_type',
            'auto'
        )

        redaction_method = request.form.get(
            'method',
            'blur'
        )

        # --------------------------------------------------
        # SAVE ORIGINAL FILE
        # --------------------------------------------------

        file_ext = file.filename.rsplit(
            '.',
            1
        )[1].lower()

        orig_name = (
            f"doc_{uuid.uuid4().hex}.{file_ext}"
        )

        orig_path = os.path.join(
            current_app.config['UPLOAD_FOLDER'],
            orig_name
        )

        file.save(orig_path)

        # --------------------------------------------------
        # PDF
        # --------------------------------------------------

        if file_ext == 'pdf':

            out_name = (
                f"protected_{uuid.uuid4().hex}.pdf"
            )

            out_path = os.path.join(
                current_app.config['PROTECTED_FOLDER'],
                out_name
            )

            # Process PDF
            result = redact_pdf(
                orig_path,
                out_path,
                doc_type,
                redaction_method
            )

            return jsonify({
                "success": True,
                "redacted_filename": out_name,
                "file_type": "pdf",
                "download_url": (
                    f"/api/redact/download/{out_name}"
                ),
                "redaction_summary": result
            }), 200

        # --------------------------------------------------
        # IMAGE
        # --------------------------------------------------

        else:

            out_name = (
                f"redacted_{uuid.uuid4().hex}.jpg"
            )

            out_path = os.path.join(
                current_app.config['PROTECTED_FOLDER'],
                out_name
            )

            # Existing image redaction
            result = do_redact(
                orig_path,
                out_path,
                doc_type,
                redaction_method
            )

            return jsonify({
                "success": True,
                "redacted_filename": out_name,
                "file_type": "image",
                "download_url": (
                    f"/api/redact/download/{out_name}"
                ),
                "redaction_summary": result
            }), 200

    except Exception as e:

        import traceback

        print(traceback.format_exc())

        return jsonify({
            "error": str(e),
            "trace": traceback.format_exc()
        }), 500


@redact_bp.route('/download/<filename>', methods=['GET'])
def download_redacted(filename):
    """Serve protected image or PDF."""

    try:

        # Prevent directory traversal
        safe_filename = os.path.basename(filename)

        file_path = os.path.join(
            current_app.config['PROTECTED_FOLDER'],
            safe_filename
        )

        if not os.path.exists(file_path):
            return jsonify({
                "error": "File not found"
            }), 404

        # PDF
        if safe_filename.lower().endswith('.pdf'):

            return send_file(
                file_path,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=safe_filename
            )

        # Image
        return send_file(
            file_path,
            mimetype='image/jpeg',
            as_attachment=True,
            download_name=safe_filename
        )

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500