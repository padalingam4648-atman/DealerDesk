import React from 'react';
import { useDealer } from '../context/DealerContext';
import { formatMoney } from './Money';
import { IconAssistant } from './Icons';

export default function TopBar({
  onToggleSidebar,
  onToggleAssistant,
  assistantOpen,
}) {
  const { dealers, selectedDealer, selectedDealerId, changeDealer, loading } = useDealer();

  return (
    <header className="portal-topbar" role="banner">
      <div className="topbar-left">
        <button
          className="mobile-nav-toggle"
          onClick={onToggleSidebar}
          aria-label="Toggle menu"
        >
          ☰
        </button>

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
          >
            {dealers.map((d) => (
              <option key={d.id} value={d.id}>
                {d.dealer_code} — {d.name} ({d.city})
              </option>
            ))}
          </select>
        </div>

        {selectedDealer && (
          <>
            <span className="dealer-meta-pill" title="Dealer GSTIN">
              GSTIN: {selectedDealer.gstin || 'Unregistered'}
            </span>
            <span className="dealer-meta-pill" title="Approved credit limit">
              Limit: {formatMoney(selectedDealer.credit_limit)}
            </span>
          </>
        )}
      </div>

      <div className="topbar-right">
        <div className="search-shortcut-pill" title="Press / anywhere to focus catalogue search">
          <span>Search</span>
          <kbd className="search-shortcut-key">/</kbd>
        </div>

        <button
          className={`btn btn-sm ${assistantOpen ? 'btn-primary' : 'btn-secondary'}`}
          onClick={onToggleAssistant}
          aria-label="Toggle Dealer Assistant panel"
        >
          <IconAssistant size={14} />
          <span>Assistant</span>
        </button>
      </div>
    </header>
  );
}
