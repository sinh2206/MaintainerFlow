import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const config = readFileSync(new URL("../nginx.conf", import.meta.url), "utf8");

describe("production proxy boundary", () => {
  it("allowlists only read-only backend resources", () => {
    expect(config).toContain("location = /api/health");
    expect(config).toContain("location = /api/ready");
    expect(config).toContain("location = /api/openapi.json");
    expect(config).toMatch(/location \/api\/ \{\s+return 404;/);
    expect(config).not.toContain("proxy_pass http://api:8000/;");
  });
});
