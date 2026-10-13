import React, { useState, useEffect, useMemo } from 'react';
import { fetchOrders, fetchOrder } from '../api';
import { useDealer } from '../context/DealerContext';
import DataTable from '../components/DataTable';
import Money from '../components/Money';
import StatusBadge from '../components/StatusBadge';
import { IconPrinter, IconClose } from '../components/Icons';
import StatusTracker, { OrderNumberDisplay } from '../components/StatusTracker';

export default function Orders({ onOpenProduct }) {
  const { dealers, selectedDealerId } = useDealer();
  const [orders, setOrders] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);

  // Filters: default to current dealer or allow All
  const [filterDealerId, setFilterDealerId] = useState(selectedDealerId || '');
  const [statusFilter, setStatusFilter] = useState('');

  // Selected Order Detail View
  const [selectedOrderNo, setSelectedOrderNo] = useState(null);
  const [orderDetail, setOrderDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    async function loadOrders() {
      try {
        const res = await fetchOrders({
          page,
          pageSize,
          dealer_id: filterDealerId || undefined,
          status: statusFilter || undefined,
        });

        if (isMounted) {
          setOrders(res.results || []);
          setCount(res.count || 0);
        }
      } catch (err) {
        console.error('Failed to load orders', err);
        if (isMounted) {
          setOrders([]);
          setCount(0);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadOrders();
    return () => {
      isMounted = false;
    };
  }, [page, pageSize, filterDealerId, statusFilter]);

  // Load single order detail when an order is opened
  useEffect(() => {
    if (!selectedOrderNo) {
      setOrderDetail(null);
      return;
    }

    let isMounted = true;
    setLoadingDetail(true);

    fetchOrder(selectedOrderNo)
      .then((data) => {
        if (isMounted) setOrderDetail(data);
      })
      .catch((err) => console.error(err))
      .finally(() => {
        if (isMounted) setLoadingDetail(false);
      });

    return () => {
      isMounted = false;
    };
  }, [selectedOrderNo]);

  const formatDate = (isoStr) => {
    if (!isoStr) return '—';
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return isoStr;
    }
  };

  const columns = useMemo(() => [
    {
      header: 'Order Reference',
      accessor: 'order_number',
      width: '180px',
      render: (row) => (
        <span className="text-mono" style={{ fontWeight: 600, color: 'var(--accent)' }}>
          {row.order_number}
        </span>
      ),
    },
    {
      header: 'Dealer Code',
      accessor: 'dealer_id',
      width: '120px',
      render: (row) => {
        const d = dealers.find((item) => item.id === row.dealer_id);
        return <span>{d ? d.dealer_code : `Dealer #${row.dealer_id}`}</span>;
      },
    },
    {
      header: 'Placed On',
      accessor: 'created_at',
      width: '160px',
      render: (row) => <span className="text-muted">{formatDate(row.created_at)}</span>,
    },
    {
      header: 'Lines',
      accessor: (row) => row.items?.length || 0,
      align: 'center',
      width: '70px',
      render: (row) => <span className="tabular-nums">{row.items?.length || 0}</span>,
    },
    {
      header: 'Tax (18%)',
      accessor: 'tax_total',
      align: 'right',
      width: '110px',
      render: (row) => <Money amount={row.tax_total} />,
    },
    {
      header: 'Grand Total',
      accessor: 'grand_total',
      align: 'right',
      width: '130px',
      render: (row) => (
        <span style={{ fontWeight: 600 }}>
          <Money amount={row.grand_total} />
        </span>
      ),
    },
    {
      header: 'Status',
      accessor: 'status',
      align: 'center',
      width: '130px',
      render: (row) => <StatusTracker status={row.status} compact={true} />,
    },
    {
      header: 'Action',
      align: 'right',
      width: '80px',
      render: (row) => (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={(e) => {
            e.stopPropagation();
            setSelectedOrderNo(row.order_number);
          }}
        >
          View
        </button>
      ),
    },
  ], [dealers]);

  const totalPages = Math.max(1, Math.ceil(count / pageSize));

  return (
    <div className="orders-page">
      <div className="page-header">
        <div className="page-header-title-group">
          <h1>Purchase Orders</h1>
          <p className="page-header-desc">
            Complete transaction history and draft order records for authorized dealerships.
          </p>
        </div>
      </div>

      {/* Filter toolbar */}
      <div className="filter-toolbar">
        <div className="filter-group">
          <label htmlFor="dealer-filter" className="text-xs text-muted">
            Dealer:
          </label>
          <select
            id="dealer-filter"
            value={filterDealerId}
            onChange={(e) => {
              setFilterDealerId(e.target.value);
              setPage(1);
            }}
            className="select-input"
          >
            <option value="">All Dealers</option>
            {dealers.map((d) => (
              <option key={d.id} value={d.id}>
                {d.dealer_code} — {d.name}
              </option>
            ))}
          </select>

          <label htmlFor="status-filter" className="text-xs text-muted" style={{ marginLeft: '8px' }}>
            Status:
          </label>
          <select
            id="status-filter"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="select-input"
          >
            <option value="">All Statuses</option>
            <option value="DRAFT">DRAFT</option>
            <option value="CONFIRMED">CONFIRMED</option>
            <option value="DISPATCHED">DISPATCHED</option>
            <option value="DELIVERED">DELIVERED</option>
            <option value="CANCELLED">CANCELLED</option>
          </select>

          {(filterDealerId || statusFilter) && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setFilterDealerId('');
                setStatusFilter('');
                setPage(1);
              }}
            >
              Reset filters
            </button>
          )}
        </div>

        <div className="result-count-text">
          {loading ? 'Fetching...' : `${count} total orders`}
        </div>
      </div>

      {/* Orders Table */}
      <DataTable
        columns={columns}
        data={orders}
        loading={loading}
        emptyMessage="No orders yet for this dealer"
        onRowClick={(row) => setSelectedOrderNo(row.order_number)}
        selectedKey={selectedOrderNo}
      />

      {/* Pagination Bar */}
      <div className="pagination-bar">
        <div>
          Showing {orders.length > 0 ? (page - 1) * pageSize + 1 : 0}–
          {Math.min(page * pageSize, count)} of {count} orders
        </div>

        <div className="pagination-actions">
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={page <= 1 || loading}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={page >= totalPages || loading}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            Next
          </button>
        </div>
      </div>

      {/* Order Detail Drawer & Printable invoice */}
      {selectedOrderNo && (
        <div
          className="drawer-backdrop"
          onClick={() => setSelectedOrderNo(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="drawer"
            style={{ width: '600px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="drawer-header">
              <div>
                <OrderNumberDisplay orderNumber={selectedOrderNo} />
                <h2 style={{ fontSize: '15px', marginTop: '4px', fontWeight: 600 }}>
                  Order Details
                </h2>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => window.print()}
                  title="Print invoice or order slip"
                >
                  <IconPrinter size={14} />
                  <span>Print</span>
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setSelectedOrderNo(null)}
                  aria-label="Close drawer"
                >
                  <IconClose size={16} />
                </button>
              </div>
            </div>

            <div className="drawer-body">
              {loadingDetail ? (
                <div className="text-muted text-sm">Loading order lines...</div>
              ) : orderDetail ? (
                <>
                  {/* Status Progress Tracker */}
                  <StatusTracker status={orderDetail.status} />

                  <div style={{ background: 'var(--bg-surface-subtle)', padding: '12px', borderRadius: '4px', border: '1px solid var(--border-color)', fontSize: '13px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      <div>
                        <div className="text-xs text-muted">Dealer Account</div>
                        <div style={{ fontWeight: 600 }}>
                          Dealer #{orderDetail.dealer_id}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-muted">Created Timestamp</div>
                        <div>{formatDate(orderDetail.created_at)}</div>
                      </div>
                      <div>
                        <div className="text-xs text-muted">Current Status</div>
                        <div style={{ marginTop: '2px' }}>
                          <StatusBadge type="order" status={orderDetail.status} />
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-muted">Last Updated</div>
                        <div>{formatDate(orderDetail.updated_at)}</div>
                      </div>
                    </div>
                  </div>

                  <div>
                    <div className="text-xs text-muted" style={{ fontWeight: 600, textTransform: 'uppercase', marginBottom: '8px' }}>
                      Itemized Line Details
                    </div>
                    <table className="data-table" style={{ fontSize: '12px' }}>
                      <thead>
                        <tr>
                          <th>SKU</th>
                          <th>Part</th>
                          <th className="text-right">Price</th>
                          <th className="text-center">Qty</th>
                          <th className="text-right">Subtotal</th>
                          <th className="text-right">Tax (18%)</th>
                          <th className="text-right">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {orderDetail.items?.map((it, idx) => (
                          <tr key={idx}>
                            <td>
                              <button
                                type="button"
                                className="sku-chip"
                                onClick={() => onOpenProduct(it.sku)}
                              >
                                {it.sku}
                              </button>
                            </td>
                            <td style={{ maxWidth: '140px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {it.name}
                            </td>
                            <td className="text-right">
                              <Money amount={it.unit_price} />
                            </td>
                            <td className="text-center tabular-nums">{it.quantity}</td>
                            <td className="text-right">
                              <Money amount={it.line_subtotal} />
                            </td>
                            <td className="text-right text-muted">
                              <Money amount={it.line_tax} />
                            </td>
                            <td className="text-right" style={{ fontWeight: 600 }}>
                              <Money amount={it.line_total} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div className="ledger-card" style={{ marginTop: 'auto' }}>
                    <div className="ledger-row">
                      <span className="text-muted">Subtotal:</span>
                      <Money amount={orderDetail.subtotal} />
                    </div>
                    <div className="ledger-row">
                      <span className="text-muted">GST Total (18%):</span>
                      <Money amount={orderDetail.tax_total} />
                    </div>
                    <div className="ledger-row total-row">
                      <span>Grand Total:</span>
                      <Money amount={orderDetail.grand_total} />
                    </div>
                  </div>
                </>
              ) : null}
            </div>
          </div>
        </div>
      )}

      {/* Printable Invoice View (Revealed when printing) */}
      {orderDetail && (
        <div className="printable-order" style={{ display: 'none' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '2px solid #000', paddingBottom: '12px', marginBottom: '16px' }}>
            <div>
              <h1 style={{ fontSize: '20px', margin: 0 }}>VIKMO DealerDesk — Trade Invoice</h1>
              <p style={{ margin: '4px 0 0 0', fontSize: '12px' }}>Automotive Parts Distribution Hub, Bengaluru</p>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontWeight: 'bold' }}>{orderDetail.order_number}</div>
              <div style={{ fontSize: '12px' }}>Date: {formatDate(orderDetail.created_at)}</div>
              <div style={{ fontSize: '12px' }}>Status: {orderDetail.status}</div>
            </div>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '16px', fontSize: '12px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #000' }}>
                <th style={{ textAlign: 'left', padding: '6px' }}>SKU</th>
                <th style={{ textAlign: 'left', padding: '6px' }}>Part</th>
                <th style={{ textAlign: 'right', padding: '6px' }}>Unit Price</th>
                <th style={{ textAlign: 'center', padding: '6px' }}>Qty</th>
                <th style={{ textAlign: 'right', padding: '6px' }}>Subtotal</th>
                <th style={{ textAlign: 'right', padding: '6px' }}>GST (18%)</th>
                <th style={{ textAlign: 'right', padding: '6px' }}>Total</th>
              </tr>
            </thead>
            <tbody>
              {orderDetail.items?.map((it, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid #ddd' }}>
                  <td style={{ padding: '6px', fontFamily: 'monospace' }}>{it.sku}</td>
                  <td style={{ padding: '6px' }}>{it.name}</td>
                  <td style={{ padding: '6px', textAlign: 'right' }}>{it.unit_price}</td>
                  <td style={{ padding: '6px', textAlign: 'center' }}>{it.quantity}</td>
                  <td style={{ padding: '6px', textAlign: 'right' }}>{it.line_subtotal}</td>
                  <td style={{ padding: '6px', textAlign: 'right' }}>{it.line_tax}</td>
                  <td style={{ padding: '6px', textAlign: 'right' }}>{it.line_total}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ width: '250px', marginLeft: 'auto', fontSize: '12px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
              <span>Subtotal:</span>
              <span>{orderDetail.subtotal}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0' }}>
              <span>GST Total:</span>
              <span>{orderDetail.tax_total}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderTop: '1px solid #000', fontWeight: 'bold' }}>
              <span>Grand Total:</span>
              <span>Rs. {orderDetail.grand_total}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
