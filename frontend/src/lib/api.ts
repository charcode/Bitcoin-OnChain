import axios from "axios";
import type {
  PriceNow,
  NodeStatus,
  CurveResp,
  CandidatesInfo,
  HistogramResp,
  HeatmapResp,
  StencilPriceResp,
  DistributionResp,
  RecentArrivalsResp,
  EstimateHistoryResp,
  BlockTimelineResp,
} from "./types";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function getPriceNow(): Promise<PriceNow> {
  const r = await axios.get<PriceNow>(API + "/price/now", { timeout: 5000 });
  return r.data;
}

export async function getNodeStatus(): Promise<NodeStatus> {
  const r = await axios.get<NodeStatus>(API + "/node/status", { timeout: 5000 });
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

export async function getHistogram(params?: { grid?: number; span?: number }): Promise<HistogramResp> {
  const query = new URLSearchParams();
  if (params?.grid !== undefined) query.set("grid", String(params.grid));
  if (params?.span !== undefined) query.set("span", String(params.span));
  const suffix = query.toString();
  const url = API + "/debug/histogram" + (suffix ? "?" + suffix : "");
  const r = await axios.get<HistogramResp>(url, { timeout: 5000 });
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

export async function getRecentArrivals(params?: { window_sec?: number; limit?: number }): Promise<RecentArrivalsResp> {
  const query = new URLSearchParams();
  if (params?.window_sec !== undefined) query.set("window_sec", String(params.window_sec));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const suffix = query.toString();
  const url = API + "/debug/recent_arrivals" + (suffix ? "?" + suffix : "");
  const r = await axios.get<RecentArrivalsResp>(url, { timeout: 5000 });
  return r.data;
}

export async function getEstimateHistory(params?: { window_sec?: number; limit?: number }): Promise<EstimateHistoryResp> {
  const query = new URLSearchParams();
  if (params?.window_sec !== undefined) query.set("window_sec", String(params.window_sec));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const suffix = query.toString();
  const url = API + "/debug/estimate_history" + (suffix ? "?" + suffix : "");
  const r = await axios.get<EstimateHistoryResp>(url, { timeout: 5000 });
  return r.data;
}

export async function getBlockTimeline(params?: {
  block_count?: number;
  bin_count?: number;
  min_usd?: number;
  max_usd?: number;
  price_usd?: number;
}): Promise<BlockTimelineResp> {
  const query = new URLSearchParams();
  if (params?.block_count !== undefined) query.set("block_count", String(params.block_count));
  if (params?.bin_count !== undefined) query.set("bin_count", String(params.bin_count));
  if (params?.min_usd !== undefined) query.set("min_usd", String(params.min_usd));
  if (params?.max_usd !== undefined) query.set("max_usd", String(params.max_usd));
  if (params?.price_usd !== undefined) query.set("price_usd", String(params.price_usd));
  const suffix = query.toString();
  const url = API + "/debug/block_timeline" + (suffix ? "?" + suffix : "");
  const r = await axios.get<BlockTimelineResp>(url, { timeout: 10000 });
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
  scale?: "linear" | "sqrt" | "log";
}): Promise<DistributionResp> {
  const query = new URLSearchParams();
  if (params?.source) query.set("source", params.source);
  if (params?.bin_size !== undefined) query.set("bin_size", String(params.bin_size));
  if (params?.bins !== undefined) query.set("bins", String(params.bins));
  if (params?.block_lookback !== undefined) query.set("block_lookback", String(params.block_lookback));
  if (params?.weighted !== undefined) query.set("weighted", params.weighted ? "true" : "false");
  if (params?.scale !== undefined) query.set("scale", params.scale);
  const suffix = query.toString();
  const url = API + "/debug/distribution" + (suffix ? "?" + suffix : "");
  const r = await axios.get<DistributionResp>(url, { timeout: 10000 });
  return r.data;
}


