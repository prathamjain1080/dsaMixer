import { showTimePlanning } from "./features.js";
import { $, $$, esc, fmtDay, hm } from "./util.js";
import { api } from "./api.js";
import { SlideOver, Button, Badge, toast } from "./components/index.js";

export function openAIBalance(week, onApplied) {
  let preview = null, busy = false;
  const panel = SlideOver({ title: "Balance AI week", width: 640,
    sub: "Spread work from overloaded days through Sunday.",
    body: `<p>${showTimePlanning() ? "Set each day's AI quota in minutes. Unstarted AI cards on overloaded days can move, including rolled-over work. Days already within quota keep their cards." : "Preview how unstarted AI cards can move across the week using your saved planning settings."}</p>
      <p class="muted">Classes, started and completed cards stay in place. Past and closed days are locked. Future recurring work reserves space. Cards stay whole; limited capacity may leave an overload.</p>
      <div class="form-grid" ${showTimePlanning() ? "" : "hidden"}>${week.days.map(d => `<label class="field"><span class="f-label">${esc(fmtDay(d.date, { weekday: "short", day: "numeric", month: "short" }))}</span>
        <input type="number" min="0" max="1440" step="1" data-quota="${d.date}" value="${d.ai_capacity}" ${d.date < week.today || d.closed ? "disabled" : ""}>
        <span class="f-hint">${hm(d.minutes.ai)} on board</span></label>`).join("")}</div>
      <p class="muted" ${showTimePlanning() ? "" : "hidden"}>Saturday and Sunday are included. Give them a larger quota to make room around classes. Quotas apply to these dates only and are saved when you apply.</p>
      <div id="balanceResult" aria-live="polite"></div>`,
    footer: Button({ label: "Cancel", kind: "ghost", id: "balanceCancel" }) +
      Button({ label: "Preview balance", id: "balancePreview" }) +
      Button({ label: "Apply balance", kind: "primary", id: "balanceApply", attrs: { disabled: true } }),
  });
  const applyButton = $("#balanceApply", panel.el), previewButton = $("#balancePreview", panel.el);
  const inputs = $$("[data-quota]", panel.el);
  const clear = () => { preview = null; applyButton.disabled = true; $("#balanceResult", panel.el).innerHTML = ""; };
  inputs.forEach(input => input.addEventListener("input", clear));
  $("#balanceCancel", panel.el).onclick = panel.close;
  const setBusy = value => {
    busy = value;
    previewButton.disabled = value;
    applyButton.disabled = value || !preview;
    inputs.forEach(input => { input.readOnly = value; });
  };
  previewButton.onclick = async () => {
    if (busy || inputs.some(input => !input.checkValidity())) {
      inputs.find(input => !input.checkValidity())?.reportValidity();
      return;
    }
    clear();
    setBusy(true);
    try {
      const quotas = Object.fromEntries(inputs.map(input => [input.dataset.quota, Number(input.value)]));
      const result = await api(`/week/${week.start}/ai-balance/preview`, { method: "POST", body: { quotas } });
      preview = result;
      const remaining = result.days.filter(d => d.eligible && d.over);
      $("#balanceResult", panel.el).innerHTML = `<h3>${result.moves.length} card${result.moves.length === 1 ? "" : "s"} to move</h3>
        ${showTimePlanning() ? `<div class="table-wrap"><table class="table"><thead><tr><th>Day</th><th>Quota</th><th>Before</th><th>After</th></tr></thead><tbody>
        ${result.days.map(d => `<tr><td>${esc(fmtDay(d.date, { weekday: "short" }))}${d.eligible ? "" : " · locked"}</td><td>${hm(d.quota)}</td><td>${hm(d.before)}</td><td>${hm(d.after)} ${d.eligible && d.over ? Badge(`+${hm(d.over)}`, "warn") : ""}</td></tr>`).join("")}</tbody></table></div>` : ""}
        ${result.days.some(d => d.reserved) ? '<p class="muted">Before and after include recurring template work that will appear when future days are planned.</p>' : ""}
        ${remaining.length ? `<p role="status">${remaining.length} day(s) remain over quota. Increase quotas or move/split large cards manually.</p>` : '<p>All remaining days fit their quotas.</p>'}
        ${result.moves.length ? `<ul>${result.moves.map(m => `<li><strong>${esc(m.title)}</strong> · ${showTimePlanning() ? hm(m.minutes) : ""}${m.carried ? " · rolled over" : ""}<br>${esc(fmtDay(m.from))} → ${esc(fmtDay(m.to))}</li>`).join("")}</ul>` : '<p>No cards need moving, or only fixed work exceeds quota.</p>'}`;
    } catch { /* The API wrapper displays the error. */ }
    finally { setBusy(false); }
  };
  applyButton.onclick = async () => {
    if (busy || !preview) return;
    setBusy(true);
    try {
      const result = await api(`/week/${week.start}/ai-balance/apply`, {
        method: "POST", body: { quotas: preview.quotas, token: preview.token },
      });
      panel.close();
      toast(`AI week balanced · ${result.moves.length} cards moved`);
      await onApplied();
    } catch { clear(); }
    finally { setBusy(false); }
  };
}
