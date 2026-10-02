/**
 * ContextIQ Frontend Single-Page Application (SPA)
 */

let activeIncidentId = "INC-2026-0001";
let currentIncidentData = null;
let sseEventSource = null;
let leafletMap = null;

// Preset Demo Data Bundles
const DEMO_PRESETS = {
  A: {
    id: "INC-2026-0001",
    title: "Incident A — Zone B (Flash Flood)",
    zone: "Zone B",
    text: "Citizen Report 1 (14:15): Flood waters rising fast in Zone B, Market Road. 4 families trapped on rooftop near River Bridge!\nCitizen Report 2 (14:22): Main access road to Zone B completely submerged under 4ft water. Rescue boats required immediately.\nField Update (14:30): Power transformer submerged in Zone B. High risk of electrical hazards near trapped victims.",
    hasImage: true,
    hasPdf: true
  },
  B: {
    id: "INC-2026-0002",
    title: "Incident B — Zone C (Waterlogging)",
    zone: "Zone C",
    text: "Traffic Police Update (14:05): Heavy waterlogging near Zone C Bus Terminal. 2 vehicles stalled.\nCitizen Report (14:18): Drains overflowing on Commercial Street, Zone C. Water level 1 foot. No trapped individuals.",
    hasImage: true,
    hasPdf: false
  },
  C: {
    id: "INC-2026-0003",
    title: "Incident C — Zone A (Monsoon Watch)",
    zone: "Zone A",
    text: "Resident Report (13:50): Continuous rain in Zone A North Hills. Roads wet but clear. River level normal.",
    hasImage: false,
    hasPdf: false
  }
};

document.addEventListener("DOMContentLoaded", () => {
  lucide.createIcons();
  setupNavigation();
  setupDemoPresets();
  setupMap();
  loadDashboardData();
  
  // Auto load Incident A by default
  loadIncidentDetail(activeIncidentId);
});

/* Navigation Tab Switcher */
function setupNavigation() {
  const navBtns = document.querySelectorAll(".nav-btn");
  navBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      switchTab(tabId);
    });
  });
}

function switchTab(tabId) {
  document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));

  const targetBtn = document.getElementById(`nav-${tabId}`);
  const targetPane = document.getElementById(`tab-${tabId}`);
  if (targetBtn) targetBtn.classList.add("active");
  if (targetPane) targetPane.classList.add("active");

  if (tabId === "dashboard") {
    loadDashboardData();
  } else if (tabId === "history") {
    loadAuditHistory();
  } else if (tabId === "analytics") {
    loadAnalytics();
  }
}

/* Demo Preset Loaders */
function setupDemoPresets() {
  document.getElementById("btn-load-demo-a").addEventListener("click", () => applyDemoPreset("A"));
  document.getElementById("btn-load-demo-b").addEventListener("click", () => applyDemoPreset("B"));
  document.getElementById("btn-load-demo-c").addEventListener("click", () => applyDemoPreset("C"));

  document.getElementById("btn-analyze-incident").addEventListener("click", submitNewIncident);
  document.getElementById("btn-officer-approve").addEventListener("click", () => submitFeedback("approve"));
  document.getElementById("btn-officer-override").addEventListener("click", () => submitFeedback("override"));
}

function applyDemoPreset(key) {
  const p = DEMO_PRESETS[key];
  if (!p) return;
  activeIncidentId = p.id;
  document.getElementById("input-text-content").value = p.text;
  
  if (p.hasImage) {
    document.getElementById("preview-image-name").innerText = `${p.id}_photo.jpg attached`;
    document.getElementById("image-thumbnail-preview").innerHTML = `<img src="/data/uploads/${p.id}/photo.jpg" alt="Incident photo" style="max-height:100px; border-radius:6px; margin-top:8px;" />`;
    document.getElementById("image-thumbnail-preview").classList.remove("hidden");
  } else {
    document.getElementById("preview-image-name").innerText = "Click or drag image file here";
    document.getElementById("image-thumbnail-preview").classList.add("hidden");
  }

  if (p.hasPdf) {
    document.getElementById("pdf-badge-preview").classList.remove("hidden");
    document.getElementById("pdf-file-title").innerText = `${p.id}_advisory.pdf attached`;
  } else {
    document.getElementById("pdf-badge-preview").classList.add("hidden");
  }
}

function handleFileSelect(input, targetId) {
  if (input.files && input.files[0]) {
    document.getElementById(targetId).innerText = input.files[0].name;
  }
}

