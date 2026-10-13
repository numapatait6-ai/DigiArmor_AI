"""
DIGIARMOR AI - OCR-Based Document Redaction Module
Automatically detects and redacts sensitive information from Aadhaar & PAN cards.
"""
import cv2
import numpy as np
import re
import fitz
import tempfile
from PIL import Image, ImageDraw, ImageFilter
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
from typing import List, Tuple, Dict


# ─── SENSITIVE PATTERN DEFINITIONS ───────────────────────────────────────────

AADHAAR_PATTERNS = [
    # Full 12-digit Aadhaar
    (r'\b\d{4}\s?\d{4}\s?\d{4}\b', "AADHAAR_NUMBER", "full"),
    # Middle 4 digits (most sensitive)
    (r'\b\d{4}\s\d{4}\s\d{4}\b', "AADHAAR_MIDDLE", "middle"),
    # VID
    (r'\b\d{16}\b', "VID_NUMBER", "full"),
    # QR code regions - handled separately via region detection
    (r'[Aa]adhaar|[Aa]dhaar|AADHAAR|ADHAAR', "AADHAAR_TEXT", "none"),
    # DOB
    (r'\b\d{2}/\d{2}/\d{4}\b', "DATE_OF_BIRTH", "full"),
    (r'DOB\s*:?\s*\d{2}[/-]\d{2}[/-]\d{4}', "DOB_LABEL", "full"),
    # Phone
    (r'\b[6-9]\d{9}\b', "PHONE_NUMBER", "full"),
]

PAN_PATTERNS = [
    # PAN number format: AAAAA9999A
    (r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', "PAN_NUMBER", "full"),
    (r'Permanent\s+Account\s+Number', "PAN_LABEL", "none"),
    # Father's name regions (label-based)
    (r"Father['']?s?\s+Name", "FATHER_NAME_LABEL", "none"),
    # DOB
    (r'\b\d{2}/\d{2}/\d{4}\b', "DATE_OF_BIRTH", "full"),
]

ADDRESS_PATTERNS = [
    (r'\b\d+[,\s]+[A-Za-z\s]+(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Nagar|Colony|Block|Sector)\b', "ADDRESS", "full"),
    (r'\bPIN\s*:?\s*\d{6}\b', "PIN_CODE", "full"),
    (r'\b\d{6}\b', "PIN_CODE_BARE", "full"),
]


# ─── REDACTION ENGINE ─────────────────────────────────────────────────────────

def extract_text_with_positions(image_array: np.ndarray) -> list:
    """
    Extract text with bounding boxes using multiple OCR passes.
    Uses upscaling and different preprocessing methods to improve
    recognition of small text and numbers on identity documents.
    """

    results = []

    try:
        # ---------------------------------------------------------
        # 1. UPSCALE IMAGE
        # ---------------------------------------------------------
        scale = 3

        enlarged = cv2.resize(
            image_array,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC
        )

        # ---------------------------------------------------------
        # 2. CREATE MULTIPLE OCR VERSIONS
        # ---------------------------------------------------------
        gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)

        # Version 1: normal grayscale
        normal = gray

        # Version 2: Otsu threshold
        _, otsu = cv2.threshold(
            gray,
            0,
            255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        # Version 3: adaptive threshold
        adaptive = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11
        )

        processed_images = [
            normal,
            otsu,
            adaptive
        ]

        # ---------------------------------------------------------
        # 3. RUN TESSERACT ON EACH VERSION
        # ---------------------------------------------------------
        for processed in processed_images:

            data = pytesseract.image_to_data(
                processed,
                output_type=pytesseract.Output.DICT,
                config='--psm 11 -l eng'
            )

            for i in range(len(data['text'])):

                text = data['text'][i].strip()

                try:
                    conf = float(data['conf'][i])
                except:
                    conf = 0

                if text and conf > 15:

                    # Convert coordinates back to original image size
                    x = int(data['left'][i] / scale)
                    y = int(data['top'][i] / scale)
                    w = int(data['width'][i] / scale)
                    h = int(data['height'][i] / scale)

                    item = (
                        text,
                        x,
                        y,
                        w,
                        h,
                        conf
                    )

                    # Avoid duplicate OCR results
                    if item not in results:
                        results.append(item)

        # ---------------------------------------------------------
        # 4. PRINT OCR RESULTS FOR DEBUGGING
        # ---------------------------------------------------------
        print("\n========== OCR RESULTS ==========")

        for item in results:
            print(item)

        print("========== END OCR RESULTS ==========\n")

        return results

    except Exception as e:
        print(f"OCR error: {e}")
        return []
