import React from 'react';

/**
 * StatusBadge renders meaningful semantic status indicators according to the design tokens:
 * - Green = In stock
 * - Amber = Low stock / Reorder needed
 * - Red = Out of stock
 * - Blue-grey = DRAFT badge
 */
export default function StatusBadge({ type = 'stock', status, stock, qty }) {
  if (type === 'stock') {
    const count = typeof stock === 'number' ? stock : parseInt(stock, 10) || 0;
    if (count > 10) {
      return <span className="badge badge-in-stock">In stock ({count})</span>;
    }
    if (count > 0) {
      return <span className="badge badge-low-stock">Low: {count} left</span>;
    }
    return <span className="badge badge-out-stock">Out of stock</span>;
  }

  if (type === 'reorder') {
    const needed = typeof qty === 'number' ? qty : parseInt(qty, 10) || 0;
    if (needed > 0) {
      return <span className="badge badge-low-stock">Order {needed} units</span>;
    }
    return <span className="badge badge-in-stock">Adequate</span>;
  }

  // Order status badge
  const s = (status || '').toUpperCase();
  switch (s) {
    case 'DRAFT':
      return <span className="badge badge-draft">DRAFT</span>;
    case 'CONFIRMED':
      return <span className="badge badge-confirmed">CONFIRMED</span>;
    case 'DISPATCHED':
      return <span className="badge badge-dispatched">DISPATCHED</span>;
    case 'DELIVERED':
      return <span className="badge badge-delivered">DELIVERED</span>;
    case 'CANCELLED':
      return <span className="badge badge-cancelled">CANCELLED</span>;
    default:
      return <span className="badge badge-draft">{status}</span>;
  }
}
