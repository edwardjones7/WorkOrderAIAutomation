"use client";

import { useCallback, useEffect, useState } from "react";
import { api, backend } from "../lib/api";
import type { WorkOrder } from "../lib/types";
import WorkOrderReview from "../components/WorkOrderReview";

const FILTERS: { key: string; label: string; status?: string }[] = [
  { key: "review", label: "Needs review", status: "needs_review" },
  { key: "approved", label: "In progress", status: "approved,submitting" },
  { key: "submitted", label: "Submitted", status: "submitted" },
  { key: "failed", label: "Failed", status: "failed" },
  { key: "ignored", label: "Ignored", status: "ignored" },
  { key: "all", label: "All" },
];

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

export default function Page() {
  const [filter, setFilter] = useState("review");
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [selected, setSelected] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const [demo, setDemo] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    const status = FILTERS.find((f) => f.key === filter)?.status;
    const [rows, s] = await Promise.all([api.list(status), api.stats()]);
    setOrders(rows);
    setStats(s);
    setDemo(!backend.live);
    setLoading(false);
    if (rows.length && !rows.find((r) => r.id === selected)) setSelected(rows[0].id);
    if (!rows.length) setSelected(null);
  }, [filter, selected]);

  useEffect(() => { setLoading(true); load(); }, [filter]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, [load]);

  const showToast = (m: string) => {
    setToast(m);
    setTimeout(() => setToast(null), 2500);
  };

  const pollNow = async () => {
    setPolling(true);
    try {
      const { ingested } = await api.pollNow();
      showToast(ingested ? `${ingested} new work order(s)` : "No new emails");
      await load();
    } catch {
      showToast("Backend offline — showing demo data");
    } finally {
      setPolling(false);
    }
  };

  return (
    <>
      <div className="topbar">
        <div className="brand-lockup">
          <div className="logo-mark">◆</div>
          <h1>Work Order Inbox<span className="sub">Elenos AI</span></h1>
        </div>
        <div className="stat-pills">
          <span className="pill"><span className="dot dot-review" /> Needs review <b>{stats.needs_review || 0}</b></span>
          <span className="pill"><span className="dot dot-ok" /> Submitted <b>{stats.submitted || 0}</b></span>
          <span className="pill"><span className="dot dot-fail" /> Failed <b>{stats.failed || 0}</b></span>
          <button className="btn ghost" onClick={pollNow} disabled={polling}>
            {polling ? "Checking…" : "↻ Check email"}
          </button>
        </div>
      </div>

      {demo && (
        <div className="demo-banner">
          ● Demo data — backend not connected. Provision <code>backend/.env</code> + Supabase to go live.
        </div>
      )}

      <div className="layout">
        <div className="queue">
          <div className="filters">
            {FILTERS.map((f) => {
              const c = f.status
                ? f.status.split(",").reduce((n, st) => n + (stats[st] || 0), 0)
                : Object.values(stats).reduce((a, b) => a + b, 0);
              return (
                <button
                  key={f.key}
                  className={`chip ${filter === f.key ? "active" : ""}`}
                  onClick={() => setFilter(f.key)}
                >
                  {f.label}{c ? <span className="count">{c}</span> : null}
                </button>
              );
            })}
          </div>

          {loading ? (
            <div className="empty skeleton"><div className="icon">◆</div>Loading…</div>
          ) : orders.length === 0 ? (
            <div className="empty">
              <div className="icon">✓</div>
              <div className="title">All clear</div>
              <div className="hint">No work orders in this view.</div>
            </div>
          ) : (
            orders.map((o) => (
              <div
                key={o.id}
                className={`card ${selected === o.id ? "selected" : ""} ${o.is_emergency ? "emergency" : ""}`}
                onClick={() => setSelected(o.id)}
              >
                <div className="card-top">
                  <div className="addr">
                    {o.is_emergency ? "🚨 " : ""}
                    {o.property_address || o.subject || "Unknown property"}
                    {o.unit ? ` · ${o.unit}` : ""}
                  </div>
                  <div className="time">{timeAgo(o.received_at)}</div>
                </div>
                <div className="sub">{o.issue || "(no description)"}</div>
                <div className="row">
                  {o.priority && (
                    <span className={`badge pri-${o.priority.toLowerCase()}`}>
                      <span className="bdot" />{o.priority}
                    </span>
                  )}
                  {o.category && <span className="badge">{o.category}</span>}
                  <span className={`badge st-${o.status}`}>{o.status.replace("_", " ")}</span>
                  {o.missing_fields?.length > 0 && (
                    <span className="badge warn">⚠ {o.missing_fields.length} missing</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="detail">
          {selected ? (
            <WorkOrderReview id={selected} onChanged={load} onToast={showToast} />
          ) : (
            <div className="empty">
              <div className="icon">◆</div>
              <div className="title">Nothing selected</div>
              <div className="hint">Pick a work order from the queue to review it.</div>
            </div>
          )}
        </div>
      </div>

      {toast && <div className="toast">{toast}</div>}
    </>
  );
}
