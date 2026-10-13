// DIGIARMOR AI - Main Layout with Sidebar
import React, { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  Shield, Image, Search, FileText, AlertTriangle,
  Share2, MessageSquare, LayoutDashboard, LogOut, Menu, X
} from 'lucide-react';

const NAV_ITEMS = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { path: '/protect', label: 'Protect Image', icon: Shield },
  { path: '/detect', label: 'Deepfake Detection', icon: Search },
  { path: '/redact', label: 'Redact Document', icon: FileText },
  { path: '/check-misuse', label: 'Check Misuse', icon: AlertTriangle },
  { path: '/share', label: 'Secure Share', icon: Share2 },
  { path: '/scam', label: 'Scam Analyzer', icon: MessageSquare },
];

export default function Layout({
  user,
  onLogout,
  darkMode,
  setDarkMode
}) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  

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
  const navigate = useNavigate();

  const handleLogout = () => {
    onLogout();
    navigate('/login');
  };

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : 'closed'}`}>
        {/* Logo */}
        <div className="sidebar-logo">
          <span className="logo-icon">🛡️</span>
          {sidebarOpen && (
            <div className="topbar-status">
  <span className="status-dot"></span>
  <span>DIGIARMOR AI Active</span>

  <button
    className="theme-toggle"
    onClick={() => setDarkMode(!darkMode)}
    title={darkMode ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
  >
    {darkMode ? '☀️' : '🌙'}
    <span>{darkMode ? 'Light' : 'Dark'}</span>
  </button>
</div>
          )}
        </div>

        {/* Nav Links */}
        <nav className="sidebar-nav">
          {NAV_ITEMS.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={20} />
              {sidebarOpen && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* User & Logout */}
        <div className="sidebar-footer">
          {sidebarOpen && (
            <div className="user-info">
              <div className="user-avatar">{user?.name?.[0]?.toUpperCase() || 'U'}</div>
              <div className="user-details">
                <span className="user-name">{user?.name}</span>
                <span className="user-email">{user?.email}</span>
              </div>
            </div>
          )}
          <button className="logout-btn" onClick={handleLogout} title="Logout">
            <LogOut size={18} />
            {sidebarOpen && <span>Logout</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {/* Top Bar */}
        <header className="topbar">
          <button
            className="menu-toggle"
            onClick={() => setSidebarOpen(!sidebarOpen)}
          >
            {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
          <div className="topbar-status">
            <span className="status-dot"></span>
            <span>DIGIARMOR AI Active</span>
          </div>
        </header>

        {/* Page Content */}
        <div className="page-content">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
