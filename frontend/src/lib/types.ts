export type PriceNow = {
  t: number;
  price: number | null;
  confidence: number;
  curvature: number;
  samples_used: number;
};

export type NodeStatus = {
  t: number;
  status: "ok" | "not_ready" | "missing";
  connected: boolean;
  message: string;
  chain?: string | null;
  blocks?: number | null;
  headers?: number | null;
  initialblockdownload?: boolean | null;
  mempool_size?: number | null;
};

export type CurvePoint = { p: number; s: number };
export type CurveResp = { t: number; points: CurvePoint[] };

export type CandidatesInfo = {
  total_outputs_cached: number;
  usable: number;
};

export type HistogramBin = {
  price: number;
  count: number;
  weight_sum: number;
};

export type HistogramResp = {
  t: number;
  grid: number;
  span: number;
  window: number;
  used_price: number;
  bins: HistogramBin[];
  total_samples: number;
};

export type HeatmapBucket = {
  start: number;
  end: number;
  counts: number[];
};

export type HeatmapResp = {
  t: number;
  bucket_seconds: number;
  bin_edges: number[];
  buckets: HeatmapBucket[];
  max_count: number;
  total_samples: number;
  overflow: boolean;
};

export type MempoolArrival = {
  ts: number;
  age_sec: number;
  value_btc: number;
  value_usd: number;
  weight: number;
  txid?: string | null;
  vout_n?: number | null;
  address_out?: string | null;
};

export type RecentArrivalsResp = {
  t: number;
  current_price: number;
  window_sec: number;
  total_samples: number;
  arrivals: MempoolArrival[];
};

export type EstimateHistoryPoint = {
  t: number;
  raw_price: number;
  ema_price: number;
  confidence: number;
  curvature: number;
  samples_used: number;
};

export type EstimateHistoryResp = {
  t: number;
  window_sec: number;
  points: EstimateHistoryPoint[];
};

export type BlockTimelineSlice = {
  height: number;
  time: number;
  counts: number[];
  total_outputs: number;
};

export type BlockTimelineResp = {
  t: number;
  current_price: number;
  current_block_age_sec: number;
  tip_height: number;
  last_block_time: number;
  bin_edges_usd: number[];
  blocks: BlockTimelineSlice[];
  max_count: number;
};
export type RoundUsdStat = {
  usd_amount: number;
  bins: number[];
  btc_amount: number;
  sats: number;
  normalized_weight: number;
  raw_weight: number;
  implied_price: number;
};

export type StencilPriceResp = {
  start_height: number;
  end_height: number;
  block_count: number;
  tip_height: number;
  samples_used: number;
  estimated_price: number;
  best_slide: number;
  best_slide_score: number;
  neighbor_slide: number;
  neighbor_score: number;
  average_slide_score: number;
  slides_considered: number;
  usd100_btc: number;
  usd100_neighbor_btc: number;
  round_stats: RoundUsdStat[];
};
export type DistributionBin = {
  start_sats: number;
  end_sats: number;
  count: number;
  weight_sum: number;
};

export type DistributionResp = {
  t: number;
  source: "mempool" | "blocks";
  bin_size_sats: number;
  bin_count: number;
  bins: DistributionBin[];
  total_samples: number;
  overflow: boolean;
  weighted: boolean;
  block_start: number | null;
  block_end: number | null;
  block_count: number | null;
};
