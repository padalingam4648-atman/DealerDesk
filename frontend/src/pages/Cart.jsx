import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCart } from '../context/CartContext';
import { useDealer } from '../context/DealerContext';
import { createOrder } from '../api';
import Money from '../components/Money';
import { IconCart } from '../components/Icons';
import StatusTracker, { OrderNumberDisplay } from '../components/StatusTracker';

export default function Cart({ onOpenProduct }) {
  const navigate = useNavigate();
  const {
    items,
    updateQuantity,
    removeFromCart,
    clearCart,
    subtotal,
    taxTotal,
    grandTotal,
    totalUnits,
    totalLines,
  } = useCart();
  const { selectedDealer, selectedDealerId } = useDealer();

  const [submitting, setSubmitting] = useState(false);
  const [createdOrder, setCreatedOrder] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const handleCreateDraft = async () => {
    if (items.length === 0 || submitting) return;

    setSubmitting(true);
    setErrorMessage(null);

    try {
      const orderPayload = items.map((it) => ({
        sku: it.sku,
        quantity: it.quantity,
      }));

      const res = await createOrder(selectedDealerId, orderPayload);
      clearCart();
      setCreatedOrder(res);
    } catch (err) {
      setErrorMessage(
        err.message || 'Failed to submit draft order. Please verify line items.'
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="cart-page">
      <div className="page-header">
        <div className="page-header-title-group">
          <h1>Draft Order Cart</h1>
          <p className="page-header-desc">
            Build and calculate purchase orders with itemized 18% GST tax breakdown.
          </p>
        </div>
      </div>

      {createdOrder && (
        <div
          style={{
            background: 'var(--bg-surface)',
            border: '1px solid var(--border-color)',
            borderRadius: '6px',
            padding: '20px',
            marginBottom: '24px',
            boxShadow: 'var(--shadow-subtle)',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '16px',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div>
              <div
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  color: 'var(--status-in-stock)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  marginBottom: '4px',
                }}
              >
                Draft Order Created Successfully
              </div>
              <OrderNumberDisplay orderNumber={createdOrder.order_number} />
              <div className="text-xs text-muted" style={{ marginTop: '4px' }}>
                Dealer: {selectedDealer ? `${selectedDealer.dealer_code} — ${selectedDealer.name}` : `Dealer #${selectedDealerId}`}
              </div>
            </div>

            <button
              type="button"
              className="btn btn-primary btn-sm btn-pill"
              onClick={() => navigate('/orders')}
            >
              View in Orders List →
            </button>
          </div>

          <StatusTracker status={createdOrder.status} />
        </div>
      )}

      {errorMessage && (
        <div
          style={{
            background: 'var(--status-out-stock-bg)',
            border: '1px solid var(--status-out-stock-border)',
            color: 'var(--status-out-stock)',
            borderRadius: '4px',
            padding: '12px',
            marginBottom: '20px',
            fontSize: '13px',
          }}
        >
          <strong>Error:</strong> {errorMessage}
        </div>
      )}

      {items.length === 0 && !createdOrder ? (
        <div className="empty-state">
          <IconCart size={32} className="text-muted" />
          <div className="empty-state-title">Your draft order is empty</div>
          <p className="empty-state-desc">
            Add parts from the catalogue, review safety stock reorders, or ask the
            assistant to compile items.
          </p>
          <button
            type="button"
            className="btn btn-primary btn-sm"
            onClick={() => navigate('/catalogue')}
            style={{ marginTop: '8px' }}
          >
            Browse Catalogue
          </button>
        </div>
      ) : items.length > 0 ? (
        <div className="cart-layout">
          {/* Items Table */}
          <div className="table-container">
            <table className="data-table" role="table">
              <thead>
                <tr>
                  <th style={{ width: '95px' }}>SKU</th>
                  <th>Part Description</th>
                  <th className="text-right" style={{ width: '95px' }}>Unit Price</th>
                  <th className="text-center" style={{ width: '110px' }}>Quantity</th>
                  <th className="text-right" style={{ width: '95px' }}>Subtotal</th>
                  <th className="text-right" style={{ width: '85px' }}>GST (18%)</th>
                  <th className="text-right" style={{ width: '100px' }}>Total</th>
                  <th style={{ width: '50px' }}></th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.sku}>
                    <td>
                      <button
                        type="button"
                        className="sku-chip"
                        onClick={() => onOpenProduct(item.sku)}
                        title="View details"
                      >
                        {item.sku}
                      </button>
                    </td>
                    <td style={{ fontWeight: 500 }}>{item.name}</td>
                    <td className="text-right">
                      <Money amount={item.unit_price} />
                    </td>
                    <td className="text-center">
                      <div className="qty-control">
                        <button
                          type="button"
                          className="qty-btn"
                          onClick={() => updateQuantity(item.sku, item.quantity - 1)}
                          aria-label="Decrease quantity"
                        >
                          -
                        </button>
                        <span className="qty-val">{item.quantity}</span>
                        <button
                          type="button"
                          className="qty-btn"
                          onClick={() => updateQuantity(item.sku, item.quantity + 1)}
                          aria-label="Increase quantity"
                        >
                          +
                        </button>
                      </div>
                    </td>
                    <td className="text-right">
                      <Money amount={item.lineSubtotal} />
                    </td>
                    <td className="text-right text-muted">
                      <Money amount={item.lineTax} />
                    </td>
                    <td className="text-right" style={{ fontWeight: 600 }}>
                      <Money amount={item.lineTotal} />
                    </td>
                    <td className="text-center">
                      <button
                        type="button"
                        className="btn-link text-xs text-muted"
                        onClick={() => removeFromCart(item.sku)}
                        title="Remove item"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Ledger Calculation Sidebar */}
          <aside className="ledger-card" aria-label="Order Ledger Summary">
            <div className="ledger-title">Order Ledger Summary</div>

            <div style={{ background: 'var(--bg-surface-subtle)', padding: '10px', borderRadius: '4px', border: '1px solid var(--border-color)', fontSize: '12px' }}>
              <div className="text-muted">Target Dealership:</div>
              <div style={{ fontWeight: 600, marginTop: '2px' }}>
                {selectedDealer ? `${selectedDealer.dealer_code} — ${selectedDealer.name}` : `Dealer ID ${selectedDealerId}`}
              </div>
              <div className="text-muted" style={{ marginTop: '2px' }}>
                {selectedDealer?.city} • GSTIN: {selectedDealer?.gstin || 'None'}
              </div>
            </div>

            <div className="ledger-row">
              <span className="text-muted">Line Items:</span>
              <span className="tabular-nums font-semibold">{totalLines} lines ({totalUnits} units)</span>
            </div>

            <div className="ledger-row">
              <span className="text-muted">Net Subtotal:</span>
              <Money amount={subtotal} />
            </div>

            <div className="ledger-row">
              <span className="text-muted">GST Total (18% rounded):</span>
              <Money amount={taxTotal} />
            </div>

            <div className="ledger-row total-row">
              <span>Grand Total:</span>
              <Money amount={grandTotal} />
            </div>

            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleCreateDraft}
                disabled={submitting}
                style={{ width: '100%' }}
              >
                {submitting ? 'Submitting draft...' : 'Create Draft Order'}
              </button>

              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={clearCart}
                disabled={submitting}
                style={{ width: '100%' }}
              >
                Clear Cart
              </button>
            </div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
