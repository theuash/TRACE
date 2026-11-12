import type { TraceApi } from "./contract";
import { HttpTraceApi } from "./http";
import { MockTraceApi } from "./mock/server";

export function createTraceApi(): TraceApi {
  const mode = (import.meta.env.VITE_API_MODE as "mock" | "http" | undefined) ?? "mock";
  if (mode === "http") {
    return new HttpTraceApi();
  }
  return new MockTraceApi();
}
