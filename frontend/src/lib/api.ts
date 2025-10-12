import axios from "axios";
import type { PriceNow, CurveResp, CandidatesInfo, HeatmapResp, StencilPriceResp, DistributionResp } from "./types";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function getPriceNow(): Promise<PriceNow> {
  const r = await axios.get<PriceNow>(API + "/price/now", { timeout: 5000 });
  return r.data;
}

export async function getRnrCurve(): Promise<CurveResp> {
  const r = await axios.get<CurveResp>(API + "/rnr/curve", { timeout: 5000 });
  return r.data;
}

export async function getCandidates(): Promise<CandidatesInfo> {
  const r = await axios.get<CandidatesInfo>(API + "/debug/candidates", { timeout: 5000 });
  return r.data;
}

export async function getHeatmap(params?: { bucket?: number; buckets?: number }): Promise<HeatmapResp> {
  const query = new URLSearchParams();
  if (params?.bucket) query.set("bucket", String(params.bucket));
  if (params?.buckets) query.set("buckets", String(params.buckets));
  const suffix = query.toString();
  const url = API + "/debug/heatmap" + (suffix ? "?" + suffix : "");
  const r = await axios.get<HeatmapResp>(url, { timeout: 5000 });
  return r.data;
}
export async function getStencilPrice(params?: { start?: number; end?: number }): Promise<StencilPriceResp> {
  const query = new URLSearchParams();
  if (params?.start !== undefined) query.set("start", String(params.start));
  if (params?.end !== undefined) query.set("end", String(params.end));
  const suffix = query.toString();
  const url = API + "/debug/stencil_price" + (suffix ? "?" + suffix : "");
  const r = await axios.get<StencilPriceResp>(url, { timeout: 60000 });
  return r.data;
}
export async function getDistribution(params?: {
  source?: "mempool" | "blocks";
  bin_size?: number;
  bins?: number;
  block_lookback?: number;
  weighted?: boolean;
}): Promise<DistributionResp> {
  const query = new URLSearchParams();
  if (params?.source) query.set("source", params.source);
  if (params?.bin_size !== undefined) query.set("bin_size", String(params.bin_size));
  if (params?.bins !== undefined) query.set("bins", String(params.bins));
  if (params?.block_lookback !== undefined) query.set("block_lookback", String(params.block_lookback));
  if (params?.weighted !== undefined) query.set("weighted", params.weighted ? "true" : "false");
  const suffix = query.toString();
  const url = API + "/debug/distribution" + (suffix ? "?" + suffix : "");
  const r = await axios.get<DistributionResp>(url, { timeout: 10000 });
  return r.data;
}


