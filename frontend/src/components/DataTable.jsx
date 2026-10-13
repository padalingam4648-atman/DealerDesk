import React from 'react';

/**
 * DataTable Component
 * Features:
 * - Dense 40px rows
 * - Sticky header
 * - Row hover effect, no zebra
 * - Skeleton rows on loading to prevent layout shift
 * - Ledger column alignments (right-aligned for numbers/prices)
 */
export default function DataTable({
  columns = [],
  data = [],
  loading = false,
  emptyMessage = 'No records found',
  onRowClick = null,
  selectedKey = null,
  rowKey = (row) => row.id || row.sku || row.order_number,
}) {
  return (
    <div className="table-container">
      <table className="data-table" role="table">
        <thead>
          <tr role="row">
            {columns.map((col, idx) => (
              <th
                key={col.key || idx}
                scope="col"
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
            // Render 6 skeleton rows while fetching data to prevent layout shift
            Array.from({ length: 6 }).map((_, rIdx) => (
              <tr key={`skel-${rIdx}`} className="skeleton-row" role="row">
                {columns.map((col, cIdx) => (
                  <td key={`skel-c-${cIdx}`}>
                    <div style={{ width: col.align === 'right' ? '60%' : '80%', marginLeft: col.align === 'right' ? 'auto' : 0 }} />
                  </td>
                ))}
              </tr>
            ))
          ) : data.length === 0 ? (
            <tr role="row">
              <td colSpan={columns.length} style={{ height: '120px', textAlign: 'center', color: 'var(--text-muted)' }}>
                {emptyMessage}
              </td>
            </tr>
          ) : (
            data.map((row, rIdx) => {
              const key = rowKey(row, rIdx);
              const isSelected = selectedKey && selectedKey === key;
              return (
                <tr
                  key={key}
                  role="row"
                  className={isSelected ? 'selected' : ''}
                  onClick={() => onRowClick && onRowClick(row)}
                  style={{ cursor: onRowClick ? 'pointer' : 'default' }}
                >
                  {columns.map((col, cIdx) => {
                    const val = col.accessor ? (typeof col.accessor === 'function' ? col.accessor(row) : row[col.accessor]) : null;
                    return (
                      <td
                        key={col.key || cIdx}
                        className={col.align === 'right' ? 'text-right tabular-nums' : col.align === 'center' ? 'text-center' : ''}
                      >
                        {col.render ? col.render(row, val) : val}
                      </td>
                    );
                  })}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
