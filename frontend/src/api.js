/**
 * VIKMO DealerDesk - API Client
 * Clean fetch wrapper that handles standard JSON responses and API error shapes:
 * { "error": { "code": "...", "message": "...", "details": [] } }
 */

export class ApiError extends Error {
  constructor(status, code, message, details = []) {
    super(message || `API error (${status})`);
    this.name = 'ApiError';
    this.status = status;
    this.code = code || 'UNKNOWN_ERROR';
    this.details = details;
  }
}

/**
 * Base fetch wrapper that handles JSON deserialization and error parsing
 */
export async function apiFetch(endpoint, options = {}) {
  const url = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

  const defaultHeaders = {
    'Accept': 'application/json',
  };

  if (options.body && typeof options.body === 'string') {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  const config = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  };

  let response;
  try {
    response = await fetch(url, config);
  } catch (netErr) {
    throw new ApiError(0, 'NETWORK_ERROR', 'Network connection failed. Please check backend connectivity.');
  }

  let data = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch (parseErr) {
      // Empty or invalid JSON
      data = null;
    }
  }

  if (!response.ok) {
    if (data && data.error) {
      throw new ApiError(
        response.status,
        data.error.code,
        data.error.message,
        data.error.details || []
      );
    }
    throw new ApiError(
      response.status,
      `HTTP_${response.status}`,
      `Server returned HTTP ${response.status}`,
      []
    );
  }

  return data;
}

// Concrete Endpoint Functions

export async function checkHealth() {
  return apiFetch('/api/health/');
}

export async function fetchProducts(params = {}) {
  const query = new URLSearchParams();
  if (params.page) query.set('page', params.page);
  if (params.pageSize || params.page_size) query.set('page_size', params.pageSize || params.page_size);
  if (params.search) query.set('search', params.search);
  if (params.category) query.set('category', params.category);
  if (params.vehicle) query.set('vehicle', params.vehicle);

  const qs = query.toString();
  return apiFetch(`/api/products/${qs ? `?${qs}` : ''}`);
}

export async function fetchProduct(sku) {
  return apiFetch(`/api/products/${encodeURIComponent(sku)}/`);
}

export async function fetchDealers(params = {}) {
  const query = new URLSearchParams();
  if (params.page) query.set('page', params.page);
  if (params.pageSize || params.page_size) query.set('page_size', params.pageSize || params.page_size);

  const qs = query.toString();
  return apiFetch(`/api/dealers/${qs ? `?${qs}` : ''}`);
}

export async function fetchDealer(id) {
  return apiFetch(`/api/dealers/${id}/`);
}

export async function fetchOrders(params = {}) {
  const query = new URLSearchParams();
  if (params.dealer_id) query.set('dealer_id', params.dealer_id);
  if (params.status) query.set('status', params.status);
  if (params.page) query.set('page', params.page);
  if (params.pageSize || params.page_size) query.set('page_size', params.pageSize || params.page_size);

  const qs = query.toString();
  return apiFetch(`/api/orders/${qs ? `?${qs}` : ''}`);
}

export async function fetchOrder(orderNumber) {
  return apiFetch(`/api/orders/${encodeURIComponent(orderNumber)}/`);
}

export async function createOrder(dealerId, items) {
  return apiFetch('/api/orders/', {
    method: 'POST',
    body: JSON.stringify({
      dealer_id: Number(dealerId),
      items: items.map(item => ({
        sku: item.sku,
        quantity: Number(item.quantity),
      })),
    }),
  });
}

export async function fetchForecast(sku) {
  return apiFetch(`/api/forecast/${encodeURIComponent(sku)}/`);
}

export async function fetchReorderSuggestions() {
  return apiFetch('/api/reorder-suggestions/');
}

export async function postAssistantChat(sessionId, dealerId, message) {
  return apiFetch('/api/assistant/chat/', {
    method: 'POST',
    body: JSON.stringify({
      session_id: sessionId,
      dealer_id: Number(dealerId),
      message: message,
    }),
  });
}
