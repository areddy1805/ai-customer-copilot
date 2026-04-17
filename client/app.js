function addMessage(text, type) {
  const chat = document.getElementById("chat");

  const empty = chat.querySelector(".empty");
  if (empty) empty.remove();

  const div = document.createElement("div");
  div.className = "msg " + type;
  div.innerHTML = text.replace(/\n/g, "<br>");

  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;

  return div;
}

async function send() {
  const input = document.getElementById("input");
  const btn = document.getElementById("sendBtn");
  const status = document.getElementById("statusText");

  const query = input.value.trim();
  if (!query) return;

  input.value = "";
  input.disabled = true;
  btn.disabled = true;

  addMessage(query, "user");

  const botDiv = addMessage("Thinking...", "bot");

  status.innerText = "Running...";
  botDiv.innerText = "";

  try {
    const res = await fetch("http://127.0.0.1:8000/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query,
        session_id: "ui",
        debug: true,
      }),
    });

    const data = await res.json();

    botDiv.innerText = data.response;

    const latency = data.metrics?.total_time_ms || 0;
    const route = data.route;
    const cache = data.metrics?.response_cache_hit;

    status.innerText = `Route: ${route} | ${latency.toFixed(2)}ms | Cache: ${cache}`;

    // ONLY populate debug — do NOT control visibility
    document.getElementById("traceBox").textContent = JSON.stringify(
      data.trace,
      null,
      2,
    );

    document.getElementById("metricsBox").textContent = JSON.stringify(
      data.metrics,
      null,
      2,
    );
  } catch {
    botDiv.innerText = "Error occurred";
    status.innerText = "Error";
  }

  input.disabled = false;
  btn.disabled = false;
  input.focus();
}

// -------- DEBUG TOGGLE (UI CONTROL ONLY) --------
const debugPanel = document.getElementById("debugPanel");
const handle = document.getElementById("debugHandle");

let isDragging = false;

handle.addEventListener("mousedown", (e) => {
  isDragging = true;
  document.body.style.cursor = "ns-resize";
});

document.addEventListener("mousemove", (e) => {
  if (!isDragging) return;

  const container = document.querySelector(".container");
  const rect = container.getBoundingClientRect();

  const newHeight = rect.bottom - e.clientY;

  if (newHeight > 100 && newHeight < window.innerHeight * 0.6) {
    debugPanel.style.height = newHeight + "px";
  }
});

document.addEventListener("mouseup", () => {
  isDragging = false;
  document.body.style.cursor = "default";
});

document.getElementById("debugToggle").addEventListener("change", function () {
  const panel = document.getElementById("debugPanel");
  panel.style.display = this.checked ? "block" : "none";
});

// -------- EXPAND TRACE / METRICS --------
function togglePanel(id) {
  const el = document.getElementById(id);
  el.style.display = el.style.display === "none" ? "block" : "none";
}

// -------- INPUT --------
document.getElementById("input").addEventListener("keypress", function (e) {
  if (e.key === "Enter") send();
});

window.onload = () => {
  document.getElementById("input").focus();
};
