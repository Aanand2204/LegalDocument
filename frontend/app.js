"use strict";

/* State */

const state = {
  user: null,
  contracts: [],
  contractsLoadedAt: 0,
};

/* API helper */

async function api(path, { method = "GET", body, isForm = false } = {}) {
  const headers = {};
  if (!isForm && body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      credentials: "same-origin",
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch (networkError) {
    setConnState(false);
    throw new Error("Could not reach the LegalGuard API. Is the server running?");
  }
  setConnState(true);

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      detail = formatErrorDetail(payload?.detail) ?? detail;
    } catch {
      /* body wasn't JSON */
    }
    const error = new Error(detail);
    error.status = response.status;
    throw error;
  }
  if (response.status === 204) return null;
  return response.json();
}

// FastAPI's detail is a string for a raised HTTPException but a list of
// {loc, msg} objects for a 422 validation error.
function formatErrorDetail(detail) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const field = Array.isArray(e?.loc) ? e.loc.at(-1) : null;
        return field && e?.msg ? `${field}: ${e.msg}` : e?.msg || JSON.stringify(e);
      })
      .join("; ");
  }
  return null;
}

function setConnState(online) {
  const el = document.getElementById("conn-indicator");
  if (!el) return;
  el.classList.toggle("offline", !online);
  el.querySelector(".conn-label").textContent = online ? "API online" : "API unreachable";
}

/* Toasts */

function toast(message, kind = "info") {
  const stack = document.getElementById("toast-stack");
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.innerHTML = `<span class="dot"></span><span>${escapeHtml(message)}</span>`;
  stack.appendChild(el);
  setTimeout(() => {
    el.style.opacity = "0";
    el.style.transition = "opacity 0.2s ease";
    setTimeout(() => el.remove(), 220);
  }, 4200);
}

/* Modal */

