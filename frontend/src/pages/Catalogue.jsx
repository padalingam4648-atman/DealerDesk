import React, { useState, useEffect, useRef, useMemo } from 'react';
import { fetchProducts } from '../api';
import DataTable from '../components/DataTable';
import Money from '../components/Money';
import StatusBadge from '../components/StatusBadge';
import ProductDrawer from '../components/ProductDrawer';
import { IconSearch } from '../components/Icons';
import { useCart } from '../context/CartContext';

export default function Catalogue({ onOpenProduct, selectedSku, onCloseProduct }) {
  const { addToCart } = useCart();
  const [products, setProducts] = useState([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [category, setCategory] = useState('');
  const [vehicle, setVehicle] = useState('');

  const searchInputRef = useRef(null);

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 250);
    return () => clearTimeout(handler);
  }, [search]);

  // "/" Keyboard shortcut to focus search
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === '/' && document.activeElement !== searchInputRef.current && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Fetch products when page or filters change
  useEffect(() => {
    let isMounted = true;
    setLoading(true);

    async function loadData() {
      try {
        const res = await fetchProducts({
          page,
          pageSize,
          search: debouncedSearch.trim() || undefined,
          category: category || undefined,
          vehicle: vehicle.trim() || undefined,
        });

        if (isMounted) {
          setProducts(res.results || []);
          setCount(res.count || 0);
        }
      } catch (err) {
        console.error('Failed to load catalogue', err);
        if (isMounted) {
          setProducts([]);
          setCount(0);
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadData();
    return () => {
      isMounted = false;
    };
  }, [page, pageSize, debouncedSearch, category, vehicle]);

  // Common motorcycle/car categories in DealerDesk catalogue
  const categories = [
    'Brakes',
    'Chain & Sprockets',
    'Electrical',
    'Engine',
    'Filters',
    'Grips & Controls',
    'Lubricants',
    'Suspension',
  ];

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
          title="Click to view details"
        >
          {row.sku}
        </button>
      ),
    },
    {
      header: 'Part Name',
      accessor: 'name',
      render: (row) => (
        <span style={{ fontWeight: 500 }} title={row.name}>
          {row.name}
        </span>
      ),
    },
    {
      header: 'Category',
      accessor: 'category',
      width: '130px',
      render: (row) => <span className="text-muted">{row.category}</span>,
    },
    {
      header: 'Brand',
      accessor: 'brand',
      width: '110px',
      render: (row) => <span className="text-muted">{row.brand}</span>,
    },
    {
      header: 'Vehicle Fitment',
      accessor: 'vehicle_fitment',
      width: '160px',
      render: (row) => <span className="text-muted">{row.vehicle_fitment}</span>,
    },
    {
      header: 'Unit Price',
      accessor: 'price',
      align: 'right',
      width: '110px',
      render: (row) => <Money amount={row.price} />,
    },
    {
      header: 'Warehouse Stock',
      accessor: 'stock',
      align: 'right',
      width: '120px',
      render: (row) => <StatusBadge type="stock" stock={row.stock} />,
    },
    {
      header: 'Action',
      align: 'right',
      width: '110px',
      render: (row) => (
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={(e) => {
            e.stopPropagation();
            addToCart(row, 1);
          }}
          title="Add 1 unit to draft order"
        >
          Add to draft
        </button>
      ),
    },
  ], [onOpenProduct, addToCart]);

  const totalPages = Math.max(1, Math.ceil(count / pageSize));

  return (
    <div className="catalogue-page">
      <div className="page-header">
        <div className="page-header-title-group">
          <h1>Parts Catalogue</h1>
          <p className="page-header-desc">
            Complete warehouse inventory for motorcycle & automotive spare parts.
          </p>
        </div>
      </div>

      {/* Filter and Search Controls */}
      <div className="filter-toolbar">
        <div className="filter-group">
          <div className="search-input-wrap">
            <span className="search-icon-inline">
              <IconSearch size={14} />
            </span>
            <input
              ref={searchInputRef}
              type="text"
              placeholder="Search SKU, part or brand..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-text"
              aria-label="Search parts"
            />
            <span className="search-kbd-hint">/</span>
          </div>

          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              setPage(1);
            }}
            className="select-input"
            aria-label="Filter by category"
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>
                {cat}
              </option>
            ))}
          </select>

          <input
            type="text"
            placeholder="Vehicle fitment (e.g. Pulsar)..."
            value={vehicle}
            onChange={(e) => {
              setVehicle(e.target.value);
              setPage(1);
            }}
            className="input-text"
            style={{ width: '180px' }}
            aria-label="Filter by vehicle"
          />

          {(debouncedSearch || category || vehicle) && (
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => {
                setSearch('');
                setCategory('');
                setVehicle('');
                setPage(1);
              }}
            >
              Clear filters
            </button>
          )}
        </div>

        <div className="result-count-text">
          {loading ? 'Updating...' : `${count} matching items`}
        </div>
      </div>

      {/* Main Table */}
      <DataTable
        columns={columns}
        data={products}
        loading={loading}
        emptyMessage="No spare parts match your query."
        onRowClick={(row) => onOpenProduct(row.sku)}
        selectedKey={selectedSku}
      />

      {/* Pagination Bar */}
      <div className="pagination-bar">
        <div>
          Showing {products.length > 0 ? (page - 1) * pageSize + 1 : 0}–
          {Math.min(page * pageSize, count)} of {count} parts
        </div>

        <div className="pagination-actions">
          <label htmlFor="pageSize-select" className="text-xs text-muted">
            Rows:
          </label>
          <select
            id="pageSize-select"
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
            className="select-input"
            style={{ height: '28px', padding: '0 4px', fontSize: '12px' }}
          >
            <option value={20}>20</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>

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

      {/* Slide-out Product Drawer */}
      {selectedSku && (
        <ProductDrawer sku={selectedSku} onClose={onCloseProduct} />
      )}
    </div>
  );
}
