import "./styles.css";
import { loadSystemStatus, type ProbeResult } from "./status";

function required<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) throw new Error(`Missing UI element: ${selector}`);
  return element;
}

function renderProbe(service: "api" | "database", result: ProbeResult): void {
  const card = required<HTMLElement>(`[data-service="${service}"]`);
  card.dataset.state = result.state;
  required<HTMLElement>(`[data-service="${service}"] .status-value`).textContent =
    result.state === "online" ? "Operational" : "Unavailable";
  card.title = result.detail;
}

async function refresh(): Promise<void> {
  const button = required<HTMLButtonElement>("#refresh");
  button.disabled = true;
  button.textContent = "Checking…";
  const status = await loadSystemStatus(import.meta.env.VITE_API_BASE_URL || "/api");
  renderProbe("api", status.api);
  renderProbe("database", status.database);
  const online = [status.api, status.database].filter((item) => item.state === "online").length;
  required<HTMLElement>("#observed-at").textContent =
    `Last checked ${new Intl.DateTimeFormat(undefined, { timeStyle: "medium" }).format(status.observedAt)}`;
  required<HTMLElement>("#status-announcement").textContent =
    `${online} of 2 deployment probes are operational.`;
  button.disabled = false;
  button.textContent = "Refresh status";
}

required<HTMLButtonElement>("#refresh").addEventListener("click", () => void refresh());
void refresh();
