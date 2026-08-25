import React, { useState } from 'react';
import { Send, CheckCircle2, ShieldAlert, X, Zap, ArrowRight, Code } from 'lucide-react';
import { formatINR } from './OperationsKPIs';

export default function WebhookSimulatorModal({ isOpen, onClose, onWebhookSent }) {
  const [eventType, setEventType] = useState('payment.captured');
  const [amount, setAmount] = useState(2499);
  const [merchantId, setMerchantId] = useState('merch_Nova_Store');
  const [isSending, setIsSending] = useState(false);
  const [result, setResult] = useState(null);

  if (!isOpen) return null;

  const handleSendWebhook = async () => {
    setIsSending(true);
    setResult(null);
    try {
      const payload = {
        event: eventType,
        id: `wh_live_${Date.now()}`,
        payload: eventType.startsWith('refund') ? {
          refund: {
            entity: {
              id: `rfnd_live_${Date.now().toString().slice(-6)}`,
              payment_id: "pay_P19283",
              amount: amount * 100, // paise
              status: "processed",
              speed: "instant"
            }
          }
        } : {
          payment: {
            entity: {
              id: `pay_live_${Date.now().toString().slice(-6)}`,
              order_id: `ord_live_${Date.now().toString().slice(-6)}`,
              amount: amount * 100, // paise
              status: eventType === 'payment.captured' ? 'captured' : 'failed',
              method: 'card',
              notes: { merchant_id: merchantId },
              acquirer_data: { bank: 'Gateway_HDFC' }
            }
          }
        }
      };

      const res = await fetch("http://localhost:8000/api/webhooks/simulate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!res.ok) throw new Error("Webhook dispatch failed");
      const data = await res.json();
      setResult(data);
      if (onWebhookSent) onWebhookSent();
    } catch (err) {
      setResult({ error: err.message });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0, 0, 0, 0.75)',
      backdropFilter: 'blur(8px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 200,
      padding: '20px'
    }}>
      <div className="glass-panel animate-fade-in" style={{
        width: '100%',
        maxWidth: '560px',
        padding: '24px',
        border: '1px solid var(--border-accent)',
        position: 'relative'
      }}>
        
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '32px',
              height: '32px',
              borderRadius: '8px',
              background: 'linear-gradient(135deg, #06b6d4, #3b82f6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <Send size={16} color="#ffffff" />
            </div>
            <div>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                Razorpay Webhook Ingestion Console
              </h2>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                Simulate or ingest live Razorpay Test Mode webhooks with HMAC-SHA256 verification.
              </p>
            </div>
          </div>

          <button onClick={onClose} className="btn btn-ghost" style={{ padding: '6px' }}>
            <X size={16} />
          </button>
        </div>

        {/* Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginBottom: '18px' }}>
          <div>
            <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
              EVENT TYPE
            </label>
            <select
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
              style={{
                width: '100%',
                background: 'rgba(15, 20, 31, 0.9)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '8px 12px',
                color: 'var(--text-primary)',
                fontSize: '0.85rem',
                outline: 'none'
              }}
            >
              <option value="payment.captured">payment.captured (Success)</option>
              <option value="payment.failed">payment.failed (Failure)</option>
              <option value="refund.processed">refund.processed (Instant Refund)</option>
            </select>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            <div>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                AMOUNT (INR)
              </label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(Number(e.target.value))}
                style={{
                  width: '100%',
                  background: 'rgba(15, 20, 31, 0.9)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem',
                  outline: 'none'
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                MERCHANT
              </label>
              <select
                value={merchantId}
                onChange={(e) => setMerchantId(e.target.value)}
                style={{
                  width: '100%',
                  background: 'rgba(15, 20, 31, 0.9)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '8px 12px',
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem',
                  outline: 'none'
                }}
              >
                <option value="merch_Nova_Store">Nova E-Commerce</option>
                <option value="merch_Cloud_Desk">CloudDesk SaaS</option>
                <option value="merch_Quick_Bite">QuickBite Deliveries</option>
              </select>
            </div>
          </div>
        </div>

        {/* Dispatch Action */}
        <button
          onClick={handleSendWebhook}
          disabled={isSending}
          className="btn btn-primary"
          style={{ width: '100%', padding: '10px', fontSize: '0.85rem', marginBottom: '14px' }}
        >
          <Send size={15} />
          {isSending ? "Dispatching & Ingesting..." : "Dispatch Signed Webhook to MoneyOps"}
        </button>

        {/* Result Log */}
        {result && (
          <div style={{
            background: 'rgba(7, 9, 14, 0.9)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '8px',
            padding: '10px 14px',
            fontSize: '0.75rem'
          }}>
            {result.error ? (
              <span style={{ color: '#f87171' }}>Error: {result.error}</span>
            ) : (
              <div>
                <div style={{ color: '#34d399', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                  <CheckCircle2 size={13} />
                  Webhook Verified & Ingested into SQLite + Money Graph
                </div>
                <div className="mono" style={{ color: '#94a3b8' }}>
                  Event ID: <span style={{ color: '#38bdf8' }}>{result.event_id}</span> | Type: {result.event_type}
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
