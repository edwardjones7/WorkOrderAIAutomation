from pydantic import BaseModel


# Fields a human can edit in the dashboard before approving.
class WorkOrderUpdate(BaseModel):
    property_address: str | None = None
    unit: str | None = None
    resident_name: str | None = None
    issue: str | None = None
    category: str | None = None
    priority: str | None = None
    vendor: str | None = None
    is_emergency: bool | None = None


# Valid lifecycle states.
STATUSES = [
    "new",
    "extracted",
    "needs_review",
    "approved",
    "submitting",
    "submitted",
    "failed",
    "ignored",
]
