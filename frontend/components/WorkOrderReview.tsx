"use client";

import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { WorkOrderDetail } from "../lib/types";

const CATEGORIES = ["Plumbing", "Electrical", "HVAC", "Appliance", "Pest", "General", "Other"];
const PRIORITIES = ["Low", "Medium", "High", "Emergency"];

export default function WorkOrderReview({
  id,
  onChanged,
  onToast,
}: {
  id: string;
  onChanged: () => void;
  onToast: (m: string) => void;
}) {
  const [wo, setWo] = useState<WorkOrderDetail | null>(null);
  const [draft, setDraft] = useState<Partial<WorkOrderDetail>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setWo(null);
    api.get(id).then((d) => {
      setWo(d);
      setDraft(d);
    });
  }, [id]);

  if (!wo) return <div className="empty skeleton"><div className="icon">◆</div>Loading…</div>;

  const missing = new Set(wo.missing_fields || []);
  const set = (k: keyof WorkOrderDetail, v: unknown) => setDraft((p) => ({ ...p, [k]: v }));
  const conf = Math.round((wo.confidence || 0) * 100);

  const field = (
    k: keyof WorkOrderDetail,
    label: string,
    opts?: { wide?: boolean; textarea?: boolean; select?: string[] }
  ) => (
    <div className={`field ${opts?.wide ? "wide" : ""} ${missing.has(k as string) ? "missing" : ""}`}>
      <label>{label}{missing.has(k as string) ? <span className="flag">⚠ missing</span> : null}</label>
      {opts?.select ? (
        <select value={(draft[k] as string) || ""} onChange={(e) => set(k, e.target.value)}>
          <option value="">—</option>
          {opts.select.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : opts?.textarea ? (
        <textarea value={(draft[k] as string) || ""} onChange={(e) => set(k, e.target.value)} />
      ) : (
        <input value={(draft[k] as string) || ""} onChange={(e) => set(k, e.target.value)} />
      )}
    </div>
  );

  const save = async () => {
    setSaving(true);
    try {
      await api.update(id, {
        property_address: draft.property_address ?? null,
        unit: draft.unit ?? null,
        resident_name: draft.resident_name ?? null,
        issue: draft.issue ?? null,
        category: draft.category ?? null,
        priority: draft.priority ?? null,
        vendor: draft.vendor ?? null,
      } as never);
      onToast("Saved");
      onChanged();
    } finally {
      setSaving(false);
    }
  };

  const approve = async () => {
    await save();
    const r = await api.approve(id);
    onToast(r.message || "Approved → submitting to AppFolio");
    onChanged();
  };

  const ignore = async () => {
    await api.ignore(id);
    onToast("Ignored");
    onChanged();
  };

  const copyFields = async () => {
    const { text } = await api.copyText(id);
    await navigator.clipboard.writeText(text);
    onToast("Copied — paste into AppFolio");
  };

  return (
    <div>
      <div className="detail-head">
        <h2>
          {wo.is_emergency ? "🚨 " : ""}
          {draft.property_address || "Unknown property"}
          {draft.unit ? ` · Unit ${draft.unit}` : ""}
        </h2>
        <div className="meta">
          <span>{wo.from_email || "unknown sender"}</span>
          <span className="sep">•</span>
          <span>{wo.received_at ? new Date(wo.received_at).toLocaleString() : "—"}</span>
          <span className="sep">•</span>
          <span className="confidence">
            {conf}% confidence
            <span className="conf-bar"><span style={{ width: `${conf}%` }} /></span>
          </span>
          <span className="sep">•</span>
          <span className={`badge st-${wo.status}`}>{wo.status.replace("_", " ")}</span>
        </div>
      </div>

      <div className="panel-block">
        <div className="fields">
          {field("property_address", "Property address", { wide: true })}
          {field("unit", "Unit")}
          {field("resident_name", "Resident")}
          {field("category", "Category", { select: CATEGORIES })}
          {field("priority", "Priority", { select: PRIORITIES })}
          {field("vendor", "Vendor")}
          {field("issue", "Description", { wide: true, textarea: true })}
        </div>

        <div className="actions">
          <button className="btn primary" onClick={approve} disabled={saving}>
            ✓ Approve → AppFolio
          </button>
          <button className="btn" onClick={save} disabled={saving}>Save edits</button>
          <button className="btn ghost" onClick={copyFields}>⧉ Copy all fields</button>
          <button className="btn subtle" onClick={ignore}>Ignore</button>
        </div>
      </div>

      <div className="section-title">Original email</div>
      <div className="email-body">{wo.raw_body || "(empty)"}</div>

      {wo.attachments.length > 0 && (
        <>
          <div className="section-title">Attachments</div>
          <div className="attachments">
            {wo.attachments.map((a) => (
              <a key={a.id} href={a.signed_url || "#"} target="_blank" rel="noreferrer">
                {a.mime?.startsWith("image/") && a.signed_url ? (
                  <img src={a.signed_url} alt={a.filename || ""} />
                ) : (
                  <div className="att-file">📎 {a.filename}</div>
                )}
              </a>
            ))}
          </div>
        </>
      )}

      <div className="section-title">Activity</div>
      <div className="events">
        {wo.events.map((e) => (
          <div key={e.id} className="ev">
            <div><b>{e.event_type.replace("_", " ")}</b>{e.to_status ? ` → ${e.to_status.replace("_", " ")}` : ""} · {e.actor}</div>
            <div className="ev-time">{new Date(e.created_at).toLocaleString()}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
