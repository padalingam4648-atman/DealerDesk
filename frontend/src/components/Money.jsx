import React from 'react';

/**
 * Formats numerical and string amounts as Indian Rupee currency: "Rs. 1,459.50"
 * using Intl.NumberFormat with the "en-IN" locale and exact 2 decimal places.
 */
export function formatMoney(amount) {
  const num = typeof amount === 'number' ? amount : parseFloat(amount) || 0;
  const formatted = new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(num);
  return `Rs. ${formatted}`;
}

/**
 * Money component displaying tabular-num currency representation
 */
export default function Money({ amount, className = '' }) {
  return (
    <span className={`tabular-nums ${className}`}>
      {formatMoney(amount)}
    </span>
  );
}
