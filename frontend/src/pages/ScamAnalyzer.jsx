// DIGIARMOR AI - Scam Message Analyzer
import React, { useState } from 'react';
import { MessageSquare, AlertTriangle, CheckCircle, Send } from 'lucide-react';
import { toast } from 'react-toastify';
import { detectAPI } from '../utils/api';

const SAMPLE_MESSAGES = [
  "Congratulations! You have won Rs 5 Lakh in the BSNL lottery! Send your Aadhaar card and bank details to claim your prize immediately.",
  "URGENT: Your SBI account will be blocked. Complete KYC by clicking http://bit.ly/sbi-kyc and uploading your PAN card photo.",
  "Hi, this is your team lead. Please share your Aadhaar OTP for verification of salary account.",
  "Your Amazon package is on hold. Pay Rs 29 delivery fee at: http://amzn-delivery.xyz/pay",
];

export default function ScamAnalyzer() {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const handleAnalyze = async () => {
    if (!message.trim()) { toast.error('Please enter a message to analyze'); return; }
    setLoading(true);

    try {
      const res = await detectAPI.analyzeScamMessage(message);
      setResult(res.data);
    } catch (err) {
      toast.error(err.response?.data?.error || 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (level) => {
    if (level === 'HIGH') return '#dc2626';
    if (level === 'MEDIUM') return '#d97706';
    return '#059669';
  };

  return (
    <div className="page">
      <div className="page-header">
        <MessageSquare size={28} className="page-icon" />
        <div>
          <h1>Scam Message Analyzer</h1>
          <p>Detect phishing, identity theft & financial fraud in suspicious messages</p>
        </div>
      </div>

      <div className="two-col">
        <div className="card">
          <h3>Enter Suspicious Message</h3>

          <textarea
            className="scam-textarea"
            placeholder="Paste the suspicious message here..."
            value={message}
            onChange={e => setMessage(e.target.value)}
            rows={8}
          />

          <div className="sample-messages">
            <p>Try a sample:</p>
            {SAMPLE_MESSAGES.map((msg, i) => (
              <button key={i} className="sample-btn" onClick={() => { setMessage(msg); setResult(null); }}>
                Sample {i + 1}
              </button>
            ))}
          </div>

          <button className="btn-primary btn-full" onClick={handleAnalyze} disabled={loading || !message.trim()}>
            {loading ? <><span className="spinner"></span> Analyzing...</> : <><Send size={16} /> Analyze Message</>}
          </button>
        </div>

        <div className="card">
          <h3>Analysis Result</h3>

          {!result && (
            <div className="empty-state">
              <MessageSquare size={60} className="empty-icon" />
              <p>Paste a message and click Analyze</p>
            </div>
          )}

          {result && (
            <div className="scam-result">
              {/* Risk Gauge */}
              <div className="risk-gauge">
                <div className="gauge-label">Risk Score</div>
                <div className="gauge-bar-container">
                  <div
                    className="gauge-bar"
                    style={{
                      width: `${result.risk_score}%`,
                      background: getRiskColor(result.risk_level)
                    }}
                  ></div>
                </div>
                <div className="gauge-value" style={{ color: getRiskColor(result.risk_level) }}>
                  {result.risk_score}/100
                </div>
              </div>

              {/* Verdict */}
              <div className="scam-verdict" style={{
                background: `${getRiskColor(result.risk_level)}15`,
                borderColor: getRiskColor(result.risk_level)
              }}>
                {result.risk_level === 'HIGH' ? (
                  <AlertTriangle size={24} color={getRiskColor(result.risk_level)} />
                ) : (
                  <CheckCircle size={24} color={getRiskColor(result.risk_level)} />
                )}
                <div>
                  <div className="verdict-main" style={{ color: getRiskColor(result.risk_level) }}>
                    {result.verdict}
                  </div>
                </div>
              </div>

              {/* Indicators */}
              {result.indicators?.length > 0 && (
                <div className="scam-indicators">
                  <h4>⚠ Detected Patterns:</h4>
                  {result.indicators.map((ind, i) => (
                    <div key={i} className="indicator-item">
                      <span className="indicator-bullet">•</span>
                      <span>{ind}</span>
                    </div>
                  ))}
                </div>
              )}

              {/* Recommendation */}
              <div className="scam-recommendation" style={{ borderColor: getRiskColor(result.risk_level) }}>
                <strong>Recommendation:</strong> {result.recommendation}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
