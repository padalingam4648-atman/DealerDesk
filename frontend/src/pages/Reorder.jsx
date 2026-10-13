import React, { useState, useEffect, useMemo } from 'react';
import { fetchReorderSuggestions, fetchForecast, fetchProduct } from '../api';
import DataTable from '../components/DataTable';
import StatusBadge from '../components/StatusBadge';
import Sparkline from '../components/Sparkline';
import { useCart } from '../context/CartContext';
import { IconSearch } from '../components/Icons';

export default function Reorder({ onOpenProduct }) {
  const { addToCart } = useCart();
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filterNeedsReorder, setFilterNeedsReorder] = useState(false);
  const [searchSku, setSearchSku] = useState('');

  // Expandable row forecast caching
  const [expandedSku, setExpandedSku] = useState(null);
  const [forecastCache, setForecastCache] = useState({});
  const [loadingForecast, setLoadingForecast] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    fetchReorderSuggestions()
      .then((data) => {
        if (isMounted) setSuggestions(data.results || []);
      })
      .catch((err) => console.error('Failed to load reorder suggestions', err))
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch forecast when row is expanded
  const handleToggleExpand = async (sku) => {
    if (expandedSku === sku) {
      setExpandedSku(null);
      return;
    }

    setExpandedSku(sku);
    if (!forecastCache[sku]) {
      setLoadingForecast(true);
      try {
        const fc = await fetchForecast(sku);
        setForecastCache((prev) => ({ ...prev, [sku]: fc.forecast || [] }));
      } catch (err) {
        console.error('Failed to fetch forecast for SKU', sku, err);
      } finally {
        setLoadingForecast(false);
      }
    }
  };

  const handleQuickAdd = async (row) => {
    try {
      const prod = await fetchProduct(row.sku);
      addToCart(prod, row.reorder_qty > 0 ? row.reorder_qty : 1);
    } catch {
      addToCart({
        sku: row.sku,
        name: `Part ${row.sku}`,
        price: '0.00',
        stock: row.current_stock,
      }, row.reorder_qty > 0 ? row.reorder_qty : 1);
    }
  };

  // Filtered rows
  const filteredData = useMemo(() => {
    return suggestions.filter((item) => {
      if (filterNeedsReorder && item.reorder_qty <= 0) return false;
      if (searchSku && !item.sku.toLowerCase().includes(searchSku.toLowerCase())) return false;
      return true;
    });
  }, [suggestions, filterNeedsReorder, searchSku]);

  const columns = useMemo(() => [
    {
      header: 'SKU',
      accessor: 'sku',
      width: '100px',
      render: (row) => (
        <button
          type="button"
          className="sku-chip"
          onClick={(e) => {
            e.stopPropagation();
            onOpenProduct(row.sku);
          }}
          title="View product details"
        >
          {row.sku}
        </button>
      ),
    },
    {
      header: 'Lead Time',
      accessor: 'lead_time_weeks',
      width: '95px',
      render: (row) => <span className="text-muted">{row.lead_time_weeks} wks</span>,
    },
    {
      header: 'Live Stock',
      accessor: 'current_stock',
      align: 'right',
      width: '90px',
      render: (row) => (
        <span className="tabular-nums" style={{ fontWeight: 600 }}>
          {row.current_stock}
        </span>
      ),
    },
    {
      header: 'Stock vs Reorder Point',
      width: '180px',
      render: (row) => {
        const ratio = row.reorder_point > 0 ? Math.min(100, Math.round((row.current_stock / row.reorder_point) * 100)) : 100;
        const color = ratio >= 100 ? 'var(--status-in-stock)' : ratio >= 50 ? 'var(--status-low-stock)' : 'var(--status-out-stock)';
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div className="reorder-bar-container">
              <div className="reorder-bar-fill" style={{ width: `${ratio}%`, backgroundColor: color }} />
            </div>
            <span className="tabular-nums text-xs text-muted" style={{ width: '40px' }}>
              {ratio}%
            </span>
          </div>
        );
      },
    },
    {
      header: 'LT Demand',
      accessor: 'lead_time_demand',
      align: 'right',
      width: '95px',
      render: (row) => <span className="tabular-nums">{row.lead_time_demand}</span>,
    },
    {
      header: 'Safety Stock',
      accessor: 'safety_stock',
      align: 'right',
      width: '95px',
      render: (row) => <span className="tabular-nums">{row.safety_stock}</span>,
    },
    {
      header: 'Reorder Point',
      accessor: 'reorder_point',
      align: 'right',
      width: '105px',
      render: (row) => <span className="tabular-nums font-semibold">{row.reorder_point}</span>,
    },
    {
      header: 'Recommendation',
      accessor: 'reorder_qty',
      align: 'center',
      width: '135px',
      render: (row) => <StatusBadge type="reorder" qty={row.reorder_qty} />,
    },
    {
      header: 'Action',
      align: 'right',
      width: '120px',
      render: (row) => (
        <button
          type="button"
          className={row.reorder_qty > 0 ? 'btn btn-primary btn-sm' : 'btn btn-secondary btn-sm'}
          onClick={(e) => {
            e.stopPropagation();
            handleQuickAdd(row);
          }}
        >
          {row.reorder_qty > 0 ? `Add ${row.reorder_qty}` : 'Add 1 unit'}
        </button>
      ),
    },
  ], [onOpenProduct]);

  return (
    <div className="reorder-page">
      <div className="page-header">
        <div className="page-header-title-group">
          <h1>Demand Forecast & Reorder Engine</h1>
          <p className="page-header-desc">
            Safety stock calculations across 40 critical spare parts based on Phase 2 LightGBM model.
          </p>
        </div>
      </div>

      {/* Filter toolbar */}
      <div className="filter-toolbar">
        <div className="filter-group">
          <div className="search-input-wrap">
            <span className="search-icon-inline">
              <IconSearch size={14} />
            </span>
            <input
              type="text"
              placeholder="Filter by SKU code..."
              value={searchSku}
              onChange={(e) => setSearchSku(e.target.value)}
              className="input-text"
              style={{ width: '200px' }}
            />
          </div>

          <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer', marginLeft: '8px' }}>
            <input
              type="checkbox"
              checked={filterNeedsReorder}
              onChange={(e) => setFilterNeedsReorder(e.target.checked)}
            />
            <span>Short stock only (Reorder &gt; 0)</span>
          </label>
        </div>

        <div className="result-count-text">
          {loading ? 'Evaluating warehouse inventory...' : `${filteredData.length} of 40 forecast SKUs`}
        </div>
      </div>

      {/* Main Reorder Table */}
      <div className="table-container">
        <table className="data-table" role="table">
          <thead>
            <tr>
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  className={col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : ''}
                  style={{ width: col.width }}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 6 }).map((_, rIdx) => (
                <tr key={rIdx} className="skeleton-row">
                  {columns.map((_, cIdx) => (
                    <td key={cIdx}><div style={{ width: '80%' }} /></td>
                  ))}
                </tr>
              ))
            ) : filteredData.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{ height: '100px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No SKUs require reordering under current criteria.
                </td>
              </tr>
            ) : (
              filteredData.map((row) => {
                const isExpanded = expandedSku === row.sku;
                return (
                  <React.Fragment key={row.sku}>
                    <tr
                      onClick={() => handleToggleExpand(row.sku)}
                      className={isExpanded ? 'selected' : ''}
                      style={{ cursor: 'pointer' }}
                      title="Click to toggle 4-week demand sparkline"
                    >
                      {columns.map((col, cIdx) => {
                        const val = col.accessor ? (typeof col.accessor === 'function' ? col.accessor(row) : row[col.accessor]) : null;
                        return (
                          <td
                            key={cIdx}
                            className={col.align === 'right' ? 'text-right tabular-nums' : col.align === 'center' ? 'text-center' : ''}
                          >
                            {col.render ? col.render(row, val) : val}
                          </td>
                        );
                      })}
                    </tr>

                    {/* Row Detail: 4-Week Demand Sparkline and Formula Trace */}
                    {isExpanded && (
                      <tr style={{ backgroundColor: 'var(--bg-surface-subtle)' }}>
                        <td colSpan={columns.length} style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-color)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
                            <div>
                              <div className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase' }}>
                                4-Week ML Demand Trend ({row.sku})
                              </div>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '6px' }}>
                                <Sparkline
                                  data={forecastCache[row.sku] || []}
                                  width={120}
                                  height={28}
                                />
                                {loadingForecast ? (
                                  <span className="text-xs text-muted">Loading projection...</span>
                                ) : (
                                  <div style={{ display: 'flex', gap: '8px' }}>
                                    {(forecastCache[row.sku] || []).map((fw, i) => (
                                      <div key={i} className="text-xs">
                                        <span className="text-muted">{fw.week_start.slice(5)}:</span>{' '}
                                        <span className="tabular-nums font-semibold">{fw.forecast_units}</span>
                                      </div>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>

                            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                              <div><strong>Formula:</strong> safety_stock = ⌈1.65 × σ × √{row.lead_time_weeks}⌉ = {row.safety_stock}</div>
                              <div>reorder_point = {row.lead_time_demand} + {row.safety_stock} = {row.reorder_point} units</div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
