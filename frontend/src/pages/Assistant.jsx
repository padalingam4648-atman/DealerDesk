import React from 'react';
import AssistantDrawer from '../components/AssistantDrawer';

export default function Assistant({ onOpenProduct }) {
  return (
    <div className="assistant-page-container" style={{ height: 'calc(100vh - 110px)', display: 'flex', flexDirection: 'column' }}>
      <div className="page-header" style={{ marginBottom: '12px' }}>
        <div className="page-header-title-group">
          <h1>Dealer Desk AI Assistant</h1>
          <p className="page-header-desc">
            Natural language parts search, stock checks, and draft purchase order generation.
          </p>
        </div>
      </div>

      <div style={{ flex: 1, border: '1px solid var(--border-color)', borderRadius: '6px', overflow: 'hidden' }}>
        <AssistantDrawer isPage={true} onSelectSku={onOpenProduct} />
      </div>
    </div>
  );
}
