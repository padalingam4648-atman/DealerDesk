import React, { useState } from 'react';
import { IconCheck, IconCopy } from './Icons';

/**
 * StatusTracker Component
 * 
 * Renders the 4 lifecycle order stages:
 * Draft -> Confirmed -> Dispatched -> Delivered
 * (or a prominent Cancelled indicator if CANCELLED).
 * 
 * Completed steps: Teal checkmark icon
 * Current step: Filled teal background with active indicator
 * Future steps: Subtle grey outline
 * 
 * Includes the mandatory disclaimer:
 * "Draft orders are not reserved. Confirmation happens in the dealer portal."
 */
export default function StatusTracker({ status = 'DRAFT', compact = false }) {
  const steps = [
    { key: 'DRAFT', label: 'Draft' },
    { key: 'CONFIRMED', label: 'Confirmed' },
    { key: 'DISPATCHED', label: 'Dispatched' },
    { key: 'DELIVERED', label: 'Delivered' },
  ];

  const currentStatus = (status || 'DRAFT').toUpperCase();
  const isCancelled = currentStatus === 'CANCELLED';

  const currentIdx = steps.findIndex((s) => s.key === currentStatus);
  const activeIdx = currentIdx >= 0 ? currentIdx : 0;

  if (compact) {
    if (isCancelled) {
      return (
        <span className="badge badge-out-stock" title="Order was cancelled">
          CANCELLED
        </span>
      );
    }
    return (
      <div className="status-tracker-compact" title={`Status: ${steps[activeIdx]?.label}`}>
        <div className="tracker-mini-steps">
          {steps.map((step, idx) => {
            const isCompleted = idx < activeIdx;
            const isCurrent = idx === activeIdx;
            return (
              <span
                key={step.key}
                className={`tracker-mini-dot ${
                  isCompleted ? 'completed' : isCurrent ? 'current' : 'future'
                }`}
              />
            );
          })}
        </div>
        <span className="tracker-compact-label">{steps[activeIdx]?.label}</span>
      </div>
    );
  }

  if (isCancelled) {
    return (
      <div className="status-tracker-container" role="region" aria-label="Order Status Progress">
        <div className="tracker-cancelled-box">
          <span className="badge badge-out-stock" style={{ fontSize: '12px', padding: '4px 10px' }}>
            CANCELLED
          </span>
          <span className="text-xs text-muted">
            This purchase order was cancelled and will not be processed.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="status-tracker-container" role="region" aria-label="Order Status Progress">
      <div className="tracker-steps-row">
        {steps.map((step, idx) => {
          const isCompleted = idx < activeIdx;
          const isCurrent = idx === activeIdx;
          const isFuture = idx > activeIdx;

          return (
            <React.Fragment key={step.key}>
              {idx > 0 && (
                <div
                  className={`tracker-connector ${
                    idx <= activeIdx ? 'active-line' : 'future-line'
                  }`}
                  aria-hidden="true"
                />
              )}
              <div
                className={`tracker-step-node ${
                  isCompleted ? 'step-completed' : isCurrent ? 'step-current' : 'step-future'
                }`}
                aria-current={isCurrent ? 'step' : undefined}
              >
                <div className="tracker-node-circle">
                  {isCompleted ? (
                    <IconCheck size={12} className="tracker-check-icon" />
                  ) : (
                    <span className="tracker-node-index">{idx + 1}</span>
                  )}
                </div>
                <div className="tracker-node-label">{step.label}</div>
              </div>
            </React.Fragment>
          );
        })}
      </div>

      <p className="tracker-caption">
        Draft orders are not reserved. Confirmation happens in the dealer portal.
      </p>
    </div>
  );
}

/**
 * OrderNumberDisplay
 * Monospace prominent display with a 1.5s visual "Copied!" feedback button
 */
export function OrderNumberDisplay({ orderNumber, className = '' }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e) => {
    e.stopPropagation();
    if (!orderNumber) return;
    navigator.clipboard.writeText(orderNumber);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className={`order-number-wrap ${className}`}>
      <span className="order-number-text text-mono">{orderNumber}</span>
      <button
        type="button"
        className="btn btn-secondary btn-sm order-copy-btn"
        onClick={handleCopy}
        title="Copy order reference to clipboard"
        aria-label="Copy order number"
      >
        {copied ? (
          <>
            <IconCheck size={12} style={{ color: 'var(--status-in-stock)' }} />
            <span style={{ color: 'var(--status-in-stock)' }}>Copied</span>
          </>
        ) : (
          <>
            <IconCopy size={12} />
            <span>Copy</span>
          </>
        )}
      </button>
    </div>
  );
}
