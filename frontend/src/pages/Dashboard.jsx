// DIGIARMOR AI - Dashboard
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Shield, Search, FileText, AlertTriangle, Share2, MessageSquare, TrendingUp, Clock } from 'lucide-react';
import { protectAPI } from '../utils/api';

const FEATURE_CARDS = [
  {
    path: '/protect',
    icon: Shield,
    title: 'Protect Image',
    desc: 'Apply adversarial noise + dual-layer biometric watermarking to prevent deepfake misuse',
    color: '#4f46e5',
    badge: 'Core Feature'
  },
  {
    path: '/detect',
    icon: Search,
    title: 'Deepfake Detection',
    desc: 'Analyze images using ELA, frequency analysis & facial inconsistency detection',
    color: '#dc2626',
    badge: 'AI Powered'
  },
  {
    path: '/redact',
    icon: FileText,
    title: 'Redact Document',
    desc: 'Auto-redact Aadhaar numbers, PAN, DOB and QR codes from identity documents',
    color: '#d97706',
    badge: 'OCR Based'
  },
  {
    path: '/check-misuse',
    icon: AlertTriangle,
    title: 'Check Misuse',
    desc: 'Detect if your protected image has been reused — via hidden ID or landmark signature',
    color: '#059669',
    badge: 'Tracking'
  },
  {
    path: '/share',
    icon: Share2,
    title: 'Secure Share',
    desc: 'Generate expiring view-only links for your protected images',
    color: '#7c3aed',
    badge: 'Expiring Links'
  },
  {
    path: '/scam',
    icon: MessageSquare,
    title: 'Scam Analyzer',
    desc: 'Analyze suspicious messages for phishing, identity theft & financial fraud patterns',
    color: '#e11d48',
    badge: 'NLP Detection'
  },
];

export default function Dashboard({ user }) {
  const [protectedImages, setProtectedImages] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    protectAPI.listImages()
      .then(res => setProtectedImages(res.data.images || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const stats = [
    { label: 'Images Protected', value: protectedImages.length, icon: Shield, color: '#4f46e5' },
    { label: 'Misuse Detected', value: protectedImages.filter(i => i.misuse_detected).length, icon: AlertTriangle, color: '#dc2626' },
    { label: 'Active Since', value: 'Today', icon: Clock, color: '#059669' },
    { label: 'Protection Rate', value: '98%', icon: TrendingUp, color: '#d97706' },
  ];

  return (
    <div className="dashboard">
      {/* Welcome Header */}
      <div className="dashboard-header">
        <div className="welcome-text">
          <h1>Welcome back, {user?.name?.split(' ')[0]} 👋</h1>
          <p>Your digital identity is protected by DIGIARMOR AI</p>
        </div>
        <div className="protection-badge">
          <Shield size={24} />
          <span>PROTECTED</span>
        </div>
      </div>

      {/* Stats Row */}
      <div className="stats-grid">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <div className="stat-card" key={label}>
            <div className="stat-icon" style={{ background: `${color}20`, color }}>
              <Icon size={22} />
            </div>
            <div className="stat-info">
              <span className="stat-value">{loading ? '...' : value}</span>
              <span className="stat-label">{label}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Feature Cards */}
      <div className="section-title">
        <h2>Protection Features</h2>
        <p>Comprehensive digital identity security suite</p>
      </div>

      <div className="feature-grid">
        {FEATURE_CARDS.map(({ path, icon: Icon, title, desc, color, badge }) => (
          <Link to={path} className="feature-card" key={path}>
            <div className="feature-badge" style={{ background: `${color}20`, color }}>
              {badge}
            </div>
            <div className="feature-icon" style={{ color }}>
              <Icon size={32} />
            </div>
            <h3>{title}</h3>
            <p>{desc}</p>
            <div className="feature-arrow" style={{ color }}>→ Get Started</div>
          </Link>
        ))}
      </div>

      {/* Recent Protected Images */}
      {protectedImages.length > 0 && (
        <div className="recent-section">
          <h2>Recent Protected Images</h2>
          <div className="recent-list">
            {protectedImages.slice(0, 5).map((img) => (
              <div className="recent-item" key={img._id}>
                <Shield size={16} className="recent-icon" />
                <div className="recent-info">
                  <span className="recent-filename">{img.original_filename}</span>
                  <span className="recent-id">ID: {img.unique_id}</span>
                </div>
                <div className="recent-status">
                  {img.misuse_detected ? (
                    <span className="badge-danger">⚠ Misuse Detected</span>
                  ) : (
                    <span className="badge-safe">✓ Safe</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
