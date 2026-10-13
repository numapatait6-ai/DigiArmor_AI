// DIGIARMOR AI - Deepfake Detection Page
import React, { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Search, Upload, AlertTriangle, CheckCircle, Info } from 'lucide-react';
import { toast } from 'react-toastify';
import { detectAPI } from '../utils/api';

export default function DetectDeepfake() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [mode, setMode] = useState('deepfake'); // 'deepfake' | 'tamper'
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

  const handleDetect = async () => {
    if (!file) { toast.error('Please upload an image'); return; }
    setLoading(true);

    const formData = new FormData();
    formData.append('image', file);

    try {
      const res = mode === 'deepfake'
        ? await detectAPI.detectDeepfake(formData)
        : await detectAPI.detectTamper(formData);
      setResult(res.data);
    } catch (err) {
      toast.error(err.response?.data?.error || 'Detection failed');
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (level) => {
    if (!level) return '#6b7280';
    if (level === 'HIGH') return '#dc2626';
    if (level === 'MEDIUM') return '#d97706';
    return '#059669';
  };

  const getRiskLevel = (probability) => {
    if (probability > 0.80) return 'HIGH';
    if (probability > 0.40) return 'MEDIUM';
    return 'LOW';
  };

  return (
    <div className="page">
      <div className="page-header">
        <Search size={28} className="page-icon" />
        <div>
          <h1>Deepfake & Tamper Detection</h1>
          <p>Multi-layer AI analysis to identify manipulated or AI-generated images</p>
        </div>
      </div>

      {/* Mode Selector */}
      <div className="mode-tabs">
        <button className={`mode-tab ${mode === 'deepfake' ? 'active' : ''}`}
          onClick={() => { setMode('deepfake'); setResult(null); }}>
          🤖 Deepfake Detection
        </button>
        <button className={`mode-tab ${mode === 'tamper' ? 'active' : ''}`}
          onClick={() => { setMode('tamper'); setResult(null); }}>
          🔍 Tamper Detection
        </button>
      </div>

      <div className="two-col">
        {/* Upload */}
        <div className="card">
          <h3>Upload Image for Analysis</h3>

          <div {...getRootProps()} className={`dropzone ${isDragActive ? 'active' : ''} ${file ? 'has-file' : ''}`}>
            <input {...getInputProps()} />
            {preview ? (
              <img src={preview} alt="Preview" className="preview-img" />
            ) : (
              <div className="dropzone-placeholder">
                <Upload size={40} />
                <p>Drop image to analyze</p>
                <span>JPG, PNG, WebP</span>
              </div>
            )}
          </div>

          {file && <div className="file-info"><span>📷 {file.name}</span></div>}

          <div className="info-box">
            <Info size={14} />
            <span>
              {mode === 'deepfake'
                ? 'Uses an AI deepfake detection model to estimate the probability that the image is AI-generated or manipulated'
                : 'Uses Error Level Analysis and block noise consistency checks'}
            </span>
          </div>

          <button className="btn-primary btn-full" onClick={handleDetect} disabled={loading || !file}>
            {loading ? <><span className="spinner"></span> Analyzing...</> : <><Search size={16} /> Run Analysis</>}
          </button>
        </div>

        {/* Results */}
        <div className="card">
          <h3>Analysis Results</h3>

          {!result && (
            <div className="empty-state">
              <Search size={60} className="empty-icon" />
              <p>Upload an image and run analysis</p>
            </div>
          )}

        {result && (
            <div className="detect-results">
              {/* Verdict Banner */}
{mode === 'deepfake' && result.status === 'no_face' ? ( 
      <div className="verdict-banner" style={{
        borderColor: '#6b7280',
        background: '#6b728015'
      }}>
      <div className="verdict-icon">
        <Info size={28} color="#6b7280" />
      </div>

    <div>
      <div
        className="verdict-text"
        style={{ color: '#6b7280' }}
      >
        No Face Detected
      </div>

      <div className="confidence-score">
        {result.message || 'A clear face could not be detected.'}
      </div>
    </div>
     </div>
) : mode === 'deepfake' &&
result.status !== 'error' &&
result.deepfake_probability != null ? (() => {
                const probability = result.deepfake_probability;

                let riskLevel;
                let verdict;

                if (probability >= 0.80) {
                  riskLevel = 'HIGH';
                  verdict = 'High Risk';
                } else if (probability > 0.40) {
                  riskLevel = 'MEDIUM';
                  verdict = 'Suspicious';
                } else {
                  riskLevel = 'LOW';
                  verdict = 'Likely Authentic';
                }

                const riskColor = getRiskColor(riskLevel);

                return (
                  <div
                    className="verdict-banner"
                    style={{
                      borderColor: riskColor,
                      background: `${riskColor}15`
                    }}
                  >
                    <div className="verdict-icon">
                      {riskLevel === 'LOW' ? (
                        <CheckCircle size={28} color={riskColor} />
                      ) : (
                        <AlertTriangle size={28} color={riskColor} />
                      )}
                    </div>

                    <div>
                      <div
                        className="verdict-text"
                        style={{ color: riskColor }}
                      >
                        {verdict}
                      </div>

                      <div className="confidence-score">
                        Deepfake Probability: {(probability * 100).toFixed(1)}%
                      </div>
                    </div>
                  </div>
                );
              })() : (
                /* Existing tamper detection result */
                <div className="verdict-banner" style={{
                  borderColor: getRiskColor(
                    result.risk_level ||
                    (result.tamper_detected ? 'HIGH' : 'LOW')
                  ),
                  background: `${getRiskColor(
                    result.risk_level ||
                    (result.tamper_detected ? 'HIGH' : 'LOW')
                  )}15`
                }}>
                  <div className="verdict-icon">
                    {result.tamper_detected
                      ? <AlertTriangle size={28} color={getRiskColor('HIGH')} />
                      : <CheckCircle size={28} color="#059669" />
                    }
                  </div>

                  <div>
                    <div
                      className="verdict-text"
                      style={{
                        color: getRiskColor(
                          result.risk_level ||
                          (result.tamper_detected ? 'HIGH' : 'LOW')
                        )
                      }}
                    >
                      {result.verdict ||
                        (result.tamper_detected ? 'TAMPERED' : 'AUTHENTIC')}
                    </div>

                    {result.tamper_confidence !== undefined && (
                      <div className="confidence-score">
                        Tamper Confidence: {result.tamper_confidence}%
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Deepfake Mode Details */}
              {mode === 'deepfake' && result.ela_analysis && (
                <div className="analysis-details">
                  <h4>Analysis Breakdown</h4>
                  <div className="detail-grid">
                    <div className="detail-item">
                      <span className="detail-label">ELA Score</span>
                      <span className="detail-value">{(result.ela_analysis?.tampering_score * 100)?.toFixed(1)}%</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Freq. Anomaly</span>
                      <span className="detail-value">{(result.frequency_analysis?.freq_anomaly_score * 100)?.toFixed(1)}%</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Facial Score</span>
                      <span className="detail-value">{(result.facial_analysis?.inconsistency_score * 100)?.toFixed(1)}%</span>
                    </div>
                    <div className="detail-item">
                      <span className="detail-label">Faces Found</span>
                      <span className="detail-value">{result.facial_analysis?.faces_detected || 0}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Indicators */}
              {result.indicators?.length > 0 && (
                <div className="indicators-list">
                  <h4>Detected Indicators</h4>
                  {result.indicators.map((ind, i) => (
                    <div className="indicator-item" key={i}>
                      <AlertTriangle size={12} className="ind-icon" />
                      <span>{ind}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Recommendation */}
              {result.recommendation && (
                <div className="recommendation">
                  <Info size={14} />
                  <span>{result.recommendation}</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
