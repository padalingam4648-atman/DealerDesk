import React, { createContext, useContext, useState, useEffect, useMemo } from 'react';

const CartContext = createContext(null);

/**
 * Exact GST & Paisa math adhering to Contract §7.4:
 * - line_subtotal = unit_price * quantity
 * - line_tax = line_subtotal * 0.18, rounded half up to 2 decimal places per line
 * - line_total = line_subtotal + line_tax
 * - subtotal = Σ line_subtotal
 * - tax_total = Σ line_tax
 * - grand_total = subtotal + tax_total
 */
export function roundHalfUp(val) {
  return Math.round((val + Number.EPSILON) * 100) / 100;
}

export function CartProvider({ children }) {
  const [items, setItems] = useState(() => {
    try {
      const saved = sessionStorage.getItem('dealerdesk_draft_cart');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  useEffect(() => {
    sessionStorage.setItem('dealerdesk_draft_cart', JSON.stringify(items));
  }, [items]);

  const addToCart = (product, quantity = 1) => {
    const qty = Math.max(1, parseInt(quantity, 10) || 1);
    setItems(prev => {
      const existingIndex = prev.findIndex(item => item.sku === product.sku);
      if (existingIndex >= 0) {
        const copy = [...prev];
        copy[existingIndex] = {
          ...copy[existingIndex],
          quantity: copy[existingIndex].quantity + qty,
        };
        return copy;
      }
      return [
        ...prev,
        {
          sku: product.sku,
          name: product.name,
          unit_price: product.price,
          brand: product.brand,
          stock: product.stock,
          quantity: qty,
        },
      ];
    });
  };

  const updateQuantity = (sku, quantity) => {
    const qty = parseInt(quantity, 10);
    if (qty <= 0) {
      removeFromCart(sku);
      return;
    }
    setItems(prev =>
      prev.map(item => (item.sku === sku ? { ...item, quantity: qty } : item))
    );
  };

  const removeFromCart = (sku) => {
    setItems(prev => prev.filter(item => item.sku !== sku));
  };

  const clearCart = () => {
    setItems([]);
  };

  // Computations
  const calculations = useMemo(() => {
    let subtotal = 0;
    let taxTotal = 0;

    const computedItems = items.map(item => {
      const unitPrice = parseFloat(item.unit_price) || 0;
      const qty = item.quantity;
      const lineSubtotal = roundHalfUp(unitPrice * qty);
      const lineTax = roundHalfUp(lineSubtotal * 0.18);
      const lineTotal = roundHalfUp(lineSubtotal + lineTax);

      subtotal += lineSubtotal;
      taxTotal += lineTax;

      return {
        ...item,
        lineSubtotal,
        lineTax,
        lineTotal,
      };
    });

    subtotal = roundHalfUp(subtotal);
    taxTotal = roundHalfUp(taxTotal);
    const grandTotal = roundHalfUp(subtotal + taxTotal);

    return {
      computedItems,
      subtotal,
      taxTotal,
      grandTotal,
      totalUnits: items.reduce((acc, it) => acc + it.quantity, 0),
      totalLines: items.length,
    };
  }, [items]);

  return (
    <CartContext.Provider
      value={{
        items: calculations.computedItems,
        rawItems: items,
        addToCart,
        updateQuantity,
        removeFromCart,
        clearCart,
        subtotal: calculations.subtotal,
        taxTotal: calculations.taxTotal,
        grandTotal: calculations.grandTotal,
        totalUnits: calculations.totalUnits,
        totalLines: calculations.totalLines,
      }}
    >
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error('useCart must be used within a CartProvider');
  }
  return context;
}
