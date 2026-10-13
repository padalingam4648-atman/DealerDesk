import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { checkHealth, fetchProducts, fetchDealers } from '../api';
import Money from '../components/Money';
import StatusBadge from '../components/StatusBadge';
import {
  IconLogoMark,
  IconSunburst,
  IconDiagonalArrow,
  IconArrowRight,
  IconExternalLink,
  IconClose,
} from '../components/Icons';

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

    // Health check for status dot
    checkHealth()
      .then(() => isMounted && setIsOnline(true))
      .catch(() => isMounted && setIsOnline(false));

    // Fetch live product count and 6 preview rows from GET /api/products/
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

    // Fetch live dealer count from GET /api/dealers/
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
    <div className="landing-viewport-wrapper">
      <div className="landing-frame">
        {/* Navigation Bar matching reference top-bar aesthetic */}
        <header className="landing-header" role="banner">
          <div className="landing-brand">
            <IconLogoMark size={20} />
            <span className="landing-brand-text">VIKMO DealerDesk</span>
            <span className="landing-brand-tag">Trade Portal</span>
          </div>

          <nav className="landing-nav-center" aria-label="Page navigation">
            <a href="#what-it-does" className="landing-nav-link">Overview</a>
            <a href="#live-preview" className="landing-nav-link">
              <span>Catalogue</span>
              <span className="landing-nav-counter">25</span>
            </a>
            <a href="#by-the-numbers" className="landing-nav-link">Metrics</a>
            <a href="#architecture" className="landing-nav-link">Architecture</a>
          </nav>

          <div className="landing-nav-actions">
            {isOnline !== null && (
              <div className="health-dot-wrap" title={`Backend status: ${isOnline ? 'Online' : 'Offline'}`}>
                <span className={`health-dot ${isOnline ? 'online' : ''}`} />
                <span className="health-dot-label">{isOnline ? 'API online' : 'API offline'}</span>
              </div>
            )}
            <button
              type="button"
              className="btn btn-secondary btn-sm btn-pill"
              onClick={handleOpenPortal}
            >
              <span>Open portal</span>
              <IconDiagonalArrow size={12} />
            </button>
          </div>
        </header>

        {/* Hero Area */}
        <section className="landing-hero-section" aria-labelledby="landing-heading">
          <div className="landing-hero-grid">
            {/* Left Hero Column: Eyebrow + Headline + Pillars */}
            <div className="landing-hero-left">
              <div className="section-eyebrow">
                <span className="eyebrow-square" />
                <span>B2B Distribution & Parts Platform</span>
              </div>
              <h1 id="landing-heading" className="landing-headline headline-fade">
                Parts, stock and orders for 25 dealers, in one place.
              </h1>
              <div className="landing-hero-pillars">
                <span className="hero-pillar-item">+ 600 Live SKUs</span>
                <span className="hero-pillar-item">+ Exact 18% GST</span>
                <span className="hero-pillar-item">+ Groq Assistant</span>
                <span className="hero-pillar-item">+ ML Forecast</span>
              </div>
            </div>

            {/* Right Hero Column: Subhead + CTAs */}
            <div className="landing-hero-right">
              <p className="landing-subhead">
                A dealer desk for a Bengaluru motorcycle and car parts distributor,
                built on Django, PostgreSQL and a Groq-powered assistant.
              </p>
              <div className="landing-cta-group">
                <button
                  type="button"
                  className="btn btn-primary btn-pill landing-btn-primary"
                  onClick={handleOpenPortal}
                >
                  <span>Open the portal</span>
                  <IconDiagonalArrow size={14} />
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-pill landing-btn-secondary"
                  onClick={() => setShowContractModal(true)}
                >
                  <span>API Contract</span>
                  <IconDiagonalArrow size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* Real Product-UI Crop inside Window Frame */}
          <div id="live-preview" className="landing-crop-wrapper">
            <div className="crop-window-frame" aria-label="Live catalogue sample">
              <div className="crop-window-header">
                <div className="window-dots">
                  <span className="window-dot" />
                  <span className="window-dot" />
                  <span className="window-dot" />
                </div>
                <div className="crop-window-title">Catalogue Live Inventory — Bengaluru Warehouse Hub</div>
                <span className="crop-window-badge">Live API sample</span>
              </div>

              <div className="crop-table-container">
                <table className="data-table" style={{ fontSize: '13px' }}>
                  <thead>
                    <tr>
                      <th style={{ width: '110px' }}>SKU</th>
                      <th>Part Description</th>
                      <th>Vehicle Fitment</th>
                      <th className="text-right" style={{ width: '100px' }}>Unit Price</th>
                      <th className="text-right" style={{ width: '95px' }}>Stock</th>
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
                          <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500 }}>
                            {item.name}
                          </td>
                          <td className="text-muted" style={{ maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
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
              </div>
            </div>
          </div>
        </section>

        {/* Partner & Dealer Network Proof Strip */}
        <section className="landing-network-strip" aria-label="Authorized trade network">
          <div className="network-strip-label">
            <IconSunburst size={16} />
            <span>CONNECTING 25 AUTHORIZED DEALERS ACROSS BENGALURU & KARNATAKA</span>
          </div>
          <div className="network-strip-brands">
            <span className="network-brand-chip">HONDA OEM</span>
            <span className="network-brand-chip">YAMAHA GENUINE</span>
            <span className="network-brand-chip">BAJAJ AUTO</span>
            <span className="network-brand-chip">TVS RACING</span>
            <span className="network-brand-chip">ROYAL ENFIELD</span>
            <span className="network-brand-chip">KTM POWERPARTS</span>
          </div>
        </section>

        {/* Value Proposition / "What it does" Section */}
        <section id="what-it-does" className="landing-statement-section" aria-labelledby="statement-heading">
          <div className="statement-header-row">
            <div>
              <div className="section-eyebrow">
                <span className="eyebrow-square" />
                <span>What DealerDesk Does</span>
              </div>
              <h2 id="statement-heading" className="landing-statement-text">
                We build high-precision trade distribution systems to help motorcycle and car parts dealers{' '}
                <span className="statement-text-muted">eliminate inventory stockouts.</span>
              </h2>
            </div>
            <button
              type="button"
              className="statement-action-link"
              onClick={() => setShowContractModal(true)}
            >
              <span>EXPLORE API CONTRACT</span>
              <IconArrowRight size={14} />
            </button>
          </div>

          {/* 4 Feature Cards */}
          <div className="landing-cards-grid">
            <div className="feature-card">
              <div className="feature-card-num">01</div>
              <h3 className="feature-card-title">Catalogue and Stock</h3>
              <p className="feature-card-desc">
                600 products, live inventory, search by part, brand or vehicle. Real-time fitment validation and category filtering.
              </p>
              <div className="feature-card-badge">600 SKUs</div>
            </div>

            <div className="feature-card">
              <div className="feature-card-num">02</div>
              <h3 className="feature-card-title">Draft Orders</h3>
              <p className="feature-card-desc">
                GST at 18% per line item rounded to the paisa, order numbers formatted as ORD-YYYYMMDD-NNNN with credit limit checks.
              </p>
              <div className="feature-card-badge">Exact GST</div>
            </div>

            <div className="feature-card">
              <div className="feature-card-num">03</div>
              <h3 className="feature-card-title">Dealer Assistant</h3>
              <p className="feature-card-desc">
                Answers strictly from live data, creates draft orders, never confirms purchases. Grounded with BM25 retrieval.
              </p>
              <div className="feature-card-badge">Groq LLaMA 3.3</div>
            </div>

            <div className="feature-card">
              <div className="feature-card-num">04</div>
              <h3 className="feature-card-title">Demand Forecast & Reorder</h3>
              <p className="feature-card-desc">
                4-week rolling demand forecast for 40 SKUs with safety-stock reorder suggestions and sparkline trends.
              </p>
              <div className="feature-card-badge">LightGBM + SBA</div>
            </div>
          </div>
        </section>

        {/* Live Metrics: "BY THE NUMBERS" */}
        <section id="by-the-numbers" className="landing-numbers-section" aria-labelledby="numbers-heading">
          <div className="section-eyebrow">
            <span className="eyebrow-square" />
            <span id="numbers-heading">By The Numbers</span>
          </div>

          <div className="numbers-grid">
            <div className="number-card">
              <div className="number-stat tabular-nums">
                {productCount !== null ? productCount : '600'}
              </div>
              <div className="number-card-title">Products in catalogue</div>
              <div className="number-card-sub">
                Live inventory across 8 maintenance categories with vehicle fitment
              </div>
            </div>

            <div className="number-card">
              <div className="number-stat tabular-nums">
                {dealerCount !== null ? dealerCount : '25'}
              </div>
              <div className="number-card-title">Authorized dealers</div>
              <div className="number-card-sub">
                Registered trade accounts with GSTIN and credit verification
              </div>
            </div>

            <div className="number-card">
              <div className="number-stat tabular-nums">22.06%</div>
              <div className="number-card-title">Forecast WAPE (Phase 2)</div>
              <div className="number-card-sub">
                Beats best baseline by 6.51 pp (22.8% relative error reduction)
              </div>
            </div>

            <div className="number-card">
              <div className="number-stat tabular-nums">18.0%</div>
              <div className="number-card-title">Exact GST per line</div>
              <div className="number-card-sub">
                Deterministic round-half-up tax calculation with zero paisa drift
              </div>
            </div>
          </div>
        </section>

        {/* Architecture & "How it is built" Section */}
        <section id="architecture" className="landing-architecture-section" aria-labelledby="arch-heading">
          <div className="arch-header-row">
            <div>
              <div className="section-eyebrow">
                <span className="eyebrow-square" />
                <span>How It Is Built</span>
              </div>
              <h2 id="arch-heading" className="arch-headline">
                Engineered for Trade Precision
              </h2>
            </div>
            <p className="arch-subhead">
              Engineered strictly with <strong>Django 5.x & DRF</strong>, <strong>PostgreSQL</strong>,
              real-time <strong>Groq tool-calling</strong> with BM25 retrieval, and a direct
              multi-horizon <strong>LightGBM + SBA</strong> forecasting model isolated in <code>ml/</code>.
            </p>
          </div>

          <div className="arch-grid">
            <div className="arch-spec-card">
              <div className="arch-spec-title">Django & DRF Backend</div>
              <p className="arch-spec-desc">
                Clean REST contract, atomic database transactions for orders, deterministic 18% GST line item math, and structured error responses.
              </p>
            </div>

            <div className="arch-spec-card">
              <div className="arch-spec-title">PostgreSQL & Concurrency</div>
              <p className="arch-spec-desc">
                Strict relational data models with SELECT FOR UPDATE atomic inventory decrements to prevent overselling on concurrent checkout.
              </p>
            </div>

            <div className="arch-spec-card">
              <div className="arch-spec-title">Groq LLaMA 3.3 Assistant</div>
              <p className="arch-spec-desc">
                System-prompt-grounded conversational agent with 4 live tools: search catalogue, get stock, check reorder, create draft order.
              </p>
            </div>

            <div className="arch-spec-card">
              <div className="arch-spec-title">Statistical Forecasting</div>
              <p className="arch-spec-desc">
                Hybrid modeling: LightGBM direct multi-horizon for regular SKUs, Syntetos-Boylan Approximation for intermittent parts demand.
              </p>
            </div>
          </div>

          <div className="arch-links-row">
            <a
              href="https://github.com/padalingam4648-atman/DealerDesk"
              target="_blank"
              rel="noreferrer"
              className="arch-link"
            >
              <span>GitHub Repository</span>
              <IconExternalLink size={12} />
            </a>
            <span className="arch-links-divider">•</span>
            <button
              type="button"
              className="btn-link text-xs"
              onClick={() => setShowContractModal(true)}
            >
              API Specification
            </button>
            <span className="arch-links-divider">•</span>
            <button
              type="button"
              className="btn-link text-xs"
              onClick={handleOpenPortal}
            >
              Launch Portal App
            </button>
          </div>
        </section>

        {/* Restrained One-Line Footer */}
        <footer className="landing-footer" role="contentinfo">
          <div className="footer-left">
            <span>VIKMO DealerDesk • AI/ML track submission • Bengaluru Distributor Desk</span>
          </div>
          <div className="footer-right">
            <a
              href="https://github.com/padalingam4648-atman/DealerDesk#readme"
              target="_blank"
              rel="noreferrer"
            >
              Documentation
            </a>
            <span className="text-muted">•</span>
            <button
              type="button"
              className="btn-link text-xs"
              onClick={() => setShowContractModal(true)}
            >
              API Endpoints
            </button>
            <span className="text-muted">•</span>
            <span>{isOnline ? 'System Operational' : 'Standby'}</span>
          </div>
        </footer>
      </div>

      {/* API Contract Modal */}
      {showContractModal && (
        <div
          className="drawer-backdrop"
          onClick={() => setShowContractModal(false)}
          role="dialog"
          aria-modal="true"
          aria-label="DealerDesk REST API Specification"
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
                aria-label="Close modal"
              >
                <IconClose size={16} />
              </button>
            </div>
            <div className="drawer-body" style={{ fontSize: '13px' }}>
              <div>
                <h3 style={{ fontSize: '14px', marginBottom: '8px' }}>System Endpoints</h3>
                <ul style={{ paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
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
                <h3 style={{ fontSize: '14px', marginBottom: '6px' }}>Business Rules</h3>
                <p className="text-muted" style={{ lineHeight: '1.5' }}>
                  GST is calculated at 18% per line item rounded to the paisa (ROUND_HALF_UP).
                  Orders are created in DRAFT state with unique sequential order IDs (ORD-YYYYMMDD-NNNN).
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
