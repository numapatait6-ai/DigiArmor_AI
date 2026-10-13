// DIGIARMOR AI - Secure Share Page
import React, { useState, useEffect } from 'react';
import { Share2, Copy, Link, Clock, Eye, Trash2 } from 'lucide-react';
import { toast } from 'react-toastify';
import { shareAPI, protectAPI } from '../utils/api';

export default function SecureShare() {
  const [images, setImages] = useState([]);
  const [selectedImage, setSelectedImage] = useState('');
  const [expiryHours, setExpiryHours] = useState(24);
  const [loading, setLoading] = useState(false);
  const [shareResult, setShareResult] = useState(null);

  useEffect(() => {
    protectAPI.listImages()
      .then(res => setImages(res.data.images || []))
      .catch(() => {});
  }, []);

  const handleCreate = async () => {
    if (!selectedImage) { toast.error('Please select an image'); return; }
    setLoading(true);

    try {
      const res = await shareAPI.createLink(selectedImage, expiryHours);
      setShareResult(res.data);
      toast.success('Secure link created!');
    } catch (err) {
      toast.error(err.response?.data?.error || 'Failed to create link');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(shareResult.share_url);
    toast.success('Link copied to clipboard!');
  };

  const handleRevoke = async () => {
    if (!shareResult?.token) return;
    try {
      await shareAPI.revokeLink(shareResult.token);
      toast.success('Link revoked');
      setShareResult(null);
    } catch (err) {
      toast.error('Failed to revoke link');
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <Share2 size={28} className="page-icon" />
        <div>
          <h1>Secure Share</h1>
          <p>Generate expiring view-only links for your protected images</p>
        </div>
      </div>

      <div className="two-col">
        <div className="card">
          <h3>Create Share Link</h3>

          <div className="form-group">
            <label>Select Protected Image</label>
            <select
              value={selectedImage}
              onChange={e => setSelectedImage(e.target.value)}
              className="full-select"
            >
              <option value="">-- Choose an image --</option>
              {images.map(img => (
                <option value={img._id} key={img._id}>
                  {img.original_filename} ({img.unique_id})
                </option>
              ))}
            </select>
            {images.length === 0 && (
              <p className="hint">No protected images yet. Go to Protect Image first.</p>
            )}
          </div>

          <div className="form-group">
            <label>Link Expiry Duration</label>
            <div className="expiry-options">
              {[1, 6, 24, 48, 168].map(h => (
                <button
                  key={h}
                  className={`expiry-btn ${expiryHours === h ? 'active' : ''}`}
                  onClick={() => setExpiryHours(h)}
                >
                  {h === 1 ? '1h' : h === 6 ? '6h' : h === 24 ? '24h' : h === 48 ? '2d' : '7d'}
                </button>
              ))}
            </div>
          </div>

          <div className="share-features">
            <div className="share-feature"><Clock size={14} /> Auto-expires after {expiryHours}h</div>
            <div className="share-feature"><Eye size={14} /> View-only, no download</div>
            <div className="share-feature"><Link size={14} /> Max 10 views</div>
          </div>

          <button className="btn-primary btn-full" onClick={handleCreate} disabled={loading || !selectedImage}>
            {loading ? <><span className="spinner"></span> Creating...</> : <><Share2 size={16} /> Generate Secure Link</>}
          </button>
        </div>

        <div className="card">
          <h3>Generated Link</h3>

          {!shareResult && (
            <div className="empty-state">
              <Share2 size={60} className="empty-icon" />
              <p>Your secure link will appear here</p>
            </div>
          )}

          {shareResult && (
            <div className="share-result">
              <div className="share-url-box">
                <code className="share-url">{shareResult.share_url}</code>
                <button className="copy-btn" onClick={handleCopy}>
                  <Copy size={16} />
                </button>
              </div>

              <div className="share-meta">
                <div className="meta-row">
                  <Clock size={14} />
                  <span>Expires: {new Date(shareResult.expires_at).toLocaleString()}</span>
                </div>
                <div className="meta-row">
                  <Eye size={14} />
                  <span>Max {shareResult.max_views} views</span>
                </div>
              </div>

              <div className="share-tip">
                ✓ Anyone with this link can view the protected image once.<br />
                The link will automatically expire after {expiryHours} hours.
              </div>

              <button className="btn-danger-outline" onClick={handleRevoke}>
                <Trash2 size={14} /> Revoke Link Now
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
