// DIGIARMOR AI - Frontend API Client
import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

// Create axios instance
const api = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,
});

// Inject JWT token on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('digiarmor_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle auth errors
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('digiarmor_token');
      localStorage.removeItem('digiarmor_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

// ─── AUTH ─────────────────────────────────────────────────────────────────────
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  verify: () => api.get('/auth/verify'),
};

// ─── PROTECTION ──────────────────────────────────────────────────────────────
export const protectAPI = {
  protectImage: (formData, onProgress) =>
    api.post('/protect/image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: onProgress,
    }),

  checkMisuse: (formData) =>
    api.post('/protect/check-misuse', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  listImages: () => api.get('/protect/images'),

  downloadProtected: (filename) =>
    `${BASE_URL}/protect/download/${filename}`,
};

// ─── DETECTION ───────────────────────────────────────────────────────────────
export const detectAPI = {
  detectDeepfake: (formData) =>
    api.post('/detect/deepfake', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  detectTamper: (formData) =>
    api.post('/detect/tamper', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  analyzeScamMessage: (message) =>
    api.post('/detect/scam-message', { message }),
};

// ─── REDACTION ───────────────────────────────────────────────────────────────
export const redactAPI = {
  redactDocument: (formData) =>
    api.post('/redact/document', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),

  downloadRedacted: (filename) =>
    `${BASE_URL}/redact/download/${filename}`,
};

// ─── SHARING ─────────────────────────────────────────────────────────────────
export const shareAPI = {
  createLink: (imageId, expiryHours = 24) =>
    api.post('/share/create', { image_id: imageId, expiry_hours: expiryHours }),

  getLinkInfo: (token) => api.get(`/share/info/${token}`),

  revokeLink: (token) => api.delete(`/share/revoke/${token}`),

  getViewUrl: (token) => `${BASE_URL}/share/view/${token}`,
};

export default api;
