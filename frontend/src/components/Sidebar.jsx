import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  IconCatalogue,
  IconCart,
  IconOrders,
  IconReorder,
  IconAssistant,
  IconAbout,
} from './Icons';
import { useCart } from '../context/CartContext';

export default function Sidebar({ isOpen, onToggle }) {
  const { totalLines } = useCart();
  const navigate = useNavigate();

  const handleAboutClick = (e) => {
    e.preventDefault();
    // Allow viewing landing page
    navigate('/');
  };

  return (
    <aside className={`portal-sidebar ${isOpen ? 'open' : 'collapsed'}`} aria-label="Main Navigation">
      <div className="sidebar-brand">
        <div>
          <div className="brand-title">VIKMO DealerDesk</div>
          <div className="text-xs text-muted">Bengaluru Hub</div>
        </div>
        <span className="brand-badge">B2B</span>
      </div>

      <nav className="sidebar-nav">
        <NavLink
          to="/catalogue"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <span className="nav-link-content">
            <IconCatalogue size={16} />
            <span>Catalogue</span>
          </span>
        </NavLink>

        <NavLink
          to="/cart"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <span className="nav-link-content">
            <IconCart size={16} />
            <span>Cart</span>
          </span>
          {totalLines > 0 && <span className="nav-badge">{totalLines}</span>}
        </NavLink>

        <NavLink
          to="/orders"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <span className="nav-link-content">
            <IconOrders size={16} />
            <span>Orders</span>
          </span>
        </NavLink>

        <NavLink
          to="/reorder"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <span className="nav-link-content">
            <IconReorder size={16} />
            <span>Reorder</span>
          </span>
        </NavLink>

        <NavLink
          to="/assistant"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
        >
          <span className="nav-link-content">
            <IconAssistant size={16} />
            <span>Assistant</span>
          </span>
        </NavLink>

        <a
          href="#/"
          onClick={handleAboutClick}
          className="nav-link"
          style={{ marginTop: 'auto' }}
        >
          <span className="nav-link-content">
            <IconAbout size={16} />
            <span>About</span>
          </span>
        </a>
      </nav>

      <div className="sidebar-footer">
        <div>ERP Build v1.4</div>
        <div style={{ color: 'var(--text-subtle)', marginTop: '2px' }}>AI/ML Track • Groq LLaMA</div>
      </div>
    </aside>
  );
}
