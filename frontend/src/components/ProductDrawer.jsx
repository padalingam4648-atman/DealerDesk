import React, { useState, useEffect } from 'react';
import { fetchProduct, fetchForecast } from '../api';
import Money from './Money';
import StatusBadge from './StatusBadge';
import Sparkline from './Sparkline';
import { IconClose } from './Icons';
import { useCart } from '../context/CartContext';

export default function ProductDrawer({ sku, onClose }) {
  const { addToCart } = useCart();
  const [product, setProduct] = useState(null);
  const [forecast, setForecast] = useState(null);
  const [loading, setLoading] = useState(true);
  const [quantity, setQuantity] = useState(1);
  const [addedNotice, setAddedNotice] = useState(false);
  const [lastUpdated, setLastUpdated] = useState('');

  useEffect(() => {
    if (!sku) return;

    let isMounted = true;
    setLoading(true);
    setProduct(null);
    setForecast(null);
    setQuantity(1);
    setAddedNotice(false);

    // Formatted "last updated" time
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' });
    setLastUpdated(`Today, ${timeStr}`);

    async function loadDetails() {
      try {
        const prodData = await fetchProduct(sku);
        if (!isMounted) return;
        setProduct(prodData);

        // Try fetching forecast (will succeed for the 40 forecast SKUs, 404 for others)
        try {
          const fcData = await fetchForecast(sku);
          if (isMounted) setForecast(fcData);
        } catch {
          // Non-forecast SKU, ignore 404
        }
      } catch (err) {
        console.error('Failed to load product details', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadDetails();

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      isMounted = false;
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [sku, onClose]);

  if (!sku) return null;

  const handleAdd = () => {
    if (!product) return;
    addToCart(product, quantity);
    setAddedNotice(true);
    setTimeout(() => setAddedNotice(false), 2000);
  };

  return (
    <div className="drawer-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Product Details">
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <div>
            <span className="text-mono" style={{ color: 'var(--accent)', fontWeight: 600 }}>
              {sku}
            </span>
            <h2 style={{ fontSize: '16px', marginTop: '2px' }}>
              {loading ? 'Loading...' : product?.name}
            </h2>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={onClose} aria-label="Close drawer">
            <IconClose size={16} />
          </button>
        </div>

        <div className="drawer-body">
          {loading ? (
            <div style={{ color: 'var(--text-muted)', padding: '20px 0' }}>Fetching live inventory...</div>
          ) : product ? (
            <>
              {/* Core Ledger Specs */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', background: 'var(--bg-surface-subtle)', padding: '12px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>
                <div>
                  <div className="text-xs text-muted">Brand</div>
                  <div style={{ fontWeight: 500 }}>{product.brand}</div>
                </div>
                <div>
                  <div className="text-xs text-muted">Category</div>
                  <div style={{ fontWeight: 500 }}>{product.category}</div>
                </div>
                <div>
                  <div className="text-xs text-muted">Unit Price</div>
                  <div style={{ fontWeight: 600 }}>
                    <Money amount={product.price} />
                  </div>
                </div>
                <div>
                  <div className="text-xs text-muted">Vehicle Fitment</div>
                  <div style={{ fontWeight: 500 }}>{product.vehicle_fitment}</div>
                </div>
              </div>

              {/* Live Inventory Status */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px' }}>
                <div>
                  <div className="text-xs text-muted">Warehouse Inventory</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                    <StatusBadge type="stock" stock={product.stock} />
                    <span className="text-xs text-muted">Updated: {lastUpdated}</span>
                  </div>
                </div>
              </div>

              {/* Product Description */}
              <div>
                <div className="text-xs text-muted" style={{ marginBottom: '4px' }}>Specification & Details</div>
                <p style={{ fontSize: '13px', lineHeight: '1.5', color: 'var(--text-primary)' }}>
                  {product.description || 'Standard OEM replacement part.'}
                </p>
              </div>

              {/* 4-Week Demand Forecast (if available) */}
              {forecast && forecast.forecast && (
                <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)', borderRadius: '4px', padding: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
                      4-Week ML Demand Forecast
                    </span>
                    <Sparkline data={forecast.forecast} width={80} height={20} />
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px', textAlign: 'center' }}>
                    {forecast.forecast.map((fw, idx) => (
                      <div key={idx} style={{ background: 'var(--bg-surface-subtle)', padding: '4px', borderRadius: '2px' }}>
                        <div className="text-xs text-muted">{fw.week_start.slice(5)}</div>
                        <div className="tabular-nums" style={{ fontSize: '13px', fontWeight: 600 }}>
                          {fw.forecast_units}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div style={{ color: 'var(--status-out-stock)' }}>Product details could not be found.</div>
          )}
        </div>

        {product && (
          <div className="drawer-footer">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{ width: '90px' }}>
                <input
                  type="number"
                  min="1"
                  max={Math.max(1, product.stock || 999)}
                  value={quantity}
                  onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value, 10) || 1))}
                  className="input-text"
                  style={{ width: '100%' }}
                  aria-label="Order Quantity"
                />
              </div>
              <button
                className="btn btn-primary"
                style={{ flex: 1 }}
                onClick={handleAdd}
              >
                {addedNotice ? 'Added to draft' : 'Add to draft'}
              </button>
            </div>
            {product.stock === 0 && (
              <div className="text-xs text-muted" style={{ marginTop: '6px', textAlign: 'center' }}>
                Notice: Item is currently out of warehouse stock. Adding to draft will create a backorder line.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
