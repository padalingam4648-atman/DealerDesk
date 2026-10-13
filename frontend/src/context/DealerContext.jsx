import React, { createContext, useContext, useState, useEffect } from 'react';
import { fetchDealers } from '../api';

const DealerContext = createContext(null);

export function DealerProvider({ children }) {
  const [dealers, setDealers] = useState([]);
  const [selectedDealerId, setSelectedDealerId] = useState(() => {
    return sessionStorage.getItem('dealerdesk_dealer_id') || '1';
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let isMounted = true;
    async function loadDealers() {
      try {
        setLoading(true);
        // Dealers list has page_size up to 100 (total seeded dealers is 25)
        const response = await fetchDealers({ pageSize: 50 });
        if (isMounted) {
          const list = response.results || [];
          setDealers(list);
          if (list.length > 0 && !sessionStorage.getItem('dealerdesk_dealer_id')) {
            setSelectedDealerId(String(list[0].id));
            sessionStorage.setItem('dealerdesk_dealer_id', String(list[0].id));
          }
        }
      } catch (err) {
        if (isMounted) {
          setError(err.message || 'Failed to load dealers');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }
    loadDealers();
    return () => { isMounted = false; };
  }, []);

  const changeDealer = (id) => {
    const strId = String(id);
    setSelectedDealerId(strId);
    sessionStorage.setItem('dealerdesk_dealer_id', strId);
  };

  const selectedDealer = dealers.find(d => String(d.id) === String(selectedDealerId)) || dealers[0] || null;

  return (
    <DealerContext.Provider
      value={{
        dealers,
        selectedDealer,
        selectedDealerId,
        changeDealer,
        loading,
        error,
      }}
    >
      {children}
    </DealerContext.Provider>
  );
}

export function useDealer() {
  const context = useContext(DealerContext);
  if (!context) {
    throw new Error('useDealer must be used within a DealerProvider');
  }
  return context;
}
