// DIGIARMOR AI - Document Redaction Page
import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { FileText, Upload, Download, CheckCircle } from 'lucide-react';
import { toast } from 'react-toastify';
import { redactAPI } from '../utils/api';

export default function RedactDocument() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [docType, setDocType] = useState('auto');
  const [method, setMethod] = useState('blur');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [redactedUrl, setRedactedUrl] = useState(null);

  const onDrop = useCallback((accepted) => {
    const f = accepted[0];
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setResult(null);
    setRedactedUrl(null);
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
  onDrop,
  accept: {
    'image/*': ['.jpg', '.jpeg', '.png', '.webp', '.bmp'],
    'application/pdf': ['.pdf']
  },
  maxFiles: 1,
});

  const handleRedact = async () => {
    if (!file) { toast.error('Please upload a document'); return; }
    setLoading(true);

    const formData = new FormData();
    formData.append('document', file);
    formData.append('doc_type', docType);
    formData.append('method', method);

    try {
      const res = await redactAPI.redactDocument(formData);
      setResult(res.data);
      setRedactedUrl(redactAPI.downloadRedacted(res.data.redacted_filename));
      toast.success('Document redacted successfully!');
    } catch (err) {
      toast.error(err.response?.data?.error || 'Redaction failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <FileText size={28} className="page-icon" />
        <div>
          <h1>Redact Document</h1>
          <p>Auto-detect and blur sensitive info from Aadhaar & PAN cards</p>
        </div>
      </div>

      <div className="two-col">
        <div className="card">
          <h3>Upload Identity Document</h3>

          <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''} ${file ? 'has-file' : ''}`}>
            <input {...getInputProps()} />
           {preview ? (
  file?.type === 'application/pdf' ? (
    <div className="pdf-preview">
      <FileText size={60} />
      <p>{file.name}</p>
      <span>PDF document selected</span>
    </div>
  ) : (
    <img
      src={preview}
      alt="Document Preview"
      className="preview-img"
    />
  )
) : (
  <div className="dropzone-placeholder">
    <FileText size={40} />
    <p>Drop Aadhaar, PAN card or PDF</p>
    <span>JPG, PNG, WebP, BMP, PDF</span>
  </div>
)}
          </div>

          <div className="settings-row">
            <div className="setting-group">
              <label>Document Type</label>
              <select value={docType} onChange={e => setDocType(e.target.value)}>
                <option value="auto">Auto Detect</option>
                <option value="aadhaar">Aadhaar Card</option>
                <option value="pan">PAN Card</option>
              </select>
            </div>
            <div className="setting-group">
              <label>Redaction Method</label>
              <select value={method} onChange={e => setMethod(e.target.value)}>
                <option value="blur">Gaussian Blur</option>
                <option value="black">Black Box</option>
                <option value="mosaic">Mosaic/Pixelate</option>
              </select>
            </div>
          </div>

          <div className="redact-features">
            <div className="feature-tag">🔢 Aadhaar Number</div>
            <div className="feature-tag">💳 PAN Number</div>
            <div className="feature-tag">📅 Date of Birth</div>
            <div className="feature-tag">📍 Address</div>
            <div className="feature-tag">📱 Phone Number</div>
            <div className="feature-tag">📷 QR Code</div>
          </div>

          <button className="btn-primary btn-full" onClick={handleRedact} disabled={loading || !file}>
            {loading ? <><span className="spinner"></span> Redacting...</> : <><FileText size={16} /> Redact Document</>}
          </button>
        </div>

        <div className="card">
          <h3>Redacted Document</h3>

          {!result && (
            <div className="empty-state">
              <FileText size={60} className="empty-icon" />
              <p>Redacted document will appear here</p>
            </div>
          )}

          {result && (
            <div className="redact-results">
              <div className="redact-summary">
                <CheckCircle size={20} className="success-icon" />
                <div>
                  <span className="redact-count">{result.redaction_summary?.regions_redacted || 0} regions redacted</span>
                  <span className="redact-type">Detected: {result.redaction_summary?.doc_type_detected}</span>
                </div>
              </div>

              {result.redaction_summary?.sensitive_items_found?.length > 0 && (
                <div className="found-items">
                  <h4>Items Redacted:</h4>
                  <div className="found-tags">
                    {result.redaction_summary.sensitive_items_found.map((item, i) => (
                      <span className="found-tag" key={i}>{item.replace(/_/g, ' ')}</span>
                    ))}
                  </div>
                </div>
              )}

              {redactedUrl && (
  <>
    {result.file_type === 'pdf' ? (
      <iframe
        src={redactedUrl}
        title="Protected PDF"
        className="redacted-pdf-preview"
      />
    ) : (
      <img
        src={redactedUrl}
        alt="Redacted Document"
        className="redacted-preview"
      />
    )}

    <a
      href={redactedUrl}
      download
      className="btn-secondary btn-full"
    >
      <Download size={16} />
      {result.file_type === 'pdf'
        ? ' Download Protected PDF'
        : ' Download Protected Image'}
    </a>
  </>
)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
