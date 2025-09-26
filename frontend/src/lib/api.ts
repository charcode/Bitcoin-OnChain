import axios from "axios";
import type { PriceNow, CurveResp, CandidatesInfo } from "./types";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

export async function getPriceNow(): Promise<PriceNow> {
  const r = await axios.get<PriceNow>(`${API}/price/now`, { timeout: 5000 });
  return r.data;
}

export async function getRnrCurve(): Promise<CurveResp> {
  const r = await axios.get<CurveResp>(`${API}/rnr/curve`, { timeout: 5000 });
  return r.data;
}

export async function getCandidates(): Promise<CandidatesInfo> {
  const r = await axios.get<CandidatesInfo>(`${API}/debug/candidates`, { timeout: 5000 });
  return r.data;
}