def find_sensitive_regions(ocr_results: list, doc_type: str = "auto") -> list:
    """
    Identify sensitive information from OCR results.

    Handles:
    - Aadhaar numbers split across multiple OCR words
    - PAN numbers
    - Dates
    - Phone numbers
    - PIN codes
    """

    regions_to_redact = []

    # ---------------------------------------------------------
    # RECONSTRUCT OCR TEXT
    # ---------------------------------------------------------

    full_text = " ".join([r[0] for r in ocr_results])

    print("\n========== RECONSTRUCTED OCR TEXT ==========")
    print(full_text)
    print("============================================\n")

    # ---------------------------------------------------------
    # SELECT PATTERNS
    # ---------------------------------------------------------

    if doc_type == "aadhaar":

        patterns = [
            (r'\b\d{4}\s?\d{4}\s?\d{4}\b', "AADHAAR_NUMBER"),
            (r'\b\d{16}\b', "VID_NUMBER"),
            (r'\b\d{2}[/-]\d{2}[/-]\d{4}\b', "DATE_OF_BIRTH"),
            (r'\b[6-9]\d{9}\b', "PHONE_NUMBER"),
            (r'\b\d{6}\b', "PIN_CODE")
        ]

    elif doc_type == "pan":

        patterns = [
            (r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', "PAN_NUMBER"),
            (r'\b\d{2}[/-]\d{2}[/-]\d{4}\b', "DATE_OF_BIRTH"),
            (r'\b\d{6}\b', "PIN_CODE")
        ]

    else:

        patterns = [
            (r'\b\d{4}\s?\d{4}\s?\d{4}\b', "AADHAAR_NUMBER"),
            (r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', "PAN_NUMBER"),
            (r'\b\d{2}[/-]\d{2}[/-]\d{4}\b', "DATE_OF_BIRTH"),
            (r'\b[6-9]\d{9}\b', "PHONE_NUMBER"),
            (r'\b\d{6}\b', "PIN_CODE")
        ]

    # ---------------------------------------------------------
    # CHECK EACH OCR WORD
    # ---------------------------------------------------------

    for text, x, y, w, h, conf in ocr_results:

        cleaned = text.strip()

        for pattern, label in patterns:

            if re.search(pattern, cleaned, re.IGNORECASE):

                print("FOUND:", label, "→", cleaned)

                regions_to_redact.append(
                    (x, y, w, h, label)
                )

                break

    # ---------------------------------------------------------
    # CHECK COMBINED OCR TEXT
    # ---------------------------------------------------------

    # Remove spaces between digit groups for Aadhaar detection
    normalized_text = re.sub(r'\s+', ' ', full_text)

    combined_patterns = [
        (r'\b\d{4}\s+\d{4}\s+\d{4}\b', "AADHAAR_NUMBER"),
        (r'\b\d{16}\b', "VID_NUMBER"),
        (r'\b\d{2}[/-]\d{2}[/-]\d{4}\b', "DATE_OF_BIRTH"),
        (r'\b[6-9]\d{9}\b', "PHONE_NUMBER"),
        (r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', "PAN_NUMBER")
    ]

    for pattern, label in combined_patterns:

        matches = list(
            re.finditer(
                pattern,
                normalized_text,
                re.IGNORECASE
            )
        )

        for match in matches:

            matched_text = match.group()

            print("COMBINED MATCH:", label, "→", matched_text)

            # Find OCR boxes that belong to this match
            match_start = match.start()
            match_end = match.end()

            current_position = 0
            matched_boxes = []

            for item in ocr_results:

                text, x, y, w, h, conf = item

                start = current_position
                end = current_position + len(text)

                if end >= match_start and start <= match_end:

                    matched_boxes.append(item)

                current_position = end + 1

            if matched_boxes:

                x1 = min(item[1] for item in matched_boxes)
                y1 = min(item[2] for item in matched_boxes)

                x2 = max(item[1] + item[3] for item in matched_boxes)
                y2 = max(item[2] + item[4] for item in matched_boxes)

                region = (
                    x1,
                    y1,
                    x2 - x1,
                    y2 - y1,
                    label
                )

                if region not in regions_to_redact:

                    regions_to_redact.append(region)

    print("\n========== REDACTION REGIONS ==========")

    for region in regions_to_redact:
        print(region)

    print("Total regions:", len(regions_to_redact))
    print("========================================\n")

    return regions_to_redact


def detect_qr_code_region(image_array: np.ndarray) -> list:
    """
    Detect QR code regions using OpenCV.
    """

    regions = []

    try:

        detector = cv2.QRCodeDetector()

        # Try original image
        retval, decoded_info, points, _ = detector.detectAndDecodeMulti(
            image_array
        )

        if retval and points is not None:

            for pts in points:

                pts = pts.astype(int)

                x_min = max(0, pts[:, 0].min() - 15)
                y_min = max(0, pts[:, 1].min() - 15)

                x_max = pts[:, 0].max() + 15
                y_max = pts[:, 1].max() + 15

                regions.append(
                    (
                        x_min,
                        y_min,
                        x_max - x_min,
                        y_max - y_min,
                        "QR_CODE"
                    )
                )

    except Exception as e:

        print("QR detection error:", e)

    print("QR regions detected:", len(regions))

    return regions


def apply_redaction(image_array: np.ndarray, regions: list, 
                     method: str = "blur") -> np.ndarray:
    """
    Apply redaction to specified regions.
    
    Methods: 'blur' (Gaussian blur), 'black' (solid black), 'mosaic' (pixelate)
    """
    img = image_array.copy()
    h_img, w_img = img.shape[:2]
    
    for region in regions:
        x, y, w, h = int(region[0]), int(region[1]), int(region[2]), int(region[3])
        label = region[4] if len(region) > 4 else "REDACTED"
        
        # Expand region slightly for better coverage
        padding = 5
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(w_img, x + w + padding)
        y2 = min(h_img, y + h + padding)
        
        if x2 <= x1 or y2 <= y1:
            continue
        
        if method == "blur":
            roi = img[y1:y2, x1:x2]
            kernel_size = max(15, ((x2 - x1) // 5) * 2 + 1)
            blurred = cv2.GaussianBlur(roi, (kernel_size, kernel_size), 0)
            img[y1:y2, x1:x2] = blurred
            
        elif method == "black":
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 0), -1)
            
        elif method == "mosaic":
            roi = img[y1:y2, x1:x2]
            mosaic_size = 10
            small = cv2.resize(roi, 
                               (max(1, (x2-x1) // mosaic_size), max(1, (y2-y1) // mosaic_size)),
                               interpolation=cv2.INTER_LINEAR)
            mosaic = cv2.resize(small, (x2-x1, y2-y1), interpolation=cv2.INTER_NEAREST)
            img[y1:y2, x1:x2] = mosaic
    
    return img


def redact_document(image_path: str, output_path: str, 
                    doc_type: str = "auto",
                    redaction_method: str = "blur") -> dict:
    """
    Full document redaction pipeline.
    
    Args:
        image_path: Input document image path
        output_path: Output path for redacted document
        doc_type: 'aadhaar', 'pan', or 'auto'
        redaction_method: 'blur', 'black', or 'mosaic'
    
    Returns:
        dict with redaction summary
    """
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Cannot load image: {image_path}")
    
    # Auto-detect document type
    if doc_type == "auto":
        ocr_sample = pytesseract.image_to_string(img, config='--psm 6')
        if re.search(r'[Aa]adhaar|[Aa]dhaar|UIDAI', ocr_sample):
            doc_type = "aadhaar"
        elif re.search(r'INCOME TAX|PAN|Permanent Account', ocr_sample, re.IGNORECASE):
            doc_type = "pan"
        else:
            doc_type = "general"
    
    # Extract text with positions
    ocr_results = extract_text_with_positions(img)
    
    # Find sensitive regions
    sensitive_regions = find_sensitive_regions(ocr_results, doc_type)
    
    # Find QR codes
    qr_regions = detect_qr_code_region(img)
    
    all_regions = sensitive_regions + qr_regions
    
    # Apply redaction
    if all_regions:
        redacted_img = apply_redaction(img, all_regions, method=redaction_method)
    else:
        redacted_img = img.copy()
    
    # Add "REDACTED" watermark
    pil_img = Image.fromarray(cv2.cvtColor(redacted_img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)
    
    # Subtle "PROTECTED" text
    text = "DIGIARMOR PROTECTED"
    tw = 200
    th = 20
    draw.text(
        (pil_img.width - tw - 10, pil_img.height - th - 10),
        text,
        fill=(128, 128, 128, 128)
    )
    
    redacted_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    cv2.imwrite(output_path, redacted_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
    
    # Categorize redacted items
    labels_found = list(set([r[4] for r in all_regions if len(r) > 4]))
    
    return {
        "doc_type_detected": doc_type,
        "regions_redacted": len(all_regions),
        "sensitive_items_found": labels_found,
        "qr_codes_redacted": len(qr_regions),
        "redaction_method": redaction_method,
        "ocr_confidence": "high" if len(ocr_results) > 5 else "low",
        "redaction_successful": len(all_regions) > 0
    }

def redact_pdf(input_pdf_path: str, output_pdf_path: str,
               doc_type: str = "auto",
               redaction_method: str = "blur") -> dict:
    """
    Process every page of a PDF using the existing
    DIGIARMOR image redaction engine and create
    one protected PDF.
    """

    pdf = fitz.open(input_pdf_path)
    protected_pdf = fitz.open()

    total_regions = 0
    sensitive_items = []
    detected_types = []

    total_pages = len(pdf)

    try:
        for page_number in range(total_pages):

            page = pdf[page_number]

            # Render PDF page as a high-resolution image
            pix = page.get_pixmap(
                matrix=fitz.Matrix(2, 2),
                alpha=False
            )

            # Create temporary image path
            temp_input = tempfile.NamedTemporaryFile(
                suffix=".jpg",
                delete=False
            )
            temp_input.close()

            temp_output = tempfile.NamedTemporaryFile(
                suffix=".jpg",
                delete=False
            )
            temp_output.close()

            try:
                # Save PDF page as JPG
                pix.save(temp_input.name)

                # USE YOUR EXISTING REDACTION ENGINE
                result = redact_document(
                    temp_input.name,
                    temp_output.name,
                    doc_type,
                    redaction_method
                )

                # Collect result information
                total_regions += result.get(
                    "regions_redacted", 0
                )

                sensitive_items.extend(
                    result.get(
                        "sensitive_items_found", []
                    )
                )

                detected_type = result.get(
                    "doc_type_detected"
                )

                if detected_type:
                    detected_types.append(detected_type)

                # Read protected image
                protected_page = cv2.imread(
                    temp_output.name
                )

                if protected_page is None:
                    continue

                # Convert BGR → RGB
                protected_page = cv2.cvtColor(
                    protected_page,
                    cv2.COLOR_BGR2RGB
                )

                # Encode as JPEG
                success, encoded = cv2.imencode(
                    ".jpg",
                    cv2.cvtColor(
                        protected_page,
                        cv2.COLOR_RGB2BGR
                    ),
                    [cv2.IMWRITE_JPEG_QUALITY, 95]
                )

                if not success:
                    continue

                # Create same-size PDF page
                pdf_page = protected_pdf.new_page(
                    width=page.rect.width,
                    height=page.rect.height
                )

                # Insert protected image
                pdf_page.insert_image(
                    pdf_page.rect,
                    stream=encoded.tobytes()
                )

            finally:
                # Remove temporary files
                try:
                    os.remove(temp_input.name)
                except Exception:
                    pass

                try:
                    os.remove(temp_output.name)
                except Exception:
                    pass

    finally:
        pdf.close()

    # Remove duplicate labels
    sensitive_items = list(set(sensitive_items))

    # Save protected PDF
    protected_pdf.save(
        output_pdf_path,
        garbage=4,
        deflate=True
    )

    protected_pdf.close()

    # Determine document type
    if detected_types:
        if "aadhaar" in detected_types:
            final_doc_type = "aadhaar"
        elif "pan" in detected_types:
            final_doc_type = "pan"
        else:
            final_doc_type = detected_types[0]
    else:
        final_doc_type = doc_type

    return {
        "doc_type_detected": final_doc_type,
        "regions_redacted": total_regions,
        "sensitive_items_found": sensitive_items,
        "redaction_method": redaction_method,
        "redaction_successful": total_regions > 0,
        "output_type": "pdf",
        "pages_processed": total_pages
    }