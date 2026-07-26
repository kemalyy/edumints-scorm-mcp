// k6 HTTP smoke — /health + temel erişilebilirlik.
// MCP build yolu yükü için tests/load/load_build.py kullanın (MCP JSON-RPC oturumu gerektirir).
//
//   k6 run -e BASE=https://mcp.edumints.com/scorm tests/load/k6_smoke.js
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE || "http://localhost:8000";

export const options = {
  vus: 20,
  duration: "30s",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<500"],
  },
};

export default function () {
  const res = http.get(`${BASE}/health`);
  check(res, {
    "status 200": (r) => r.status === 200,
    "ok body": (r) => r.body && r.body.includes("ok"),
  });
  sleep(1);
}
