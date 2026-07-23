export type WorkOrderStatus =
  | "new"
  | "extracted"
  | "needs_review"
  | "approved"
  | "submitting"
  | "submitted"
  | "failed"
  | "ignored";

export interface WorkOrder {
  id: string;
  gmail_message_id: string;
  from_email: string | null;
  subject: string | null;
  received_at: string | null;
  raw_body: string | null;
  property_address: string | null;
  unit: string | null;
  resident_name: string | null;
  issue: string | null;
  category: string | null;
  priority: string | null;
  vendor: string | null;
  is_emergency: boolean;
  is_work_order: boolean | null;
  confidence: number | null;
  missing_fields: string[];
  status: WorkOrderStatus;
  appfolio_ref: string | null;
  created_at: string;
}

export interface Attachment {
  id: string;
  filename: string | null;
  mime: string | null;
  signed_url: string | null;
}

export interface WoEvent {
  id: string;
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  actor: string | null;
  created_at: string;
}

export interface WorkOrderDetail extends WorkOrder {
  attachments: Attachment[];
  events: WoEvent[];
}