function openModal({ title, description, confirmLabel = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    const root = document.getElementById("modal-root");
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal" role="dialog" aria-modal="true">
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(description)}</p>
        <textarea placeholder="Reason (visible in the audit trail)"></textarea>
        <div class="modal-actions">
          <button class="btn btn-ghost" data-act="cancel">Cancel</button>
          <button class="btn ${danger ? "btn-danger" : "btn-good"}" data-act="ok">${escapeHtml(confirmLabel)}</button>
        </div>
      </div>`;
    root.appendChild(backdrop);

    const close = (result) => {
      backdrop.remove();
      resolve(result);
    };
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) close(null);
    });
    backdrop.querySelector('[data-act="cancel"]').addEventListener("click", () => close(null));
    backdrop.querySelector('[data-act="ok"]').addEventListener("click", () => {
      close({ reason: backdrop.querySelector("textarea").value.trim() });
    });
  });
}

/* Formatters */

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function daysUntil(iso) {
  const ms = new Date(iso).setHours(0, 0, 0, 0) - new Date().setHours(0, 0, 0, 0);
  return Math.round(ms / 86400000);
}

function levelSlug(level) {
  return String(level || "low").toLowerCase();
}

function badgeHtml(level, label) {
  const slug = levelSlug(level);
  return `<span class="badge badge-${slug}"><span class="dot"></span>${escapeHtml(label ?? level ?? "—")}</span>`;
}

function statusBadgeHtml(status) {
  const map = {
    uploaded: ["neutral", "Uploaded"],
    analyzing: ["accent", "Analyzing…"],
    analyzed: ["good", "Analyzed"],
    under_review: ["warning", "Needs review"],
    approved: ["good", "Approved"],
    rejected: ["critical", "Rejected"],
  };
  const [slug, label] = map[status] || ["neutral", status];
  return badgeHtml(slug, label);
}

/* Components */

function statTileHtml({ icon, tone = "", value, label }) {
  return `
    <div class="stat-tile">
      <div class="stat-icon ${tone}">${icon}</div>
      <div class="stat-body">
        <div class="stat-value">${value}</div>
        <div class="stat-label">${escapeHtml(label)}</div>
      </div>
    </div>`;
}

const ICONS = {
  contracts: '<svg viewBox="0 0 24 24"><path d="M6 2h9l5 5v15a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1zm8 1.5V8h4.5L14 3.5z"/></svg>',
  alert: '<svg viewBox="0 0 24 24"><path d="M12 2 1 21h22L12 2zm0 6 6.5 11h-13L12 8zm-.9 3.5v3.6h1.8v-3.6h-1.8zm0 4.6v1.7h1.8v-1.7h-1.8z"/></svg>',
  clock: '<svg viewBox="0 0 24 24"><path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm.75 5v5.4l4.2 2.5-.75 1.25L11 13V7h1.75z"/></svg>',
  calendar: '<svg viewBox="0 0 24 24"><path d="M7 2h2v2h6V2h2v2h3a1 1 0 0 1 1 1v3H2V5a1 1 0 0 1 1-1h3V2zM2 10h20v11a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V10z"/></svg>',
  check: '<svg viewBox="0 0 24 24"><path d="M9.5 16.2 5.3 12l-1.4 1.4 5.6 5.6L20.1 8.4l-1.4-1.4z"/></svg>',
  cross: '<svg viewBox="0 0 24 24"><path d="M18.3 5.7 12 12l6.3 6.3-1.4 1.4L10.6 13.4 4.3 19.7l-1.4-1.4L9.2 12 2.9 5.7l1.4-1.4 6.3 6.3 6.3-6.3z"/></svg>',
  upload: '<svg viewBox="0 0 24 24"><path d="M12 3l5 5h-3v6h-4V8H7l5-5zM5 19h14v2H5z"/></svg>',
  empty: '<svg viewBox="0 0 24 24"><path d="M4 4h16v16H4V4zm2 4v10h12V8H6z"/></svg>',
};

function gaugeHtml(score, level) {
  const colorVar = {
    LOW: "var(--status-good)",
    MEDIUM: "var(--status-warning)",
    HIGH: "var(--status-serious)",
    CRITICAL: "var(--status-critical)",
  }[level] || "var(--status-good)";
  return `
    <div class="gauge-wrap">
      <div class="gauge" style="--pct:${Math.max(0, Math.min(100, score))}; --gauge-color:${colorVar};">
        <div class="gauge-readout">
          <span class="n">${Math.round(score)}</span>
          <span class="u">/ 100</span>
        </div>
      </div>
      <div class="gauge-legend">
        <div class="row"><span class="swatch" style="background:var(--status-good)"></span>0–30 Low</div>
        <div class="row"><span class="swatch" style="background:var(--status-warning)"></span>31–60 Medium</div>
        <div class="row"><span class="swatch" style="background:var(--status-serious)"></span>61–80 High</div>
        <div class="row"><span class="swatch" style="background:var(--status-critical)"></span>81–100 Critical</div>
      </div>
    </div>`;
}

const CHEVRON_ICON = '<svg class="chevron" viewBox="0 0 24 24"><path d="M7 10l5 5 5-5z"/></svg>';

function evidenceDropdownHtml({ summary, hint, body }) {
  return `
    <details class="clause-item">
      <summary>
        <span class="risk-card-title">${escapeHtml(summary)}</span>
        ${hint ? `<span class="hint">${escapeHtml(hint)}</span>` : ""}
        ${CHEVRON_ICON}
      </summary>
      <p class="mono">${escapeHtml(body)}</p>
    </details>`;
}

function clauseItemHtml(clause) {
  return evidenceDropdownHtml({
    summary: clause.clause_type,
    hint: clause.page_number ? `Page ${clause.page_number}` : "",
    body: clause.clause_text,
  });
}

function riskCardHtml(risk, sourceClause) {
  const decided = Boolean(risk.human_decision);
  return `
    <div class="risk-card level-${levelSlug(risk.risk_level)}">
      <div class="risk-card-head">
        <span class="risk-card-title">${escapeHtml(risk.risk_type)}</span>
        ${badgeHtml(risk.risk_level)}
      </div>
      <div class="label">Reason</div>
      <p>${escapeHtml(risk.reason)}</p>
      ${
        sourceClause
          ? evidenceDropdownHtml({
              summary: "Read the source clause",
              hint: sourceClause.page_number ? `Page ${sourceClause.page_number}` : "",
              body: sourceClause.clause_text,
            })
          : ""
      }
      <div class="label">AI recommendation</div>
      <p>${escapeHtml(risk.recommendation)}</p>
      <div class="label">Confidence</div>
      <p class="mono">${Math.round(risk.confidence * 100)}%</p>
      ${
        decided
          ? `<div class="risk-decision">${risk.human_decision === "CONFIRMED" ? ICONS.check : ICONS.cross}
             ${risk.human_decision === "CONFIRMED" ? "Confirmed" : "Overridden"} by ${escapeHtml(risk.reviewed_by)}
             ${risk.human_reason ? ` — “${escapeHtml(risk.human_reason)}”` : ""}</div>`
          : `<div class="risk-card-actions">
               <button class="btn btn-sm btn-good" data-action="approve-risk" data-id="${risk.id}">Confirm risk</button>
               <button class="btn btn-sm btn-danger" data-action="reject-risk" data-id="${risk.id}">Override</button>
             </div>`
      }
    </div>`;
}

function checkItemHtml(item) {
  return `
    <div class="check-item">
      <span class="check-icon ${item.satisfied ? "pass" : "fail"}">${item.satisfied ? ICONS.check : ICONS.cross}</span>
      <span>${escapeHtml(item.requirement)}</span>
    </div>`;
}

function reviewDecisionHtml(contract) {
  const review = contract.latest_review;
  const decided = contract.status === "approved" || contract.status === "rejected";

  if (decided && review) {
    return `
      <div class="risk-decision">${contract.status === "approved" ? ICONS.check : ICONS.cross}
        ${contract.status === "approved" ? "Approved" : "Rejected"} by ${escapeHtml(review.lawyer_id)} on ${formatDateTime(review.reviewed_at)}
        ${review.comments ? ` — “${escapeHtml(review.comments)}”` : ""}</div>`;
  }

  return `
    ${
      review && review.decision === "request_changes"
        ? `<p class="hint" style="margin:0 0 10px;">Changes requested by ${escapeHtml(review.lawyer_id)} on ${formatDateTime(review.reviewed_at)}${review.comments ? ` — “${escapeHtml(review.comments)}”` : ""}</p>`
        : ""
    }
    <div style="display:flex; gap:8px; flex-wrap:wrap;">
      <button class="btn btn-good" data-action="review" data-decision="approved">Approve</button>
      <button class="btn btn-danger" data-action="review" data-decision="rejected">Reject</button>
      <button class="btn btn-ghost" data-action="review" data-decision="request_changes">Request changes</button>
    </div>`;
}

function deadlineItemHtml(d, { showContract = false } = {}) {
  const dt = new Date(d.deadline_date);
  const remaining = daysUntil(d.deadline_date);
  const urgency = remaining < 0 ? "critical" : remaining <= 7 ? "critical" : remaining <= 30 ? "warning" : remaining <= 90 ? "good" : "neutral";
  return `
    <div class="deadline-item">
      <div class="deadline-date">
        ${dt.toLocaleDateString(undefined, { day: "2-digit" })}
        <span>${dt.toLocaleDateString(undefined, { month: "short" })}</span>
      </div>
      <div class="deadline-body">
        <div class="deadline-type">${escapeHtml(d.deadline_type.replaceAll("_", " "))}</div>
        <div class="deadline-meta">
          ${showContract ? `${escapeHtml(d.contract_number ?? "")} · ` : ""}
          ${remaining < 0 ? "Passed" : `${remaining} day${remaining === 1 ? "" : "s"} remaining`}
          ${d.notice_period_days ? ` · ${d.notice_period_days}-day notice` : ""}
        </div>
      </div>
      ${badgeHtml(urgency === "neutral" ? "LOW" : urgency.toUpperCase(), remaining < 0 ? "Passed" : urgency === "critical" ? "Urgent" : urgency === "warning" ? "Soon" : "Upcoming")}
    </div>`;
}

function timelineItemHtml(entry) {
  const isGovernance = entry.kind === "governance";
  return `
    <div class="timeline-item ${isGovernance ? "governance" : ""}">
      <div class="timeline-time">${formatDateTime(entry.timestamp)}</div>
      <div class="timeline-title">${escapeHtml(entry.title)}</div>
      ${entry.detail ? `<div class="timeline-detail">${escapeHtml(entry.detail)}</div>` : ""}
    </div>`;
}

/* Views */

const view = () => document.getElementById("view");

async function ensureContracts(force = false) {
  if (!force && state.contracts.length && Date.now() - state.contractsLoadedAt < 15000) return state.contracts;
  state.contracts = await api("/contracts");
  state.contractsLoadedAt = Date.now();
  return state.contracts;
}

async function renderDashboard() {
  view().innerHTML = `<div class="spinner"></div>`;
  try {
    const [stats, contracts] = await Promise.all([api("/dashboard/statistics"), ensureContracts(true)]);
    const recent = contracts.slice(0, 6);

    view().innerHTML = `
      <div class="page-head">
        <div><h1>Dashboard</h1><p>Portfolio overview across every uploaded contract.</p></div>
        <a href="#/contracts" class="btn btn-primary">${ICONS.upload} Upload contract</a>
      </div>
      <div class="stat-grid">
        ${statTileHtml({ icon: ICONS.contracts, value: stats.total_contracts, label: "Contracts tracked" })}
        ${statTileHtml({ icon: ICONS.alert, tone: "crit", value: stats.high_risk_count, label: "High / critical risks" })}
        ${statTileHtml({ icon: ICONS.clock, tone: "warn", value: stats.pending_review_count, label: "Pending lawyer review" })}
        ${statTileHtml({ icon: ICONS.calendar, tone: "good", value: stats.upcoming_deadline_count, label: "Upcoming deadlines" })}
      </div>
      <div class="card">
        <div class="card-head"><h2>Recent contracts</h2><a class="hint" href="#/contracts">View all →</a></div>
        ${recent.length ? contractsTableHtml(recent) : emptyStateHtml("No contracts uploaded yet.")}
      </div>`;
    wireContractRows();
  } catch (err) {
    handleViewError(err);
  }
}

function contractsTableHtml(contracts) {
  return `
    <table class="table">
      <thead><tr><th>Contract</th><th>Type</th><th>Status</th><th>Uploaded</th></tr></thead>
      <tbody>
        ${contracts
          .map(
            (c) => `
          <tr data-id="${c.id}">
            <td><div class="cell-primary">${escapeHtml(c.filename)}</div><div class="mono">${c.contract_number}</div></td>
            <td class="cell-muted">${escapeHtml(c.contract_type || "Unclassified")}</td>
            <td>${statusBadgeHtml(c.status)}</td>
            <td class="cell-muted">${formatDate(c.created_at)}</td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>`;
}

function emptyStateHtml(message) {
  return `<div class="empty-state">${ICONS.empty}<div>${escapeHtml(message)}</div></div>`;
}

function errorStateHtml(err) {
  return `<div class="card"><div class="empty-state">${ICONS.alert}<div>${escapeHtml(err.message || String(err))}</div></div></div>`;
}

function handleViewError(err) {
  if (err.status === 401) {
    state.user = null;
    location.hash = "#/login";
    return;
  }
  view().innerHTML = errorStateHtml(err);
}

function wireContractRows() {
  view()
    .querySelectorAll("tbody tr[data-id]")
    .forEach((row) => row.addEventListener("click", () => (location.hash = `#/contracts/${row.dataset.id}`)));
}

async function renderContracts() {
  view().innerHTML = `<div class="spinner"></div>`;
  try {
    const contracts = await ensureContracts(true);
    view().innerHTML = `
      <div class="page-head">
        <div><h1>Contracts</h1><p>${contracts.length} contract${contracts.length === 1 ? "" : "s"} on file.</p></div>
      </div>
      <div class="card">
        <div class="card-head"><h2>Upload a new contract</h2></div>
        <label class="dropzone" id="dropzone">
          <div class="dropzone-icon">${ICONS.upload}</div>
          <div><strong>Drop a PDF or DOCX here</strong>, or click to browse</div>
          <input type="file" id="file-input" accept=".pdf,.docx" />
        </label>
      </div>
      <div class="card">
        <div class="card-head"><h2>All contracts</h2></div>
        ${contracts.length ? contractsTableHtml(contracts) : emptyStateHtml("No contracts uploaded yet.")}
      </div>`;
    wireContractRows();
    wireDropzone();
  } catch (err) {
    handleViewError(err);
  }
}

function wireDropzone() {
  const zone = document.getElementById("dropzone");
  const input = document.getElementById("file-input");
  if (!zone || !input) return;

  zone.addEventListener("click", (e) => {
    if (e.target !== input) input.click();
  });
  input.addEventListener("change", () => {
    if (input.files[0]) uploadFile(input.files[0]);
  });
  ["dragenter", "dragover"].forEach((evt) =>
    zone.addEventListener(evt, (e) => {
      e.preventDefault();
      zone.classList.add("drag");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    zone.addEventListener(evt, (e) => {
      e.preventDefault();
      zone.classList.remove("drag");
    })
  );
  zone.addEventListener("drop", (e) => {
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  });
}

async function uploadFile(file) {
  const form = new FormData();
  form.append("file", file);
  try {
    const contract = await api("/contracts/upload", { method: "POST", body: form, isForm: true });
    toast(`Uploaded ${contract.filename}`, "success");
    await ensureContracts(true);
    location.hash = `#/contracts/${contract.id}`;
  } catch (err) {
    toast(err.message, "error");
  }
}

async function renderContractDetail(id) {
  view().innerHTML = `<div class="spinner"></div>`;
  try {
    const contract = await api(`/contracts/${id}`);
    const [risks, clauses, deadlines] = await Promise.all([
      api(`/contracts/${id}/risks`),
      api(`/contracts/${id}/clauses`),
      api(`/contracts/${id}/deadlines`),
    ]);
    const analyzed = contract.status !== "uploaded";
    const compliance = analyzed ? await api(`/contracts/${id}/compliance`).catch(() => null) : null;

    const topScore = risks.length ? Math.max(...risks.map((r) => r.risk_score)) : 0;
    const topLevel = risks.length ? risks.reduce((a, b) => (b.risk_score > a.risk_score ? b : a)).risk_level : "LOW";
    const pendingReview = risks.some((r) => r.requires_human_review && !r.human_decision);
    const clauseById = new Map(clauses.map((c) => [c.id, c]));

    const keyDates = [
      contract.effective_date ? `Effective ${formatDate(contract.effective_date)}` : null,
      contract.expiry_date ? `Expires ${formatDate(contract.expiry_date)}` : null,
    ]
      .filter(Boolean)
      .join(" · ");

    view().innerHTML = `
      <div class="crumb"><a href="#/contracts">Contracts</a> / ${escapeHtml(contract.contract_number)}</div>
      <div class="page-head">
        <div>
          <h1>${escapeHtml(contract.filename)} ${pendingReview ? '<span class="pulse-dot" title="Needs review"></span>' : ""}</h1>
          <p>${escapeHtml(contract.contract_type || "Unclassified")} · ${(contract.parties || []).join(" & ") || "Parties unknown"}${keyDates ? ` · ${keyDates}` : ""}</p>
        </div>
        <div style="display:flex; gap:8px;">
          <a class="btn btn-ghost" href="#/contracts/${id}/audit">Audit trail</a>
          ${!analyzed ? `<button class="btn btn-primary" data-action="analyze">Run AI analysis</button>` : ""}
        </div>
      </div>

      <div class="grid-2">
        <div>
          <div class="card">
            <div class="card-head"><h2>Risk overview</h2>${statusBadgeHtml(contract.status)}</div>
            ${
              analyzed
                ? gaugeHtml(topScore, topLevel)
                : `<div class="empty-state">${ICONS.clock}<div>Not analyzed yet — run AI analysis to surface risks, deadlines, and compliance.</div></div>`
            }
          </div>

          <div class="card">
            <div class="card-head"><h2>Risk findings</h2><span class="hint">${risks.length} finding${risks.length === 1 ? "" : "s"}</span></div>
            ${
              risks.length
                ? `<div class="risk-list">${risks.map((r) => riskCardHtml(r, clauseById.get(r.clause_id))).join("")}</div>`
                : emptyStateHtml("No risks recorded yet.")
            }
          </div>

          <div class="card">
            <div class="card-head"><h2>Clauses</h2><span class="hint">${clauses.length} extracted</span></div>
            ${
              clauses.length
                ? `<div class="clause-list">${clauses.map(clauseItemHtml).join("")}</div>`
                : emptyStateHtml("No clauses extracted yet.")
            }
          </div>
        </div>

        <div>
          <div class="card">
            <div class="card-head"><h2>Compliance</h2>${compliance ? `<span class="check-score">${compliance.score}%</span>` : ""}</div>
            ${
              compliance
                ? `<div class="check-list">${compliance.results.map(checkItemHtml).join("")}</div>`
                : emptyStateHtml("Run AI analysis to check compliance.")
            }
          </div>

          <div class="card">
            <div class="card-head"><h2>Deadlines</h2></div>
            ${deadlines.length ? `<div class="deadline-list">${deadlines.map((d) => deadlineItemHtml(d)).join("")}</div>` : emptyStateHtml("No deadlines extracted yet.")}
          </div>

          <div class="card">
            <div class="card-head"><h2>Review decision</h2></div>
            <p style="font-size:13px;color:var(--text-secondary);margin:0 0 14px;">
              The AI recommends; this contract is only approved or rejected by a human review.
            </p>
            ${reviewDecisionHtml(contract)}
          </div>
        </div>
      </div>`;

    wireDetailActions(id);
  } catch (err) {
    handleViewError(err);
  }
}

function wireDetailActions(id) {
  const root = view();
  const analyzeBtn = root.querySelector('[data-action="analyze"]');
  if (analyzeBtn) {
    analyzeBtn.addEventListener("click", async () => {
      analyzeBtn.disabled = true;
      analyzeBtn.textContent = "Analyzing…";
      try {
        const result = await api(`/contracts/${id}/analyze`, { method: "POST" });
        toast(
          result.requires_human_review ? "Analysis complete — lawyer review required" : "Analysis complete — no review required",
          result.requires_human_review ? "info" : "success"
        );
        renderContractDetail(id);
      } catch (err) {
        toast(err.message, "error");
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = "Run AI analysis";
      }
    });
  }

  root.querySelectorAll('[data-action="approve-risk"], [data-action="reject-risk"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      const isReject = btn.dataset.action === "reject-risk";
      const outcome = await openModal({
        title: isReject ? "Override this risk finding" : "Confirm this risk finding",
        description: isReject
          ? "Record why this AI-flagged risk does not apply (e.g. covered by a master agreement)."
          : "Record that the AI's risk assessment stands as written.",
        confirmLabel: isReject ? "Override" : "Confirm",
        danger: isReject,
      });
      if (!outcome) return;
      try {
        await api(`/risks/${btn.dataset.id}/${isReject ? "reject" : "approve"}`, {
          method: "POST",
          body: { reason: outcome.reason || null },
        });
        toast("Decision recorded", "success");
        renderContractDetail(id);
      } catch (err) {
        toast(err.message, "error");
      }
    });
  });

  root.querySelectorAll('[data-action="review"]').forEach((btn) => {
    btn.addEventListener("click", async () => {
      const decision = btn.dataset.decision;
      const outcome = await openModal({
        title: decision === "approved" ? "Approve this contract" : decision === "rejected" ? "Reject this contract" : "Request changes",
        description: "This decision — and your reasoning — becomes part of the permanent audit trail.",
        confirmLabel: "Submit decision",
        danger: decision === "rejected",
      });
      if (!outcome) return;
      try {
        await api(`/contracts/${id}/review`, {
          method: "POST",
          body: { decision, comments: outcome.reason || null },
        });
        toast("Review recorded", "success");
        renderContractDetail(id);
      } catch (err) {
        toast(err.message, "error");
      }
    });
  });
}

async function renderDeadlines() {
  view().innerHTML = `<div class="spinner"></div>`;
  try {
    const contracts = await ensureContracts();
    const perContract = await Promise.all(
      contracts.map((c) =>
        api(`/contracts/${c.id}/deadlines`)
          .then((rows) => rows.map((d) => ({ ...d, contract_number: c.contract_number })))
          .catch(() => [])
      )
    );
    const all = perContract.flat().sort((a, b) => new Date(a.deadline_date) - new Date(b.deadline_date));

    view().innerHTML = `
      <div class="page-head">
        <div><h1>Deadlines</h1><p>Every renewal, expiry, and notice date across the portfolio.</p></div>
        <button class="btn btn-primary" id="run-check">${ICONS.calendar} Run deadline check</button>
      </div>
      <div class="card">
        ${all.length ? `<div class="deadline-list">${all.map((d) => deadlineItemHtml(d, { showContract: true })).join("")}</div>` : emptyStateHtml("No deadlines extracted yet — analyze a contract first.")}
      </div>`;

    document.getElementById("run-check").addEventListener("click", async (e) => {
      e.target.disabled = true;
      try {
        const alerts = await api("/deadlines/check", { method: "POST" });
        toast(alerts.length ? `${alerts.length} deadline alert${alerts.length === 1 ? "" : "s"} sent` : "No deadlines due — nothing to notify", "success");
      } catch (err) {
        toast(err.message, "error");
      } finally {
        e.target.disabled = false;
      }
    });
  } catch (err) {
    handleViewError(err);
  }
}

async function renderAudit(id) {
  view().innerHTML = `<div class="spinner"></div>`;
  try {
    const [contract, audit] = await Promise.all([api(`/contracts/${id}`), api(`/audit/${id}`)]);
    const entries = [
      ...audit.governance_events.map((e) => ({
        kind: e.event_type === "governance_decision" ? "governance" : "agent",
        timestamp: e.timestamp,
        title: e.event_type === "governance_decision" ? "Governance decision recorded" : `${(e.agent_name || "").replaceAll("_", " ")} ran`,
        detail: e.model_name ? `${e.model_name} ${e.model_version}` : null,
      })),
      ...audit.audit_logs.map((a) => ({
        kind: "user",
        timestamp: a.timestamp,
        title: `${a.action.replaceAll("_", " ")} — ${a.user}`,
        detail: a.details && a.details !== "null" ? a.details : null,
      })),
    ].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    view().innerHTML = `
      <div class="crumb"><a href="#/contracts">Contracts</a> / <a href="#/contracts/${id}">${escapeHtml(contract.contract_number)}</a> / Audit</div>
      <div class="page-head"><div><h1>Audit trail</h1><p>Every agent run and human decision, in order.</p></div></div>
      <div class="card">
        ${entries.length ? `<div class="timeline">${entries.map(timelineItemHtml).join("")}</div>` : emptyStateHtml("No audit events yet.")}
      </div>`;
  } catch (err) {
    handleViewError(err);
  }
}

/* Homepage */

function renderHome() {
  const loggedIn = Boolean(state.user);
  view().innerHTML = `
    <div class="home">
      <header class="home-nav">
        ${authBrandHtml()}
        <div class="home-nav-actions">
          ${
            loggedIn
              ? `<button class="btn btn-ghost" id="home-logout" type="button">Log out</button>
                 <a class="btn btn-primary" href="#/">Go to Dashboard</a>`
              : `<a class="btn btn-ghost" href="#/login">Sign in</a>
                 <a class="btn btn-primary" href="#/register">Get started</a>`
          }
        </div>
      </header>

      <section class="home-hero">
        <div>
          <span class="home-eyebrow">AI governance for contracts</span>
          <h1>AI reads every clause.<br />A <em>human</em> makes every call.</h1>
          <p class="lede">
            LegalGuard AI extracts clauses, scores risk 0–100, tracks renewal
            and notice deadlines, and checks policy compliance automatically
            — but no contract is ever approved or rejected without a
            lawyer's sign-off. Every AI step is logged to a permanent audit
            trail.
          </p>
          <div class="home-hero-actions">
            ${
              loggedIn
                ? `<a class="btn btn-primary" href="#/">Go to Dashboard</a>`
                : `<a class="btn btn-primary" href="#/register">Get started — it's free</a>
                   <a class="btn btn-ghost" href="#/login">Sign in</a>`
            }
          </div>
        </div>
        <div class="home-hero-visual">
          <div class="card-head"><h2>Sample risk finding</h2>${badgeHtml("CRITICAL")}</div>
          ${gaugeHtml(90, "CRITICAL")}
        </div>
      </section>

      <section class="home-features">
        ${[
          { icon: ICONS.contracts, title: "Clause extraction", text: "Every contract is parsed into typed clauses — liability, termination, confidentiality, governing law — with the source paragraph kept alongside each one." },
          { icon: ICONS.alert, title: "Risk scoring", text: "Each clause is scored 0–100 and leveled LOW to CRITICAL, with a plain-language reason and an AI recommendation — never just a number." },
          { icon: ICONS.calendar, title: "Deadline tracking", text: "Renewal, expiry, and notice-period dates are extracted automatically and flagged 90/30/7 days out, before they're missed." },
          { icon: ICONS.check, title: "Human-in-the-loop", text: "The AI can only recommend. Every approval, rejection, or override is a human decision, permanently recorded in the audit trail." },
        ]
          .map(
            (f) => `
          <div class="home-feature">
            <div class="stat-icon">${f.icon}</div>
            <h3>${f.title}</h3>
            <p>${f.text}</p>
          </div>`
          )
          .join("")}
      </section>

      <section class="home-flow">
        <h2>How it works</h2>
        <p>Three steps, every time — no exceptions.</p>
        <div class="home-steps">
          <div class="home-step">
            <div class="home-step-num">1</div>
            <h3>Upload a contract</h3>
            <p>Drop in a PDF or DOCX. It's parsed and hashed the moment it lands.</p>
          </div>
          <div class="home-step">
            <div class="home-step-num">2</div>
            <h3>AI analyzes it</h3>
            <p>Clauses, risks, deadlines, and compliance are checked in one governed pipeline.</p>
          </div>
          <div class="home-step">
            <div class="home-step-num">3</div>
            <h3>A lawyer decides</h3>
            <p>Approve, reject, or request changes — the only way a contract's status ever changes.</p>
          </div>
        </div>
      </section>

      <section class="home-cta">
        <h2>${loggedIn ? "Back to your contracts" : "See it on your own contracts"}</h2>
        <p>${loggedIn ? "Pick up right where you left off." : "Free to try — every account can upload, analyze, and review."}</p>
        ${
          loggedIn
            ? `<a class="btn btn-primary" href="#/">Go to Dashboard</a>`
            : `<a class="btn btn-primary" href="#/register">Get started — it's free</a>`
        }
      </section>
    </div>`;

  document.getElementById("home-logout")?.addEventListener("click", logout);
}

/* Auth views */

function authBrandHtml() {
  return `
    <div class="auth-brand">
      <span class="brand-mark" aria-hidden="true"></span>
      <span class="brand-name">LegalGuard<em>AI</em></span>
    </div>`;
}

function authCardHtml({ title, sub, passwordAttrs, submitLabel, switchText, switchLabel, switchHref }) {
  return `
    ${authBrandHtml()}
    <div class="auth-card">
      <h1>${title}</h1>
      <p class="sub">${sub}</p>
      <div id="auth-error"></div>
      <form id="auth-form">
        <div class="field"><label for="email">Email</label><input id="email" type="email" required autocomplete="email" /></div>
        <div class="field"><label for="password">Password</label><input id="password" type="password" required ${passwordAttrs} /></div>
        <button class="btn btn-primary auth-submit" type="submit">${submitLabel}</button>
      </form>
      <div class="auth-switch">${switchText} <a href="#${switchHref}">${switchLabel}</a></div>
    </div>`;
}

function renderLogin() {
  view().innerHTML = authCardHtml({
    title: "Welcome back",
    sub: "Sign in to review contracts and manage risk decisions.",
    passwordAttrs: 'autocomplete="current-password"',
    submitLabel: "Sign in",
    switchText: "New here?",
    switchLabel: "Create an account",
    switchHref: "/register",
  });
  wireAuthForm({ endpoint: "/auth/login", submitLabel: "Sign in", busyLabel: "Signing in…" });
}

function renderRegister() {
  view().innerHTML = authCardHtml({
    title: "Create an account",
    sub: "Every account can upload, analyze, and review contracts — there's nothing further to configure.",
    passwordAttrs: 'minlength="8" autocomplete="new-password"',
    submitLabel: "Create account",
    switchText: "Already have an account?",
    switchLabel: "Sign in",
    switchHref: "/login",
  });
  wireAuthForm({ endpoint: "/auth/register", submitLabel: "Create account", busyLabel: "Creating account…" });
}

function wireAuthForm({ endpoint, submitLabel, busyLabel }) {
  const form = document.getElementById("auth-form");
  const errorBox = document.getElementById("auth-error");
  const submitBtn = form.querySelector(".auth-submit");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errorBox.innerHTML = "";
    submitBtn.disabled = true;
    submitBtn.textContent = busyLabel;
    try {
      const body = {
        email: document.getElementById("email").value.trim(),
        password: document.getElementById("password").value,
      };
      const user = await api(endpoint, { method: "POST", body });
      state.user = user;
      location.hash = "#/";
      route();
    } catch (err) {
      errorBox.innerHTML = `<div class="auth-error">${ICONS.alert}${escapeHtml(err.message)}</div>`;
      submitBtn.disabled = false;
      submitBtn.textContent = submitLabel;
    }
  });
}

/* Router */

const NO_SESSION_REQUIRED = new Set(["/home", "/login", "/register"]);
const BOUNCE_IF_LOGGED_IN = new Set(["/login", "/register"]);

const ROUTES = [
  { pattern: /^\/home$/, render: renderHome, topLevel: null },
  { pattern: /^\/login$/, render: renderLogin, topLevel: null },
  { pattern: /^\/register$/, render: renderRegister, topLevel: null },
  { pattern: /^\/$/, render: renderDashboard, topLevel: "/" },
  { pattern: /^\/contracts$/, render: renderContracts, topLevel: "/contracts" },
  { pattern: /^\/contracts\/(\d+)\/audit$/, render: (m) => renderAudit(m[1]), topLevel: "/contracts" },
  { pattern: /^\/contracts\/(\d+)$/, render: (m) => renderContractDetail(m[1]), topLevel: "/contracts" },
  { pattern: /^\/deadlines$/, render: renderDeadlines, topLevel: "/deadlines" },
];

function currentPath() {
  return location.hash.replace(/^#/, "") || "/";
}

function route() {
  const path = currentPath();

  if (!state.user && !NO_SESSION_REQUIRED.has(path)) {
    location.hash = "#/home";
    return;
  }
  if (state.user && BOUNCE_IF_LOGGED_IN.has(path)) {
    location.hash = "#/";
    return;
  }

  document.body.classList.toggle("no-shell", NO_SESSION_REQUIRED.has(path));
  document.body.classList.toggle("auth-form-page", BOUNCE_IF_LOGGED_IN.has(path));
  renderUserChip();

  const match = ROUTES.find((r) => r.pattern.test(path));
  document.querySelectorAll(".nav-link").forEach((a) => a.classList.toggle("active", a.dataset.route === (match ? match.topLevel : "/")));
  if (!match) {
    view().innerHTML = errorStateHtml(new Error("Page not found"));
    return;
  }
  match.render(path.match(match.pattern));
}

/* Init */

function renderUserChip() {
  if (!state.user) return;
  document.getElementById("user-avatar").textContent = state.user.email.slice(0, 1);
  document.getElementById("user-email").textContent = state.user.email;
}

async function logout() {
  try {
    await api("/auth/logout", { method: "POST" });
  } catch {
    /* cookie may already be invalid */
  }
  state.user = null;
  location.hash = "#/home";
  route();
}

function initLogout() {
  document.getElementById("logout-btn").addEventListener("click", logout);
}

async function checkAuth() {
  try {
    state.user = await api("/auth/me");
  } catch {
    state.user = null;
  }
}

async function pingHealth() {
  try {
    await api("/health");
  } catch {
    /* setConnState already flipped by api() */
  }
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", async () => {
  initLogout();
  await checkAuth();
  route();
  pingHealth();
  setInterval(pingHealth, 30000);
});
