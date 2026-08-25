import React from 'react';
import { Cpu, Database, Network, ShieldCheck, Zap, Layers, Server, GitBranch } from 'lucide-react';

export default function SystemArchitectureModal() {
  return (
    <div className="glass-panel animate-fade-in" style={{ padding: '28px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      
      {/* Title */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
          <Cpu size={22} color="#38bdf8" />
          <h1 style={{ fontSize: '1.3rem', fontWeight: 800, color: 'var(--text-primary)' }}>
            System Architecture & Engineering Judgment
          </h1>
        </div>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          How MoneyOps AI integrates Data Engineering, Machine Learning, Graph Modeling, Vector Case Memory, and Governed Agentic AI.
        </p>
      </div>

      {/* 4 Pillars Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
        
        {/* Pillar 1: Data Engineering */}
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <Database size={18} color="#38bdf8" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>1. Data Engineering Layer</h3>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
            • <strong>Lean Event Stream:</strong> Ingestion pipeline with <code>asyncio.Queue</code> normalizing payment, refund, settlement, and webhook events.<br />
            • <strong>Merchant Memory:</strong> Rolling behavioral profiler computing merchant-specific baselines (refund rates, retry velocity, failure distributions).<br />
            • <strong>Relational SQLite:</strong> Fast indexed financial entity store maintaining ACID consistency across transactions.
          </p>
        </div>

        {/* Pillar 2: Machine Learning & Anomaly Detection */}
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <Zap size={18} color="#f59e0b" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>2. Unsupervised ML Anomaly</h3>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
            • <strong>Isolation Forest:</strong> Unsupervised scikit-learn pipeline evaluating engineered transaction & merchant deviation vectors.<br />
            • <strong>Contextual Signals:</strong> Calibrated anomaly scores [0.0 - 1.0] with granular signal contributor breakdowns (retry velocity, gateway error spikes, SLA delay).
          </p>
        </div>

        {/* Pillar 3: Money Graph & Case Memory */}
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <Network size={18} color="#a855f7" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>3. Graph & Case Memory</h3>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
            • <strong>NetworkX Money Graph:</strong> Cross-entity graph modeling <code>Customer → Order → Payment → [Refunds, Settlement, Dispute, Webhooks]</code>.<br />
            • <strong>Vector Case Memory:</strong> TF-IDF / N-gram cosine similarity retrieval over past resolved incidents (e.g. 91% match with Incident #1282).
          </p>
        </div>

        {/* Pillar 4: Action Governance */}
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-subtle)', borderRadius: '10px', padding: '18px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <ShieldCheck size={18} color="#10b981" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#f8fafc' }}>4. Action Governance (3-Tier)</h3>
          </div>
          <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
            • <strong>Green (Observe):</strong> Automated telemetry & analysis.<br />
            • <strong>Yellow (Recommend):</strong> Operator advisory review.<br />
            • <strong>Red (Execute with Approval):</strong> Consequential actions require human approval with immutable audit IDs (e.g. <code>ACT-88291</code>).
          </p>
        </div>

      </div>

      {/* Prototype vs Production Comparison */}
      <div style={{ background: 'rgba(15, 20, 31, 0.9)', border: '1px solid var(--border-accent)', borderRadius: '10px', padding: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <GitBranch size={18} color="#38bdf8" />
          <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>
            Prototype vs. Production-Scale Architecture
          </h3>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '0.8rem' }}>
          <div style={{ background: 'rgba(0,0,0,0.3)', padding: '14px', borderRadius: '8px' }}>
            <div style={{ fontWeight: 700, color: '#38bdf8', marginBottom: '8px' }}>PROTOTYPE ARCHITECTURE (CURRENT)</div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '6px', color: 'var(--text-secondary)' }}>
              <li>• Python <code>asyncio.Queue</code> in-process stream ingestion</li>
              <li>• SQLite relational persistence with WAL mode</li>
              <li>• NetworkX in-memory relationship graph</li>
              <li>• In-memory vector cosine similarity index</li>
              <li>• Fast, zero-setup, fully reproducible 5-day build</li>
            </ul>
          </div>

          <div style={{ background: 'rgba(0,0,0,0.3)', padding: '14px', borderRadius: '8px' }}>
            <div style={{ fontWeight: 700, color: '#34d399', marginBottom: '8px' }}>PRODUCTION EVOLUTION (RAZORPAY SCALE)</div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '6px', color: 'var(--text-secondary)' }}>
              <li>• Apache Kafka / Flink distributed stream processing</li>
              <li>• Distributed PostgreSQL / DynamoDB + Redis feature store</li>
              <li>• Distributed Graph Database (e.g., Amazon Neptune / Neo4j)</li>
              <li>• Dedicated Vector Database (Qdrant / Milvus / Pinecone)</li>
              <li>• High availability, multi-region failover, and KMS auditing</li>
            </ul>
          </div>
        </div>
      </div>

    </div>
  );
}
