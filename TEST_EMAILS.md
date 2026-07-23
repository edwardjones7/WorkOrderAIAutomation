# Test Emails

Send these **to `edwardjonescontact@gmail.com`** (from any account) to exercise the
pipeline. Each is copy-paste ready. The **Expected** line is what a correct extraction
should produce — use it to grade accuracy (great for a proposal: "9/10 fields correct
across 10 real-world samples").

> The poller only picks up emails with work-order-ish wording, sent in the last 2 days.
> Non-work-orders (8–10) should land in **Ignored**, not Needs review.

---

## 1 — Clean work order
**Subject:** Maintenance Request – 245 Main St Apt 2B
**Body:**
> Tenant John Smith in unit 2B at 245 Main Street reports the kitchen sink is leaking underneath the cabinet. Water is pooling. Please dispatch ASAP.

**Expected:** property `245 Main Street` · unit `2B` · resident `John Smith` · category `Plumbing` · priority `High` · is_work_order ✓

---

## 2 — Emergency, no heat
**Subject:** NO HEAT unit 5 – freezing
**Body:**
> The heat is out in unit 5 at 18 Oak Avenue and it's freezing in here. I have a 6-month-old baby. The thermostat is completely dead. Please help urgently.

**Expected:** property `18 Oak Avenue` · unit `5` · category `HVAC` · priority `Emergency` · is_emergency ✓

---

## 3 — Emergency, water/flood
**Subject:** URGENT – water everywhere 3C
**Body:**
> Pipe burst under the bathroom sink in apartment 3C at 412 Birch Lane. Water is flooding the floor and going into the hallway. Need someone right now.

**Expected:** property `412 Birch Lane` · unit `3C` · category `Plumbing` · priority `Emergency` · is_emergency ✓

---

## 4 — Informal / missing fields
**Subject:** disposal broken
**Body:**
> hey the garbage disposal is jammed again in 1A. hums but won't spin. not urgent, whenever you get a chance. thanks

**Expected:** unit `1A` · category `Appliance` · priority `Low` · property `null` (missing → flagged) · is_work_order ✓

---

## 5 — Vendor named + due date
**Subject:** Work Order – dishwasher leak, 77 Cedar Ct #4
**Body:**
> Please create a work order for 77 Cedar Court, unit 4. Dishwasher is leaking onto the kitchen floor. Assign to ABC Appliance Repair. Resident: Maria Gonzalez. Would like this done by Friday.

**Expected:** property `77 Cedar Court` · unit `4` · resident `Maria Gonzalez` · vendor `ABC Appliance Repair` · category `Appliance` · priority `Medium`

---

## 6 — Electrical, safety wording
**Subject:** Outlet sparked in bedroom
**Body:**
> The outlet in the back bedroom at 88 Elm Street apt 12 sparked and is now dead. There's a faint burning smell. Tenant is worried.

**Expected:** property `88 Elm Street` · unit `12` · category `Electrical` · priority `High` (or Emergency) · is_emergency ✓

---

## 7 — Forwarded tenant complaint (extra noise)
**Subject:** Fwd: complaint from tenant
**Body:**
> ---------- Forwarded message ----------
> From: tenant.lee@email.com
> Hi, the bathroom fan in unit 9 at 100 Park Ave has been making a loud grinding noise for a week and now doesn't turn on at all. Can someone look at it?

**Expected:** property `100 Park Avenue` · unit `9` · category `HVAC`/`General` · priority `Medium` · is_work_order ✓

---

## 8 — NOT a work order (newsletter)
**Subject:** ☀️ Summer HVAC parts sale — 20% off all filters
**Body:**
> Beat the heat! This month only, save 20% on all HVAC filters and parts. Shop now before the sale ends. Unsubscribe anytime.

**Expected:** is_work_order ✗ → **Ignored**

---

## 9 — NOT a work order (rent question)
**Subject:** Question about my rent payment
**Body:**
> Hi, I wanted to check whether my August rent payment went through — the portal is showing a pending status. Can you confirm? Thanks, Dana.

**Expected:** is_work_order ✗ → **Ignored** (it's a billing question, not maintenance)

---

## 10 — NOT a work order (personal note)
**Subject:** lunch thursday?
**Body:**
> Hey are we still on for lunch Thursday? Let me know what time works.

**Expected:** is_work_order ✗ → **Ignored**

---

### After sending
Tell me "sent" (or click **Check email** in the dashboard). We'll confirm 1–7 land in
**Needs review** with correct fields, and 8–10 land in **Ignored**. Tally the correct
fields for your accuracy number.
