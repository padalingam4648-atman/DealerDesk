import React, { useState } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { DealerProvider } from './context/DealerContext';
import { CartProvider } from './context/CartContext';
import Landing from './pages/Landing';
import Catalogue from './pages/Catalogue';
import Cart from './pages/Cart';
import Orders from './pages/Orders';
import Reorder from './pages/Reorder';
import Assistant from './pages/Assistant';
import TopBar from './components/TopBar';
import AssistantDrawer from './components/AssistantDrawer';
import ProductDrawer from './components/ProductDrawer';

/**
 * PortalLayout: Unified shell with top navigation
 * Features:
 * - Fixed top navigation bar with wordmark, nav links, dealer selector, and cart badge
 * - Full-width central content area (max-width ~1200px, centered)
 * - Docked right assistant drawer (collapsible)
 * - Global product detail drawer for any SKU clicked
 */
function PortalLayout() {
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [drawerSku, setDrawerSku] = useState(null);
  const location = useLocation();

  // If on dedicated assistant page, collapse docked assistant to avoid duplicate view
  const isAssistantPage = location.pathname.includes('/assistant');

  return (
    <div className="portal-layout">
      {/* Top Fixed Navigation Bar */}
      <TopBar
        onToggleAssistant={() => setAssistantOpen(!assistantOpen)}
        assistantOpen={assistantOpen}
      />

      {/* Main Content Area */}
      <div className="portal-body-container">
        <div className="portal-main-area">
          {/* Main ERP Page Content */}
          <main className="portal-content" role="main">
            <Routes>
              <Route
                path="catalogue"
                element={
                  <Catalogue
                    onOpenProduct={(sku) => setDrawerSku(sku)}
                    selectedSku={drawerSku}
                    onCloseProduct={() => setDrawerSku(null)}
                  />
                }
              />
              <Route
                path="cart"
                element={<Cart onOpenProduct={(sku) => setDrawerSku(sku)} />}
              />
              <Route
                path="orders"
                element={<Orders onOpenProduct={(sku) => setDrawerSku(sku)} />}
              />
              <Route
                path="reorder"
                element={<Reorder onOpenProduct={(sku) => setDrawerSku(sku)} />}
              />
              <Route
                path="assistant"
                element={<Assistant onOpenProduct={(sku) => setDrawerSku(sku)} />}
              />
              <Route path="*" element={<Navigate to="/catalogue" replace />} />
            </Routes>
          </main>
        </div>

        {/* Docked Collapsible Right Assistant Panel */}
        {assistantOpen && !isAssistantPage && (
          <aside className="assistant-dock" aria-label="Docked Assistant Panel">
            <AssistantDrawer
              onClose={() => setAssistantOpen(false)}
              onSelectSku={(sku) => setDrawerSku(sku)}
            />
          </aside>
        )}
      </div>

      {/* Global Product Detail Drawer */}
      {drawerSku && (
        <ProductDrawer sku={drawerSku} onClose={() => setDrawerSku(null)} />
      )}
    </div>
  );
}

export default function App() {
  return (
    <DealerProvider>
      <CartProvider>
        <Routes>
          {/* Landing page at route "#/" */}
          <Route path="/" element={<Landing />} />

          {/* Portal ERP routes */}
          <Route path="/*" element={<PortalLayout />} />
        </Routes>
      </CartProvider>
    </DealerProvider>
  );
}
