import React, { useState } from 'react';
import { Network, Server, User, ShoppingBag, CreditCard, RotateCcw, Landmark, AlertTriangle, Send } from 'lucide-react';
import { formatINR } from './OperationsKPIs';

export default function MoneyGraphVisualizer({ graphData, incidentType, targetId }) {
  const [selectedNode, setSelectedNode] = useState(null);

  // Generate deterministic layout positions for the nodes
  const nodes = (graphData?.nodes && graphData.nodes.length > 0) ? graphData.nodes : getDefaultNodes(incidentType, targetId);
  const edges = (graphData?.edges && graphData.edges.length > 0) ? graphData.edges : getDefaultEdges(incidentType, targetId);

  // Calculate clean layer-based coordinates
  const positionedNodes = calculateLayout(nodes);

  return (
    <div style={{
      background: 'rgba(10, 14, 23, 0.95)',
      border: '1px solid var(--border-subtle)',
      borderRadius: '10px',
      padding: '16px',
      position: 'relative',
      overflow: 'hidden'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Network size={16} color="#38bdf8" />
          <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            Financial Relationship Money Graph
          </span>
        </div>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {nodes.length} Connected Entities | Cross-entity Correlation
        </span>
      </div>

      {/* SVG Canvas */}
      <div style={{ width: '100%', height: '240px', position: 'relative' }}>
        <svg style={{ width: '100%', height: '100%', overflow: 'visible' }}>
          <defs>
            <linearGradient id="edgeGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.6" />
              <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.6" />
            </linearGradient>
            <linearGradient id="edgeFailGrad" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#f59e0b" stopOpacity="0.8" />
            </linearGradient>
          </defs>

          {/* Render Edges */}
          {edges.map((edge, idx) => {
            const sourceNode = positionedNodes.find(n => n.id === edge.source);
            const targetNode = positionedNodes.find(n => n.id === edge.target);
            if (!sourceNode || !targetNode) return null;

            const isFailing = edge.relation?.includes('FAILED') || edge.relation?.includes('TIMEOUT') || sourceNode.status === 'failed' || targetNode.status === 'failed';

            return (
              <g key={idx}>
                <line
                  x1={sourceNode.x}
                  y1={sourceNode.y}
                  x2={targetNode.x}
                  y2={targetNode.y}
                  stroke={isFailing ? "url(#edgeFailGrad)" : "url(#edgeGrad)"}
                  strokeWidth={isFailing ? "2" : "1.5"}
                  strokeDasharray={isFailing ? "4 2" : "none"}
                />
                {/* Edge Label Pill */}
                <text
                  x={(sourceNode.x + targetNode.x) / 2}
                  y={(sourceNode.y + targetNode.y) / 2 - 4}
                  fill="#94a3b8"
                  fontSize="9"
                  fontFamily="Inter, sans-serif"
                  fontWeight="600"
                  textAnchor="middle"
                  style={{ background: '#0f172a' }}
                >
                  {edge.relation}
                </text>
              </g>
            );
          })}

          {/* Render Nodes */}
          {positionedNodes.map((node) => {
            const isTarget = node.is_target;
            const isFailing = node.status === 'failed' || node.status === 'timed_out' || node.type === 'Gateway' && node.status === 'degraded';
            const isDuplicate = node.is_duplicate;

            let nodeColor = '#3b82f6';
            let glow = 'rgba(59, 130, 246, 0.3)';
            if (isFailing || isDuplicate) {
              nodeColor = '#ef4444';
              glow = 'rgba(239, 68, 68, 0.4)';
            } else if (node.type === 'Customer') {
              nodeColor = '#a855f7';
            } else if (node.type === 'Merchant') {
              nodeColor = '#10b981';
            } else if (node.type === 'WebhookEvent') {
              nodeColor = '#06b6d4';
            }

            return (
              <g
                key={node.id}
                transform={`translate(${node.x}, ${node.y})`}
                onClick={() => setSelectedNode(node)}
                style={{ cursor: 'pointer' }}
              >
                {/* Outer Pulse if target / failing */}
                {(isTarget || isFailing) && (
                  <circle r="22" fill="none" stroke={nodeColor} strokeWidth="1.5" opacity="0.4">
                    <animate attributeName="r" values="18;26;18" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.6;0.1;0.6" dur="2s" repeatCount="indefinite" />
                  </circle>
                )}

                {/* Main Node Circle */}
                <circle
                  r="16"
                  fill="#0f172a"
                  stroke={nodeColor}
                  strokeWidth={isTarget ? "2.5" : "1.8"}
                  filter={`drop-shadow(0 0 6px ${glow})`}
                />

                {/* Node Icon */}
                <g transform="translate(-8, -8)">
                  {renderNodeIcon(node.type, nodeColor)}
                </g>

                {/* Node Label Below */}
                <text
                  y="26"
                  fill="#f8fafc"
                  fontSize="10"
                  fontWeight="600"
                  fontFamily="Inter, sans-serif"
                  textAnchor="middle"
                >
                  {node.label || node.id}
                </text>

                {/* Node Amount / Subtext */}
                {node.amount && (
                  <text
                    y="36"
                    fill="#38bdf8"
                    fontSize="9"
                    fontWeight="700"
                    fontFamily="JetBrains Mono, monospace"
                    textAnchor="middle"
                  >
                    {formatINR(node.amount)}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Selected Node Inspector Drawer */}
      {selectedNode && (
        <div style={{
          marginTop: '10px',
          padding: '10px 14px',
          background: 'rgba(30, 41, 59, 0.7)',
          borderRadius: '8px',
          border: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '0.75rem'
        }}>
          <div>
            <span style={{ fontWeight: 700, color: '#38bdf8' }}>{selectedNode.type}: </span>
            <span className="mono" style={{ color: 'var(--text-primary)' }}>{selectedNode.id}</span>
            <span style={{ color: 'var(--text-muted)', marginLeft: '8px' }}>Status: {selectedNode.status || 'Active'}</span>
          </div>
          <button
            onClick={() => setSelectedNode(null)}
            className="btn btn-ghost"
            style={{ padding: '2px 8px', fontSize: '0.7rem' }}
          >
            Close
          </button>
        </div>
      )}
    </div>
  );
}

function renderNodeIcon(type, color) {
  switch (type) {
    case 'Merchant': return <Landmark size={16} color={color} />;
    case 'Customer': return <User size={16} color={color} />;
    case 'Order': return <ShoppingBag size={16} color={color} />;
    case 'Payment': return <CreditCard size={16} color={color} />;
    case 'Refund': return <RotateCcw size={16} color={color} />;
    case 'Gateway': return <Server size={16} color={color} />;
    case 'WebhookEvent': return <Send size={16} color={color} />;
    default: return <CreditCard size={16} color={color} />;
  }
}

function calculateLayout(nodes) {
  const width = 640;
  const height = 220;

  // Layer assignment based on entity type
  const layers = {
    Gateway: 0,
    Merchant: 1,
    Customer: 1,
    Order: 2,
    Payment: 3,
    Refund: 4,
    Settlement: 4,
    WebhookEvent: 5
  };

  const grouped = {};
  nodes.forEach(n => {
    const l = layers[n.type] !== undefined ? layers[n.type] : 3;
    if (!grouped[l]) grouped[l] = [];
    grouped[l].push(n);
  });

  const layerKeys = Object.keys(grouped).sort((a, b) => Number(a) - Number(b));
  const numLayers = layerKeys.length || 1;
  const xStep = width / (numLayers + 1);

  const positioned = [];
  layerKeys.forEach((lKey, lIdx) => {
    const items = grouped[lKey];
    const yStep = height / (items.length + 1);
    items.forEach((item, itemIdx) => {
      positioned.push({
        ...item,
        x: Math.round(xStep * (lIdx + 1) + 20),
        y: Math.round(yStep * (itemIdx + 1))
      });
    });
  });

  return positioned;
}

function getDefaultNodes(incidentType, targetId) {
  if (incidentType === 'gateway_refund_failure') {
    return [
      { id: 'Gateway_X', type: 'Gateway', label: 'Gateway X (Node Degradation)', status: 'degraded', is_target: true },
      { id: 'merch_Nova_Store', type: 'Merchant', label: 'Nova Store', status: 'affected' },
      { id: 'merch_Quick_Bite', type: 'Merchant', label: 'QuickBite', status: 'affected' },
      { id: 'pay_gwx_001', type: 'Payment', label: 'Pay gwx-001', amount: 1499, status: 'captured' },
      { id: 'pay_gwx_002', type: 'Payment', label: 'Pay gwx-002', amount: 2499, status: 'captured' },
      { id: 'rfnd_gwx_001', type: 'Refund', label: 'Refund gwx-001', amount: 1499, status: 'failed' },
      { id: 'rfnd_gwx_002', type: 'Refund', label: 'Refund gwx-002', amount: 2499, status: 'failed' },
      { id: 'wh_gwx_001', type: 'WebhookEvent', label: 'WH 504 Timeout', status: 'timed_out' }
    ];
  }

  // Duplicate Refund on P19283
  return [
    { id: 'cust_P19283_VIP', type: 'Customer', label: 'Arjun S. (Customer)', status: 'active' },
    { id: 'merch_Nova_Store', type: 'Merchant', label: 'Nova Store', status: 'active' },
    { id: 'ord_O8821', type: 'Order', label: 'Order O8821', amount: 4999, status: 'paid' },
    { id: 'pay_P19283', type: 'Payment', label: 'Pay P19283', amount: 4999, status: 'captured', is_target: true },
    { id: 'rfnd_R8821', type: 'Refund', label: 'Refund R8821', amount: 4999, status: 'processed' },
    { id: 'rfnd_R8842', type: 'Refund', label: 'Refund R8842 (DUPLICATE)', amount: 4999, status: 'failed', is_duplicate: true },
    { id: 'wh_W8812', type: 'WebhookEvent', label: 'WH 504 Timeout', status: 'timed_out' },
    { id: 'wh_W8813', type: 'WebhookEvent', label: 'WH Delivered', status: 'delivered' }
  ];
}

function getDefaultEdges(incidentType, targetId) {
  if (incidentType === 'gateway_refund_failure') {
    return [
      { source: 'merch_Nova_Store', target: 'pay_gwx_001', relation: 'MERCHANT_OF' },
      { source: 'merch_Quick_Bite', target: 'pay_gwx_002', relation: 'MERCHANT_OF' },
      { source: 'pay_gwx_001', target: 'Gateway_X', relation: 'ROUTED_TO' },
      { source: 'pay_gwx_002', target: 'Gateway_X', relation: 'ROUTED_TO' },
      { source: 'pay_gwx_001', target: 'rfnd_gwx_001', relation: 'REFUND_REQ' },
      { source: 'pay_gwx_002', target: 'rfnd_gwx_002', relation: 'REFUND_REQ' },
      { source: 'rfnd_gwx_001', target: 'wh_gwx_001', relation: 'TIMEOUT_504' }
    ];
  }

  return [
    { source: 'cust_P19283_VIP', target: 'ord_O8821', relation: 'PLACED' },
    { source: 'merch_Nova_Store', target: 'ord_O8821', relation: 'FULFILLS' },
    { source: 'ord_O8821', target: 'pay_P19283', relation: 'PAID_WITH' },
    { source: 'pay_P19283', target: 'rfnd_R8821', relation: 'REFUND_1' },
    { source: 'pay_P19283', target: 'rfnd_R8842', relation: 'DUPLICATE_RACE' },
    { source: 'rfnd_R8821', target: 'wh_W8812', relation: 'TIMEOUT_504' },
    { source: 'rfnd_R8842', target: 'wh_W8813', relation: 'RETRY_ACK' }
  ];
}
