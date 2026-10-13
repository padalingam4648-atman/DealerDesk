import React, { useState, useEffect, useRef } from 'react';
import { postAssistantChat } from '../api';
import { useDealer } from '../context/DealerContext';
import { IconClose } from './Icons';

export default function AssistantDrawer({ onClose, onSelectSku, isPage = false }) {
  const { selectedDealer, selectedDealerId } = useDealer();
  const [messages, setMessages] = useState(() => {
    try {
      const saved = sessionStorage.getItem('dealerdesk_chat_history');
      return saved ? JSON.parse(saved) : [
        {
          role: 'assistant',
          reply: 'DealerDesk assistant ready. Ask about part fitment, warehouse stock levels, or request a draft purchase order.',
          cited_skus: [],
          tool_calls: [],
          actions: [],
        },
      ];
    } catch {
      return [];
    }
  });

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  // Maintain a stable session_id per tab
  const sessionIdRef = useRef('');
  if (!sessionIdRef.current) {
    let sid = sessionStorage.getItem('dealerdesk_chat_session_id');
    if (!sid) {
      sid = 'ses-' + Math.random().toString(36).substring(2, 10);
      sessionStorage.setItem('dealerdesk_chat_session_id', sid);
    }
    sessionIdRef.current = sid;
  }

  useEffect(() => {
    sessionStorage.setItem('dealerdesk_chat_history', JSON.stringify(messages));
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const handleSend = async (textToSend) => {
    const text = (textToSend || input).trim();
    if (!text || loading) return;

    setInput('');
    setError(null);

    // Append user message
    const userMsg = { role: 'user', text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const response = await postAssistantChat(
        sessionIdRef.current,
        selectedDealerId,
        text
      );

      const assistantMsg = {
        role: 'assistant',
        reply: response.reply,
        cited_skus: response.cited_skus || [],
        tool_calls: response.tool_calls || [],
        actions: response.actions || [],
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      setError(err.message || 'Failed to communicate with Groq assistant.');
    } finally {
      setLoading(false);
    }
  };

  const suggestions = [
    'Do you have brake pads for Pulsar 150?',
    'Check stock for BRK-1044',
    'What oil filters are low on stock?',
  ];

  return (
    <div className={`chat-container ${isPage ? 'chat-page' : ''}`} role="complementary" aria-label="Dealer Assistant">
      <div className="chat-header">
        <div>
          <div className="chat-header-title">Dealer Assistant (Groq)</div>
          <div className="text-xs text-muted">
            Live grounding for {selectedDealer?.dealer_code || 'Counter'}
          </div>
        </div>
        {!isPage && onClose && (
          <button className="btn btn-secondary btn-sm" onClick={onClose} aria-label="Close assistant">
            <IconClose size={14} />
          </button>
        )}
      </div>

      <div className="chat-messages">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`chat-bubble ${msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'}`}
          >
            {msg.role === 'user' ? (
              <div>{msg.text}</div>
            ) : (
              <div>
                <div>{msg.reply}</div>

                {/* SKU Chips */}
                {msg.cited_skus && msg.cited_skus.length > 0 && (
                  <div className="cited-skus-row">
                    <span className="text-xs text-muted">Referenced parts:</span>
                    {msg.cited_skus.map((sku) => (
                      <button
                        key={sku}
                        type="button"
                        className="sku-chip"
                        onClick={() => onSelectSku && onSelectSku(sku)}
                        title={`View ${sku} in drawer`}
                      >
                        {sku}
                      </button>
                    ))}
                  </div>
                )}

                {/* Side Effects / Draft Orders */}
                {msg.actions && msg.actions.length > 0 && (
                  <div style={{ marginTop: '6px' }}>
                    {msg.actions.map((act, aIdx) => (
                      <div
                        key={aIdx}
                        style={{
                          background: 'var(--accent-subtle)',
                          border: '1px solid var(--border-color)',
                          borderRadius: '4px',
                          padding: '4px 8px',
                          fontSize: '12px',
                        }}
                      >
                        <strong>Draft order created:</strong>{' '}
                        <a href={`#/orders`}>{act.order_number}</a>
                      </div>
                    ))}
                  </div>
                )}

                {/* Collapsed Tool Calls Disclosure */}
                {msg.tool_calls && msg.tool_calls.length > 0 && (
                  <details className="tool-calls-disclosure">
                    <summary className="tool-calls-summary">
                      Tool calls ({msg.tool_calls.length})
                    </summary>
                    <div className="tool-calls-body">
                      {JSON.stringify(msg.tool_calls, null, 2)}
                    </div>
                  </details>
                )}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="chat-bubble chat-bubble-assistant text-muted text-xs">
            Querying live parts database & reasoning...
          </div>
        )}

        {error && (
          <div style={{ color: 'var(--status-out-stock)', fontSize: '12px', padding: '4px 8px' }}>
            {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        {/* Suggestion Chips */}
        <div className="chat-suggestions">
          {suggestions.map((s, i) => (
            <button
              key={i}
              type="button"
              className="suggestion-chip"
              onClick={() => handleSend(s)}
              disabled={loading}
            >
              {s}
            </button>
          ))}
        </div>

        <form
          className="chat-form"
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
        >
          <input
            type="text"
            className="input-text chat-input"
            placeholder="Ask about parts, stock, or draft an order..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <button
            type="submit"
            className="btn btn-primary btn-sm"
            disabled={loading || !input.trim()}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
