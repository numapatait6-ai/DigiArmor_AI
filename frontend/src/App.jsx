// DIGIARMOR AI - Main App Component
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import ProtectImage from './pages/ProtectImage';
import DetectDeepfake from './pages/DetectDeepfake';
import RedactDocument from './pages/RedactDocument';
import CheckMisuse from './pages/CheckMisuse';
import SecureShare from './pages/SecureShare';
import ScamAnalyzer from './pages/ScamAnalyzer';
import Layout from './components/Layout';

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [darkMode, setDarkMode] = useState(() => {
  return localStorage.getItem('digiarmor_theme') !== 'light';
});

useEffect(() => {
  document.documentElement.setAttribute(
    'data-theme',
    darkMode ? 'dark' : 'light'
  );

  localStorage.setItem(
    'digiarmor_theme',
    darkMode ? 'dark' : 'light'
  );
}, [darkMode]);

  useEffect(() => {
    const stored = localStorage.getItem('digiarmor_user');
    const token = localStorage.getItem('digiarmor_token');
    if (stored && token) {
      setUser(JSON.parse(stored));
    }
    setLoading(false);
  }, []);

  const handleLogin = (userData, token) => {
    localStorage.setItem('digiarmor_token', token);
    localStorage.setItem('digiarmor_user', JSON.stringify(userData));
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('digiarmor_token');
    localStorage.removeItem('digiarmor_user');
    setUser(null);
  };

  if (loading) {
    return (
      <div className="loading-screen">
        <div className="shield-logo">🛡️</div>
        <p>Loading DIGIARMOR AI...</p>
      </div>
    );
  }

  return (
    <Router>
      <ToastContainer position="top-right" autoClose={4000} theme={darkMode ? 'dark' : 'light'} />
      <Routes>
        <Route path="/login" element={
          user ? <Navigate to="/dashboard" /> : <Login onLogin={handleLogin} />
        } />
        <Route path="/register" element={
          user ? <Navigate to="/dashboard" /> : <Register onLogin={handleLogin} />
        } />
        <Route path="/" element={
          user ? (
            <Layout
  user={user}
  onLogout={handleLogout}
  darkMode={darkMode}
  setDarkMode={setDarkMode}
/>
          ) : <Navigate to="/login" />
        }>
          <Route index element={<Navigate to="/dashboard" />} />
          <Route path="dashboard" element={<Dashboard user={user} />} />
          <Route path="protect" element={<ProtectImage />} />
          <Route path="detect" element={<DetectDeepfake />} />
          <Route path="redact" element={<RedactDocument />} />
          <Route path="check-misuse" element={<CheckMisuse />} />
          <Route path="share" element={<SecureShare />} />
          <Route path="scam" element={<ScamAnalyzer />} />
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" />} />
      </Routes>
    </Router>
  );
}

export default App;
