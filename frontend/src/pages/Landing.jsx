import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkHealth, fetchProducts, fetchDealers } from '../api';
import Money from '../components/Money';
import StatusBadge from '../components/StatusBadge';
import { IconExternalLink, IconClose } from '../components/Icons';

export default function Landing() {
  const navigate = useNavigate();
  const [isOnline, setIsOnline] = useState(null);
  const [productCount, setProductCount] = useState(null);
  const [dealerCount, setDealerCount] = useState(null);
  const [previewRows, setPreviewRows] = useState([]);
  const [loadingPreview, setLoadingPreview] = useState(true);
  const [showContractModal, setShowContractModal] = useState(false);

  useEffect(() => {
    // If intro was previously seen and user didn't specifically request about view, redirect to catalogue
    const introSeen = sessionStorage.getItem('dealerdesk_intro_seen');
    const viewingAbout = sessionStorage.getItem('dealerdesk_viewing_about');
    if (introSeen === 'true' && viewingAbout !== 'true') {
      navigate('/catalogue', { replace: true });
      return;
    }
    // Clear viewing_about once landed
    sessionStorage.removeItem('dealerdesk_viewing_about');

    let isMounted = true;

    // Optional health check for small dot
    checkHealth()
      .then(() => isMounted && setIsOnline(true))
      .catch(() => isMounted && setIsOnline(false));

    // Fetch product count and 6 real preview rows from GET /api/products/
    fetchProducts({ pageSize: 6 })
      .then((data) => {
        if (!isMounted) return;
        setProductCount(data.count);
        setPreviewRows(data.results || []);
        setLoadingPreview(false);
      })
      .catch(() => {
        if (isMounted) setLoadingPreview(false);
      });

    // Fetch dealer count from GET /api/dealers/
    fetchDealers({ pageSize: 1 })
      .then((data) => {
        if (isMounted) setDealerCount(data.count);
      })
      .catch(() => {});

    return () => {
      isMounted = false;
    };
  }, [navigate]);

  const handleOpenPortal = (e) => {
    if (e) e.preventDefault();
    sessionStorage.setItem('dealerdesk_intro_seen', 'true');
    sessionStorage.removeItem('dealerdesk_viewing_about');
    navigate('/catalogue');
  };

  return (
    <div className="landing-page">
      {/* Header Strip */}
      <header className="landing-header" role="banner">
        <div className="landing-brand">
          <span>VIKMO DealerDesk</span>
          <span className="landing-brand-tag">Trade Portal</span>
        </div>

        <div className="landing-nav-actions">
          {isOnline !== null && (
            <div className="health-dot-wrap" title={`Backend status: ${isOnline ? 'Online' : 'Offline'}`}>
              <span className={`health-dot ${isOnline ? 'online' : ''}`} />
              <span>{isOnline ? 'API online' : 'API offline'}</span>
            </div>
          )}
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={handleOpenPortal}
          >
            Open portal
          </button>
        </div>
      </header>

      {/* Main Split Layout */}
      <main className="landing-main" role="main">
        {/* Left Column: ~640px text with generous whitespace */}
        <section className="landing-content-col" aria-labelledby="landing-heading">
          <div className="landing-hero-block">
            <h1 id="landing-heading" className="landing-headline headline-fade">
              Parts, stock and orders for 25 dealers, in one place.
            </h1>
            <p className="landing-subhead">
              A dealer desk for a Bengaluru motorcycle and car parts distributor,
              built on Django, PostgreSQL and a Groq-powered assistant.
            </p>

            <div className="landing-cta-group">
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleOpenPortal}
              >
                Open the portal
              </button>
              <button
                type="button"
                className="btn-link text-sm"
                onClick={() => setShowContractModal(true)}
              >
                Read the API contract
              </button>
            </div>
          </div>

          {/* What it does: Simple 4-item list */}
          <div>
            <div className="section-heading">What it does</div>
            <ul className="what-it-does-list">
              <li className="what-it-does-item">
                <strong>Catalogue and stock:</strong>
                <span>
                  600 products, live inventory, search by part, brand or vehicle.
                </span>
              </li>
              <li className="what-it-does-item">
                <strong>Draft orders:</strong>
                <span>
                  GST at 18% per line, order numbers like ORD-YYYYMMDD-NNNN.
                </span>
              </li>
              <li className="what-it-does-item">
                <strong>Dealer Assistant:</strong>
                <span>
                  answers from live data, creates drafts, never confirms.
                </span>
              </li>
              <li className="what-it-does-item">
                <strong>Demand forecast and reorder:</strong>
                <span>
                  4-week forecast for 40 SKUs with safety-stock reorder suggestions.
                </span>
              </li>
            </ul>
          </div>

          {/* By the numbers: Live API counts & Phase 2 ML stats */}
          <div>
            <div className="section-heading">By the numbers</div>
            <div className="numbers-strip">
              <div className="number-cell">
                <span className="number-val">
                  {productCount !== null ? productCount : '...'}
                </span>
                <span className="number-label">Products in catalogue</span>
              </div>
              <div className="number-cell">
                <span className="number-val">
                  {dealerCount !== null ? dealerCount : '...'}
                </span>
                <span className="number-label">Authorized dealers</span>
              </div>
              <div className="number-cell">
                <span className="number-val">22.06%</span>
                <span className="number-label">Forecast WAPE (Phase 2)</span>
              </div>
            </div>
          </div>

          {/* How it is built: Real code components */}
          <div>
            <div className="section-heading">How it is built</div>
            <p className="tech-details">
              Engineered strictly with <strong>Django & DRF</strong>, <strong>PostgreSQL</strong>,
              real-time <strong>Groq tool-calling</strong> with BM25 retrieval, and a direct
              multi-horizon <strong>LightGBM + SBA</strong> forecasting model isolated in ml/.
            </p>
            <div className="tech-links">
              <a
                href="https://github.com/padalingam4648-atman/DealerDesk"
                target="_blank"
                rel="noreferrer"
                className="text-xs"
              >
                Repository <IconExternalLink size={12} />
              </a>
              <span className="text-muted text-xs">•</span>
              <a href="#/catalogue" onClick={handleOpenPortal} className="text-xs">
                Launch App
              </a>
            </div>
          </div>
        </section>

        {/* Right Side: Static, non-interactive crop of the catalogue table inside a bordered frame */}
        <aside className="crop-preview-frame" aria-label="Live catalogue sample">
          <div className="preview-frame-header">
            <span className="preview-frame-title">Catalogue Live Preview</span>
            <span className="preview-frame-badge">Live API sample</span>
          </div>

          <table className="data-table" style={{ fontSize: '13px' }}>
            <thead>
              <tr>
                <th style={{ width: '95px' }}>SKU</th>
                <th>Part Description</th>
                <th>Fitment</th>
                <th className="text-right" style={{ width: '90px' }}>Price</th>
                <th className="text-right" style={{ width: '85px' }}>Stock</th>
              </tr>
            </thead>
            <tbody>
              {loadingPreview ? (
                Array.from({ length: 6 }).map((_, i) => (
                  <tr key={i} className="skeleton-row">
                    <td><div style={{ width: '80%' }} /></td>
                    <td><div style={{ width: '90%' }} /></td>
                    <td><div style={{ width: '70%' }} /></td>
                    <td><div style={{ width: '60%', marginLeft: 'auto' }} /></td>
                    <td><div style={{ width: '50%', marginLeft: 'auto' }} /></td>
                  </tr>
                ))
              ) : previewRows.length > 0 ? (
                previewRows.map((item) => (
                  <tr key={item.sku}>
                    <td className="text-mono" style={{ color: 'var(--accent)', fontWeight: 600 }}>
                      {item.sku}
                    </td>
                    <td style={{ maxWidth: '170px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.name}
                    </td>
                    <td className="text-muted" style={{ maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {item.vehicle_fitment}
                    </td>
                    <td className="text-right">
                      <Money amount={item.price} />
                    </td>
                    <td className="text-right">
                      <StatusBadge type="stock" stock={item.stock} />
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="text-center text-muted" style={{ height: '80px' }}>
                    Preview data not available
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </aside>
      </main>

      {/* Footer */}
      <footer className="landing-footer" role="contentinfo">
        <div>AI/ML track submission • Bengaluru Distributor Desk</div>
        <div>
          <a
            href="https://github.com/padalingam4648-atman/DealerDesk#readme"
            target="_blank"
            rel="noreferrer"
          >
            System Documentation
          </a>
        </div>
      </footer>

      {/* API Contract Modal */}
      {showContractModal && (
        <div
          className="drawer-backdrop"
          onClick={() => setShowContractModal(false)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="drawer"
            style={{ width: '560px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="drawer-header">
              <div>
                <h2>DealerDesk REST API Specification</h2>
                <div className="text-xs text-muted">Contract specifications and live endpoints</div>
              </div>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setShowContractModal(false)}
              >
                <IconClose size={16} />
              </button>
            </div>
            <div className="drawer-body" style={{ fontSize: '13px' }}>
              <div>
                <h3 style={{ fontSize: '14px', marginBottom: '4px' }}>System Endpoints</h3>
                <ul style={{ paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <li><code>GET /api/health/</code> — System liveness status</li>
                  <li><code>GET /api/products/</code> — Paginated spare parts catalogue (600 items)</li>
                  <li><code>GET /api/dealers/</code> — Registered dealer accounts</li>
                  <li><code>POST /api/orders/</code> — DRAFT purchase order creation</li>
                  <li><code>GET /api/orders/</code> — Dealer order history</li>
                  <li><code>GET /api/reorder-suggestions/</code> — Statistical inventory replenishment</li>
                  <li><code>POST /api/assistant/chat/</code> — Grounded conversational assistant</li>
                </ul>
              </div>
              <div style={{ marginTop: '12px' }}>
                <h3 style={{ fontSize: '14px', marginBottom: '4px' }}>Business Rules</h3>
                <p className="text-muted">
                  GST is calculated at 18% per line item rounded to the paisa (ROUND_HALF_UP).
                  Orders are created in DRAFT state with unique sequential order IDs.
                </p>
              </div>
            </div>
            <div className="drawer-footer">
              <button
                type="button"
                className="btn btn-primary"
                style={{ width: '100%' }}
                onClick={() => {
                  setShowContractModal(false);
                  handleOpenPortal();
                }}
              >
                Proceed to Live Portal
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
