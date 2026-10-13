import React from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { useDealer } from '../context/DealerContext';
import { useCart } from '../context/CartContext';
import { formatMoney } from './Money';
import {
  IconLogoMark,
  IconCatalogue,
  IconCart,
  IconOrders,
  IconReorder,
  IconAssistant,
  IconAbout,
} from './Icons';

export default function TopBar({
  onToggleAssistant,
  assistantOpen,
}) {
  const { dealers, selectedDealer, selectedDealerId, changeDealer, loading } = useDealer();
  const { totalLines } = useCart();
  const navigate = useNavigate();
  const location = useLocation();

  const handleAboutClick = (e) => {
    e.preventDefault();
    sessionStorage.setItem('dealerdesk_viewing_about', 'true');
    navigate('/');
  };

  const isAssistantPage = location.pathname.includes('/assistant');

  return (
    <header className="portal-topbar" role="banner">
      <div className="topbar-main-row">
        {/* Left: Brand Wordmark */}
        <div className="topbar-brand" onClick={() => navigate('/catalogue')} role="button" tabIndex={0} title="DealerDesk Catalogue">
          <IconLogoMark size={20} />
          <span className="topbar-brand-title">VIKMO DealerDesk</span>
          <span className="brand-badge">B2B</span>
        </div>

        {/* Center / Nav Items */}
        <nav className="topbar-nav" aria-label="Portal primary navigation">
          <NavLink
            to="/catalogue"
            className={({ isActive }) => `topbar-nav-link ${isActive ? 'active' : ''}`}
            aria-current={location.pathname === '/catalogue' ? 'page' : undefined}
          >
            <IconCatalogue size={15} />
            <span>Catalogue</span>
          </NavLink>

          <NavLink
            to="/cart"
            className={({ isActive }) => `topbar-nav-link ${isActive ? 'active' : ''}`}
            aria-current={location.pathname === '/cart' ? 'page' : undefined}
          >
            <IconCart size={15} />
            <span>Cart</span>
            {totalLines > 0 && <span className="nav-badge">{totalLines}</span>}
          </NavLink>

          <NavLink
            to="/orders"
            className={({ isActive }) => `topbar-nav-link ${isActive ? 'active' : ''}`}
            aria-current={location.pathname === '/orders' ? 'page' : undefined}
          >
            <IconOrders size={15} />
            <span>Orders</span>
          </NavLink>

          <NavLink
            to="/reorder"
            className={({ isActive }) => `topbar-nav-link ${isActive ? 'active' : ''}`}
            aria-current={location.pathname === '/reorder' ? 'page' : undefined}
          >
            <IconReorder size={15} />
            <span>Reorder</span>
          </NavLink>

          <NavLink
            to="/assistant"
            className={({ isActive }) => `topbar-nav-link ${isActive ? 'active' : ''}`}
            aria-current={location.pathname === '/assistant' ? 'page' : undefined}
          >
            <IconAssistant size={15} />
            <span>Assistant</span>
          </NavLink>

          <a
            href="#/"
            onClick={handleAboutClick}
            className="topbar-nav-link"
            title="View Landing & System Overview"
          >
            <IconAbout size={15} />
            <span>About</span>
          </a>
        </nav>

        {/* Right: Dealer Selector & Utilities */}
        <div className="topbar-right">
          <div className="dealer-selector-wrap">
            <label htmlFor="dealer-select" className="dealer-label">
              Dealer:
            </label>
            <select
              id="dealer-select"
              value={selectedDealerId}
              onChange={(e) => changeDealer(e.target.value)}
              disabled={loading}
              className="dealer-select"
              aria-label="Select active dealership"
            >
              {dealers.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.dealer_code} — {d.name} ({d.city})
                </option>
              ))}
            </select>
          </div>

          {selectedDealer && (
            <div className="dealer-meta-group">
              <span className="dealer-meta-pill" title="Dealer GSTIN">
                GSTIN: {selectedDealer.gstin || 'Unregistered'}
              </span>
              <span className="dealer-meta-pill" title="Approved trade credit limit">
                Limit: {formatMoney(selectedDealer.credit_limit)}
              </span>
            </div>
          )}

          <div className="search-shortcut-pill" title="Press / anywhere to focus catalogue search">
            <span>Search</span>
            <kbd className="search-shortcut-key">/</kbd>
          </div>

          {!isAssistantPage && (
            <button
              className={`btn btn-sm btn-pill ${assistantOpen ? 'btn-primary' : 'btn-secondary'}`}
              onClick={onToggleAssistant}
              aria-label="Toggle Dealer Assistant panel"
            >
              <IconAssistant size={14} />
              <span>Assistant</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
