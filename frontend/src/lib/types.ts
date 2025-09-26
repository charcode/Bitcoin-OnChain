export type PriceNow = {
  t: number;
  price: number;
  confidence: number;
  curvature: number;
  samples_used: number;
};

export type CurvePoint = { p: number; s: number };
export type CurveResp = { t: number; points: CurvePoint[] };

export type CandidatesInfo = {
  total_outputs_cached: number;
  usable: number;
};
