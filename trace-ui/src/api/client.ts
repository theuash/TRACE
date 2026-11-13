import type { TraceApi } from "./contract";
import { HttpTraceApi } from "./http";

export function createTraceApi(): TraceApi {
  return new HttpTraceApi();
}
