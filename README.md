# 🛡️ DIGIARMOR AI
### Proactive Identity Protection System

A full-stack web application implementing adversarial image protection, OCR-based document redaction, dual-layer biometric watermarking, deepfake detection, and secure expiring link sharing.

---

## 📁 Project Structure

```
digiarmor/
├── backend/                    # Flask Python Backend
│   ├── app.py                  # Main Flask app + route registration
│   ├── requirements.txt        # Python dependencies
│   ├── .env.example            # Environment config template
│   ├── routes/
│   │   ├── auth.py             # JWT authentication (register/login)
│   │   ├── protect.py          # Image protection pipeline
│   │   ├── detect.py           # Deepfake + tamper detection
│   │   ├── redact.py           # OCR document redaction
│   │   └── share.py            # Expiring secure link sharing
│   ├── utils/
│   │   ├── adversarial.py      # FGSM + DCT adversarial noise
│   │   ├── watermark.py        # LSB steganography + geometric watermark
│   │   ├── ocr_redact.py       # OCR-based sensitive data redaction
│   │   └── deepfake_detect.py  # ELA + frequency + facial analysis
│   ├── models/
│   │   └── db_models.py        # MongoDB document schemas
│   ├── uploads/                # Temporary upload storage
│   └── protected/              # Protected/redacted images
│
└── frontend/                   # React Frontend
    ├── package.json
    ├── public/index.html
    └── src/
        ├── App.jsx             # Router + auth state
        ├── App.css             # Full dark theme stylesheet
        ├── index.js
        ├── utils/api.js        # Axios API client
        ├── components/
        │   └── Layout.jsx      # Sidebar + topbar layout
        └── pages/
            ├── Login.jsx
            ├── Register.jsx
            ├── Dashboard.jsx
            ├── ProtectImage.jsx    # Core protection feature
            ├── DetectDeepfake.jsx  # Detection feature
            ├── RedactDocument.jsx  # OCR redaction
            ├── CheckMisuse.jsx     # Misuse detection
            ├── SecureShare.jsx     # Expiring links
            └── ScamAnalyzer.jsx    # Message analysis
```

---

## ⚙️ Setup Instructions

### Prerequisites
- Python 3.9+
- Node.js 18+
- MongoDB (local or Atlas)
- Tesseract OCR installed

### 1. Install Tesseract OCR

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```
**macOS:**
```bash
brew install tesseract
```
**Windows:** Download from https://github.com/UB-Mannheim/tesseract/wiki

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your MongoDB URI and secret key

# Run the backend
python app.py
```

Backend will start at: `http://localhost:5000`

### 3. (Optional) Dlib Facial Landmarks

For enhanced geometric watermarking, download the shape predictor model:
```bash
# Download and extract in backend/ directory
wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
bzip2 -d shape_predictor_68_face_landmarks.dat.bz2
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

Frontend will start at: `http://localhost:3000`

### 5. MongoDB

- **Local:** Install MongoDB Community Edition and start with `mongod`
- **Atlas (Cloud):** Create free cluster at https://cloud.mongodb.com and use connection string in `.env`

---

## 🚀 Features

| Feature | Implementation |
|---------|---------------|
| **Adversarial Protection** | FGSM + checkerboard + DCT-domain noise |
| **Hidden ID Embedding** | LSB steganography in blue channel pixels |
| **Geometric Watermark** | Facial landmark micro-shifts (1-2px via MediaPipe) |
| **Deepfake Detection** | ELA + Frequency domain + Facial inconsistency |
| **Tamper Detection** | Error Level Analysis + Block noise consistency |
| **OCR Redaction** | Tesseract + Regex for Aadhaar/PAN/QR |
| **Misuse Detection** | Dual-layer: hidden ID + landmark comparison |
| **Secure Sharing** | JWT-signed expiring links with view limits |
| **Scam Analysis** | Heuristic pattern matching for fraud detection |
| **Authentication** | JWT + bcrypt |
| **Database** | MongoDB with full audit logging |

---

## 🔬 Technical Notes

### Adversarial Noise Formula
```
P = I + ε·N
where N = 0.4·checkerboard + 0.3·random_noise + 0.3·dct_perturbation
```

### Deepfake Resistance Comparison
The system compares:
- **Original image**: ~75-92% AI reuse rate
- **Protected image**: ~8-25% AI reuse rate
- **Reduction**: ~60-80% reduction

### Dual-Layer Watermarking
1. **Layer 1 (LSB)**: 8 bits per pixel in blue channel → unique ID string
2. **Layer 2 (Geometric)**: SHA256-derived 1-2px shifts to 20 facial landmarks

---

## 🛠 Technologies

**Backend:** Python, Flask, OpenCV, MediaPipe, Dlib, Pytesseract, NumPy, SciPy, PyMongo, PyJWT, bcrypt

**Frontend:** React 18, React Router v6, Axios, React Dropzone, React Toastify, Lucide React

**Database:** MongoDB

**AI/ML:** FGSM adversarial noise, DCT perturbation, ELA tamper detection, FFT frequency analysis, Haar cascade face detection, MediaPipe face mesh

---

## 📊 System Methodology

### Phase 1: Protection Pipeline
1. Upload photo → Apply adversarial noise (ε = 0.03)
2. Embed unique hidden ID via LSB steganography
3. Detect facial landmarks → Apply geometric micro-shifts
4. Store signature in MongoDB

### Phase 2: Detection & Verification
1. Upload query image → Extract hidden ID
2. If no ID → Compare landmark signatures (scan DB)
3. If match → Log misuse alert + display warning

### Phase 3: Secure Sharing
1. Select protected image → Generate JWT-signed token
2. Link expires after N hours (max 10 views)
3. View-only endpoint with access control

---

## 🔮 Future Scope (Extension Ideas)

- **Chrome Extension**: Auto-protect before social media upload
- **Video-Level Defense**: Frame-by-frame adversarial protection
- **Real-Time Monitoring**: Web scraping for misuse detection
- **Mobile App**: React Native version
- **Blockchain**: Immutable ownership registry

---

## ⚠️ Important Notes

1. The deepfake resistance percentages are computed heuristically using image analysis metrics (gradient disruption, frequency coherence). For production use, integrate a real deepfake API (e.g., Deepware, FaceCheck).

2. The adversarial protection is designed to confuse GAN-based deepfake models. Effectiveness varies by model and epsilon value.

3. Geometric watermarking requires face detection. Images without detectable faces will only have Layer 1 (hidden ID) protection.
