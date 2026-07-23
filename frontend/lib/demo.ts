import type { WorkOrder, WorkOrderDetail } from "./types";

// Sample data used only when the backend is unreachable, so the dashboard is
// viewable during local UI development. Real data comes from the API.

const base = (o: Partial<WorkOrder>): WorkOrder => ({
  id: "",
  gmail_message_id: "",
  from_email: null,
  subject: null,
  received_at: null,
  raw_body: null,
  property_address: null,
  unit: null,
  resident_name: null,
  issue: null,
  category: null,
  priority: null,
  vendor: null,
  is_emergency: false,
  is_work_order: true,
  confidence: 0.9,
  missing_fields: [],
  status: "needs_review",
  appfolio_ref: null,
  created_at: "2026-07-23T14:00:00Z",
  ...o,
});

export const DEMO_ORDERS: WorkOrder[] = [
  base({
    id: "demo-1",
    from_email: "tenant.smith@gmail.com",
    subject: "Kitchen sink leaking — 245 Main St 2B",
    received_at: "2026-07-23T13:42:00Z",
    property_address: "245 Main Street",
    unit: "2B",
    resident_name: "John Smith",
    issue: "Kitchen sink is leaking underneath the cabinet; water pooling. Requests dispatch ASAP.",
    category: "Plumbing",
    priority: "High",
    vendor: "ABC Plumbing",
    confidence: 0.94,
    raw_body:
      "Hi, this is John in apartment 2B at 245 Main Street. The kitchen sink is leaking underneath — there's water pooling in the cabinet and it's getting worse. Can you please send someone ASAP? Thanks.",
  }),
  base({
    id: "demo-2",
    from_email: "maria.g@outlook.com",
    subject: "NO HEAT - unit freezing",
    received_at: "2026-07-23T12:10:00Z",
    property_address: "18 Oak Avenue",
    unit: "5",
    resident_name: "Maria Gonzalez",
    issue: "No heat, unit is freezing with an infant at home. Thermostat unresponsive.",
    category: "HVAC",
    priority: "Emergency",
    is_emergency: true,
    confidence: 0.97,
    raw_body:
      "The heat is completely out in unit 5 and it's freezing in here. I have a 6-month-old baby. The thermostat does nothing. Please help urgently.",
  }),
  base({
    id: "demo-3",
    from_email: "dwilliams@gmail.com",
    subject: "Garbage disposal jammed",
    received_at: "2026-07-23T09:25:00Z",
    property_address: "77 Cedar Court",
    unit: "1A",
    resident_name: "Dana Williams",
    issue: "Garbage disposal is jammed and humming but not spinning.",
    category: "Appliance",
    priority: "Medium",
    confidence: 0.72,
    missing_fields: ["priority"],
    raw_body: "Hey — the garbage disposal in 1A is jammed. It hums but won't spin. Not urgent. Thanks!",
  }),
  base({
    id: "demo-4",
    from_email: "leasing@partner.com",
    subject: "Bedroom outlet sparked",
    received_at: "2026-07-22T17:48:00Z",
    property_address: "412 Birch Lane",
    unit: "3C",
    resident_name: "Priya Patel",
    issue: "Outlet in the back bedroom sparked and is now dead; smells faintly of burning.",
    category: "Electrical",
    priority: "High",
    confidence: 0.88,
    status: "submitted",
    appfolio_ref: "WO-10482",
  }),
  base({
    id: "demo-5",
    from_email: "newsletter@supplies.com",
    subject: "Summer HVAC parts sale — 20% off",
    received_at: "2026-07-22T08:00:00Z",
    issue: "Marketing newsletter — not a work order.",
    category: null,
    priority: null,
    is_work_order: false,
    confidence: 0.05,
    status: "ignored",
  }),
];

export function demoDetail(id: string): WorkOrderDetail {
  const wo = DEMO_ORDERS.find((o) => o.id === id) || DEMO_ORDERS[0];
  return {
    ...wo,
    attachments:
      id === "demo-1"
        ? [{ id: "a1", filename: "leak_photo.jpg", mime: "image/jpeg", signed_url: null }]
        : [],
    events: [
      { id: "e1", event_type: "ingested", from_status: null, to_status: "needs_review", actor: "system", created_at: wo.received_at || wo.created_at },
      { id: "e2", event_type: "extracted", from_status: null, to_status: null, actor: "system", created_at: wo.received_at || wo.created_at },
    ],
  };
}