/* Map Setup */
function setupMap() {
  if (leafletMap) return;
  const container = document.getElementById("incident-map");
  if (!container) return;

  // Center on Udupi coastal emergency sector coordinates
  leafletMap = L.map("incident-map").setView([13.3409, 74.7421], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "© OpenStreetMap"
  }).addTo(leafletMap);

  // Add Zone Markers A, B, C, D
  const zones = [
    { name: "Zone B (Market Road)", lat: 13.348, lng: 74.745, priority: "CRITICAL", desc: "Flash flood & submerged power grid" },
    { name: "Zone C (Bus Terminal)", lat: 13.335, lng: 74.750, priority: "HIGH", desc: "1ft waterlogging & stalled vehicles" },
    { name: "Zone A (North Hills)", lat: 13.360, lng: 74.730, priority: "MEDIUM", desc: "Monsoon watch, road clear" },
    { name: "Zone D (East Highway)", lat: 13.320, lng: 74.765, priority: "LOW", desc: "Advisory monitoring" }
  ];

  zones.forEach(z => {
    const color = z.priority === "CRITICAL" ? "#f43f5e" : (z.priority === "HIGH" ? "#fb923c" : "#10b981");
    const circle = L.circle([z.lat, z.lng], {
      color: color,
      fillColor: color,
      fillOpacity: 0.35,
      radius: 600
    }).addTo(leafletMap);

    circle.bindPopup(`<b>${z.name}</b><br>Priority: <b>${z.priority}</b><br>${z.desc}`);
  });
}

