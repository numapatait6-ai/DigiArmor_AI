// DIGIARMOR AI - Check Misuse Page
import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { AlertTriangle, Upload, CheckCircle, ShieldOff } from 'lucide-react';
import { toast } from 'react-toastify';
import { protectAPI } from '../utils/api';

export function CheckMisuse() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const onDrop = useCallback((accepted) => {
    const f = accepted[0];
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setResult(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'image/*': ['.jpg', '.jpeg', '.png', '.webp'] },
    maxFiles: 1,
  });

  const handleCheck = async () => {
    if (!file) { toast.error('Please upload an image to check'); return; }
    setLoading(true);

    const formData = new FormData();
    formData.append('image', file);

    try {
      const res = await protectAPI.checkMisuse(formData);
      setResult(res.data);
    } catch (err) {
      toast.error(err.response?.data?.error || 'Check failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <AlertTriangle size={28} className="page-icon" />
        <div>
          <h1>Check Image Misuse</h1>
          <p>Detect if a protected image has been reused — via hidden ID or landmark fingerprint</p>
        </div>
      </div>

      <div className="two-col">
        <div className="card">
          <h3>Upload Suspicious Image</h3>

          <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''} ${file ? 'has-file' : ''}`}>
            <input {...getInputProps()} />
            {preview ? (
              <img src={preview} alt="Preview" className="preview-img" />
            ) : (
              <div className="dropzone-placeholder">
                <Upload size={40} />
                <p>Drop suspected image here</p>
                <span>The system will check both layers</span>
              </div>
            )}
          </div>

          <div className="info-box">
            <AlertTriangle size={14} />
            <span>Layer 1: Extracts hidden steganographic ID · Layer 2: Compares facial landmark signatures</span>
          </div>

          <button className="btn-danger btn-full" onClick={handleCheck} disabled={loading || !file}>
            {loading ? <><span className="spinner"></span> Checking...</> : <><AlertTriangle size={16} /> Check for Misuse</>}
          </button>
        </div>

        <div className="card">
          <h3>Misuse Check Result</h3>

          {!result && (
            <div className="empty-state">
              <AlertTriangle size={60} className="empty-icon" />
              <p>Upload a suspicious image to check</p>
            </div>
          )}

          {result && (
            <div className="misuse-results">
              {result.misuse_detected ? (
                <div className="misuse-alert">
                  <ShieldOff size={40} className="misuse-icon" />
                  <h3>⚠ MISUSE DETECTED</h3>
                  <div className="misuse-details">
                    <div className="detail-row">
                      <span>Protected Image ID:</span>
                      <code>{result.protected_image_id}</code>
                    </div>
                    <div className="detail-row">
                      <span>Detection Method:</span>
                      <span className="badge-info">{result.match_method?.replace('_', ' ')}</span>
                    </div>
                    <div className="detail-row">
                      <span>Confidence:</span>
                      <span className="confidence">{(result.confidence * 100).toFixed(1)}%</span>
                    </div>
                    {result.original_filename && (
                      <div className="detail-row">
                        <span>Original File:</span>
                        <span>{result.original_filename}</span>
                      </div>
                    )}
                  </div>
                  <p className="misuse-message">This image matches a protected identity in the DIGIARMOR database. Misuse alert has been logged.</p>
                </div>
              ) : (
                <div className="no-misuse">
                  <CheckCircle size={40} className="safe-icon" />
                  <h3>✓ No Misuse Detected</h3>
                  <p>This image does not match any protected identity in the database.</p>
                  {result.hidden_id_found && (
                    <p className="found-id">Hidden ID found: <code>{result.extracted_id}</code></p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default CheckMisuse;
