export type ProbeState = "online" | "offline";

export interface ProbeResult {
  state: ProbeState;
  detail: string;
}

export interface SystemStatus {
  api: ProbeResult;
  database: ProbeResult;
  observedAt: Date;
}

type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

async function probe(
  url: string,
  expectedStatus: string,
  fetcher: Fetcher,
): Promise<ProbeResult> {
  try {
    const response = await fetcher(url, {
      headers: { Accept: "application/json" },
      signal: AbortSignal.timeout(5_000),
    });
    const body: unknown = await response.json();
    const status =
      typeof body === "object" && body !== null && "status" in body
        ? (body as { status?: unknown }).status
        : undefined;
    if (!response.ok || status !== expectedStatus) {
      return { state: "offline", detail: `Unexpected response (${response.status})` };
    }
    return { state: "online", detail: expectedStatus };
  } catch {
    return { state: "offline", detail: "Unreachable" };
  }
}

export async function loadSystemStatus(
  baseUrl = "/api",
  fetcher: Fetcher = fetch,
): Promise<SystemStatus> {
  const normalizedBase = baseUrl.replace(/\/$/, "");
  const [api, database] = await Promise.all([
    probe(`${normalizedBase}/health`, "ok", fetcher),
    probe(`${normalizedBase}/ready`, "ready", fetcher),
  ]);
  return { api, database, observedAt: new Date() };
}