/* Load Dashboard Data */
async function loadDashboardData() {
  try {
    const res = await fetch("/api/incidents");
    const data = await res.json();

    const tbody = document.getElementById("dash-incident-list");
    tbody.innerHTML = "";

    let criticalCount = 0;
    let reviewCount = 0;
    let confSum = 0;

    data.forEach(inc => {
      if (inc.priority === "CRITICAL") criticalCount++;
      if (inc.review_required) reviewCount++;
      if (inc.confidence) confSum += inc.confidence;

      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${inc.incident_id}</strong></td>
        <td><span class="meta-pill">${inc.zone}</span></td>
        <td><span class="badge-priority ${inc.priority}">${inc.priority}</span></td>
        <td><strong>${inc.confidence ? inc.confidence.toFixed(1) + '%' : 'N/A'}</strong></td>
        <td>${inc.review_required ? '<span class="text-amber">Review Required</span>' : inc.status}</td>
        <td><button class="btn-secondary-sm" onclick="viewIncidentDetail('${inc.incident_id}')">Inspect</button></td>
      `;
      tbody.appendChild(tr);
    });

    document.getElementById("dash-active-count").innerText = data.length;
    document.getElementById("dash-critical-count").innerText = criticalCount;
    document.getElementById("dash-review-count").innerText = reviewCount;
    if (data.length > 0 && confSum > 0) {
      document.getElementById("dash-avg-conf").innerText = (confSum / data.length).toFixed(1) + "%";
    }
  } catch (err) {
    console.error("Failed to load dashboard data:", err);
  }
}

function viewIncidentDetail(incId) {
  activeIncidentId = incId;
  loadIncidentDetail(incId);
  switchTab("intelligence");
}

/* Load Incident Detail view */
async function loadIncidentDetail(incId) {
  try {
    const res = await fetch(`/api/incidents/${incId}`);
    if (!res.ok) return;
    const data = await res.json();
    currentIncidentData = data;

    renderIncidentIntelligence(data);
  } catch (err) {
    console.error("Failed to fetch incident detail:", err);
  }
}

function renderIncidentIntelligence(data) {
  const inc = data.incident;
  const dec = data.latest_decision;

  document.getElementById("intel-incident-title").innerText = `Incident Intelligence — ${inc.incident_id}`;
  document.getElementById("intel-zone-pill").innerText = inc.zone;
  document.getElementById("intel-status-pill").innerText = inc.status;

  // Version selector
  const versionSelect = document.getElementById("intel-version-select");
  versionSelect.innerHTML = "";
  data.decisions.forEach((d, idx) => {
    const opt = document.createElement("option");
    opt.value = d.version;
    opt.innerText = `v${d.version} (${d.priority} - ${d.confidence}%)`;
    if (dec && d.version === dec.version) opt.selected = true;
    versionSelect.appendChild(opt);
  });

  // Column 1 Evidence
  const col1 = document.getElementById("col1-evidence-list");
  col1.innerHTML = "";
  data.inputs.forEach(inp => {
    const box = document.createElement("div");
    box.className = "evidence-item-box";
    box.style.cssText = "background:#090d16; padding:0.75rem; border-radius:8px; margin-bottom:0.75rem; border:1px solid var(--border-color); font-size:0.8rem;";
    
    if (inp.modality === "text") {
      box.innerHTML = `<strong><i data-lucide="file-text"></i> ${inp.filename}</strong><p style="color:var(--text-muted); margin-top:4px;">Recorded citizen report stream</p>`;
    } else if (inp.modality === "image") {
      box.innerHTML = `<strong><i data-lucide="image"></i> ${inp.filename}</strong><div style="margin-top:6px;"><img src="${inp.uri}" style="max-width:100%; border-radius:6px;" /></div>`;
    } else if (inp.modality === "pdf") {
      box.innerHTML = `<strong><i data-lucide="file-check"></i> ${inp.filename}</strong><p style="color:var(--text-muted); margin-top:4px;">Official DDMA advisory attached</p>`;
    }
    col1.appendChild(box);
  });

  // Column 2 Facts & Precedents
  const factBox = document.getElementById("fact-chips-box");
  factBox.innerHTML = "";
  document.getElementById("fact-count-num").innerText = data.facts.length;
  data.facts.forEach(f => {
    const chip = document.createElement("div");
    chip.className = "fact-chip";
    chip.innerHTML = `
      <i data-lucide="tag" class="fact-modality-icon"></i>
      <span><strong>[${f.zone}]</strong> ${f.claim}</span>
    `;
    factBox.appendChild(chip);
  });

  const caseBox = document.getElementById("cases-list-box");
  caseBox.innerHTML = "";
  data.past_cases.forEach(c => {
    const item = document.createElement("div");
    item.style.cssText = "background:#090d16; padding:0.6rem; border-radius:6px; margin-bottom:0.5rem; font-size:0.75rem; border:1px solid var(--border-color);";
    item.innerHTML = `
      <div style="display:flex; justify-content:space-between; font-weight:600; color:var(--accent-cyan);">
        <span>${c.case_id} — ${c.zone}</span>
        <span>Sim: ${(c.similarity_score * 100).toFixed(0)}%</span>
      </div>
      <p style="margin-top:2px; color:var(--text-muted);">${c.summary}</p>
    `;
    caseBox.appendChild(item);
  });

  // Column 3 Decision
  if (dec) {
    document.getElementById("decision-priority-val").innerText = dec.priority;
    document.getElementById("decision-priority-val").className = `priority-value ${dec.priority}`;
    document.getElementById("decision-action-text").innerText = dec.recommended_action;

    // Confidence Ring
    document.getElementById("conf-ring-val").innerText = `${dec.confidence.toFixed(1)}%`;
    const offset = 251.2 - (251.2 * (dec.confidence / 100));
    document.getElementById("conf-ring-circle").style.strokeDashoffset = offset;

    const cb = dec.confidence_breakdown;
    document.getElementById("cb-completeness").innerText = `${cb.completeness}%`;
    document.getElementById("cb-agreement").innerText = `${cb.agreement}%`;
    document.getElementById("cb-retrieval").innerText = `${cb.retrieval_relevance}%`;
    document.getElementById("cb-evidence").innerText = `${cb.evidence_coverage}%`;

    // Human Review Banner
    const hrBanner = document.getElementById("human-review-banner");
    if (dec.review_required) {
      hrBanner.classList.remove("hidden");
      document.getElementById("review-reason-text").innerText = dec.review_reason || "Confidence below threshold (70%)";
    } else {
      hrBanner.classList.add("hidden");
    }

    // Reasons with Citations
    const reasonBox = document.getElementById("reasons-list-box");
    reasonBox.innerHTML = "";
    dec.reasons.forEach(r => {
      const li = document.createElement("li");
      let citations = "";
      if (r.fact_ids) r.fact_ids.forEach(fid => citations += `<span class="citation-tag">${fid}</span>`);
      if (r.case_ids) r.case_ids.forEach(cid => citations += `<span class="citation-tag">${cid}</span>`);
      li.innerHTML = `${r.text} ${citations}`;
      reasonBox.appendChild(li);
    });

    // Trace summary
    document.getElementById("trace-summary-text").innerText = `Decision synthesized by combining citizen report, image evidence, and advisory with historical precedents for ${inc.zone}.`;
  }

  // Update Stepper backend badges
  if (dec && dec.backends) {
    document.getElementById("backend-ingest").innerText = dec.backends.storage || "fs";
    document.getElementById("backend-understanding").innerText = dec.backends.llm || "gemini-3-flash";
    document.getElementById("backend-retrieval").innerText = dec.backends.retriever || "numpy_cosine";
    document.getElementById("backend-decision").innerText = dec.backends.llm || "gemini-3-flash";
    document.getElementById("backend-validation").innerText = "verifier";
  }

  lucide.createIcons();
}

/* Submit New Incident & Start SSE Stream */
async function submitNewIncident() {
  const textContent = document.getElementById("input-text-content").value;
  const imageInput = document.getElementById("input-image-file");
  const pdfInput = document.getElementById("input-pdf-file");

  if (!textContent && !imageInput.files[0] && !pdfInput.files[0]) {
    alert("Please enter text report or attach an image/PDF file.");
    return;
  }

  // Create incident if new
  const incRes = await fetch("/api/incidents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: `Multimodal Incident ${Date.now()}` })
  });
  const newInc = await incRes.json();
  activeIncidentId = newInc.incident_id;

  // Upload inputs
  if (textContent) {
    const formData = new FormData();
    formData.append("modality", "text");
    formData.append("text_content", textContent);
    await fetch(`/api/incidents/${activeIncidentId}/inputs`, { method: "POST", body: formData });
  }

  if (imageInput.files[0]) {
    const formData = new FormData();
    formData.append("modality", "image");
    formData.append("file", imageInput.files[0]);
    await fetch(`/api/incidents/${activeIncidentId}/inputs`, { method: "POST", body: formData });
  }

  if (pdfInput.files[0]) {
    const formData = new FormData();
    formData.append("modality", "pdf");
    formData.append("file", pdfInput.files[0]);
    await fetch(`/api/incidents/${activeIncidentId}/inputs`, { method: "POST", body: formData });
  }

  switchTab("intelligence");
  connectSSEStream(activeIncidentId);
}

/* Real-Time SSE Event Source Handler */
function connectSSEStream(incId) {
  if (sseEventSource) sseEventSource.close();

  // Reset stepper icons
  document.querySelectorAll(".step-item").forEach(s => s.classList.remove("active", "done"));

  sseEventSource = new EventSource(`/api/incidents/${incId}/stream`);

  sseEventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === "ping") return;

    const stage = data.stage;
    const status = data.status;
    const ms = data.ms;

    if (stage === "Ingesting") {
      updateStepUI("step-ingest", "ms-ingest", status, ms);
    } else if (stage === "Understanding") {
      updateStepUI("step-understanding", "ms-understanding", status, ms);
      if (data.payload && data.payload.new_fact) {
        appendFactChip(data.payload.new_fact);
      }
    } else if (stage === "Retrieving Context") {
      updateStepUI("step-retrieval", "ms-retrieval", status, ms);
    } else if (stage === "Generating Decision") {
      updateStepUI("step-decision", "ms-decision", status, ms);
    } else if (stage === "Validating Evidence") {
      updateStepUI("step-validation", "ms-validation", status, ms);
      if (status === "done") {
        // Stream completed
        sseEventSource.close();
        loadIncidentDetail(incId);
      }
    }
  };
}

function updateStepUI(stepId, msId, status, ms) {
  const stepEl = document.getElementById(stepId);
  const msEl = document.getElementById(msId);
  if (!stepEl) return;

  if (status === "start" || status === "progress") {
    stepEl.classList.add("active");
  } else if (status === "done") {
    stepEl.classList.remove("active");
    stepEl.classList.add("done");
    if (msEl) msEl.innerText = `${ms} ms`;
  }
}

function appendFactChip(f) {
  const box = document.getElementById("fact-chips-box");
  const chip = document.createElement("div");
  chip.className = "fact-chip";
  chip.innerHTML = `<i data-lucide="tag" class="fact-modality-icon"></i> <span><strong>[${f.zone}]</strong> ${f.claim}</span>`;
  box.appendChild(chip);
  lucide.createIcons();
}

/* Submit Officer Feedback (Approve/Override) */
async function submitFeedback(action) {
  if (!currentIncidentData || !currentIncidentData.latest_decision) return;
  const decId = currentIncidentData.latest_decision.decision_id;

  const reason = prompt(`Enter officer review note for ${action.toUpperCase()}:`, `Officer ${action} after evidence audit.`);
  if (reason === null) return;

  let newPriority = null;
  if (action === "override") {
    newPriority = prompt("Enter override priority (CRITICAL, HIGH, MEDIUM, LOW):", "HIGH");
  }

  await fetch(`/api/incidents/${activeIncidentId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision_id: decId,
      officer_action: action,
      reason: reason,
      new_priority: newPriority
    })
  });

  alert(`Officer action '${action}' recorded.`);
  loadIncidentDetail(activeIncidentId);
}

/* Load Audit History */
async function loadAuditHistory() {
  const res = await fetch(`/api/incidents/${activeIncidentId}`);
  if (!res.ok) return;
  const data = await res.json();

  const tbody = document.getElementById("audit-log-list");
  tbody.innerHTML = "";

  data.audit_events.forEach(a => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${new Date(a.ts).toLocaleTimeString()}</td>
      <td><strong>${a.incident_id}</strong></td>
      <td><span class="meta-pill">${a.stage}</span></td>
      <td><code>${a.backend}</code></td>
      <td>${a.detail}</td>
    `;
    tbody.appendChild(tr);
  });
}

/* Load Analytics */
async function loadAnalytics() {
  const res = await fetch("/api/analytics");
  const data = await res.json();
  console.log("Analytics telemetry:", data);
}
