import { describe, expect, it, vi } from "vitest";

import { loadSystemStatus } from "../src/status";

describe("loadSystemStatus", () => {
  it("reports both probes online for the documented API contract", async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      return new Response(JSON.stringify({ status: url.endsWith("/ready") ? "ready" : "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    const result = await loadSystemStatus("/api/", fetcher);

    expect(result.api.state).toBe("online");
    expect(result.database.state).toBe("online");
    expect(fetcher).toHaveBeenCalledWith("/api/health", expect.any(Object));
    expect(fetcher).toHaveBeenCalledWith("/api/ready", expect.any(Object));
  });

  it("keeps independent probe failures visible", async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/ready")) throw new TypeError("connection refused");
      return new Response(JSON.stringify({ status: "ok" }), { status: 200 });
    });

    const result = await loadSystemStatus("/api", fetcher);

    expect(result.api).toEqual({ state: "online", detail: "ok" });
    expect(result.database).toEqual({ state: "offline", detail: "Unreachable" });
  });

  it("rejects a successful HTTP response with the wrong schema", async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ healthy: true })));

    const result = await loadSystemStatus("/api", fetcher);

    expect(result.api.state).toBe("offline");
    expect(result.database.state).toBe("offline");
  });
});
