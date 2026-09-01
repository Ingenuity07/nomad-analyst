/**
 * Nomad Analyst v1 — Canonical TypeScript API Contracts
 * Exact match to Django REST API (BE-API-1) Serializers.
 */

// ── Standard Envelopes & Pagination ──────────────────────────────────────────

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details: Record<string, any>;
    timestamp: string;
  };
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ── Market Overview & Context ────────────────────────────────────────────────

export interface MarketSessionInfo {
  window: 'OPENING' | 'MORNING' | 'MIDDAY' | 'AFTERNOON' | 'CLOSING' | 'OUTSIDE' | 'HISTORICAL';
  minutes_elapsed?: number;
  minutes_remaining?: number;
  is_trading_hour: boolean;
  session_date?: string;
  message?: string;
}

export interface MarketIndexItem {
  symbol: string;
  name: string;
  price: number | null;
  change: number | null;
  change_percent: number | null;
  timestamp: string | null;
}

export interface MarketBreadth {
  advances?: number;
  declines?: number;
  unchanged?: number;
  advancing?: number;
  declining?: number;
  advance_decline_ratio?: number;
  breadth_regime?: string;
  coverage?: {
    total_universe_size: number;
    active_coverage_size: number;
    coverage_ratio: number;
    missing_symbols: string[];
  };
  participation?: {
    pct_above_sma20?: number;
    pct_above_sma50?: number;
    pct_above_sma200?: number;
  };
  pct_above_50_sma?: number;
  pct_above_200_sma?: number;
  new_highs_count?: number;
  new_lows_count?: number;
}

export interface IndexRegime {
  symbol: string;
  status?: string;
  trend?: 'BULLISH' | 'BEARISH' | 'NEUTRAL' | string;
  regime?: string;
  sma_50?: number | null;
  sma_200?: number | null;
  distance_from_52w_high?: number | null;
  volatility_regime?: 'LOW' | 'NORMAL' | 'ELEVATED' | 'HIGH' | string;
  error?: string;
}

export interface SectorRanking {
  sector: string;
  change_percent?: number;
  average_return?: number;
  relative_return_vs_nifty?: number;
  average_rsi?: number;
  average_volatility?: number;
  relative_strength_score?: number;
  rank: number;
  trend?: 'LEADER' | 'IMPROVING' | 'WEAKENING' | 'LAGGING' | string;
  momentum_state?: string;
  tier?: string;
}

export interface GlobalCue {
  name: string;
  symbol: string;
  price?: number | null;
  change_percent?: number | null;
  impact_bias?: 'BULLISH' | 'BEARISH' | 'NEUTRAL' | string;
}

export interface DataFreshness {
  source?: string;
  last_updated?: string;
  timestamp?: string;
  status: 'LIVE' | 'STALE' | 'INCOMPLETE' | 'UNAVAILABLE';
}

export interface MarketOverviewResponse {
  as_of: string;
  universe: string;
  market_session: MarketSessionInfo;
  indices?: MarketIndexItem[];
  breadth?: MarketBreadth;
  index_regimes?: Record<string, IndexRegime> | IndexRegime[];
  sector_rankings?: SectorRanking[];
  global_cues?: Record<string, any> | GlobalCue[];
  cross_market_cues?: Record<string, any>;
  recent_news?: NewsItem[];
  data_freshness?: DataFreshness;
}

// ── Stocks & Instruments ─────────────────────────────────────────────────────

export interface Company {
  id: string;
  name: string;
  short_name: string;
  sector: string;
  industry: string;
  isin?: string;
}

export interface Instrument {
  id: string;
  symbol: string;
  exchange: string;
  instrument_type: string;
  is_active: boolean;
  company: Company | null;
}

export interface InstrumentSearchResult {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
  exchange: string;
}

export interface MarketSnapshot {
  id: string;
  timestamp: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  previous_close: number | null;
  change: number | null;
  change_percent: number | null;
  source: string;
}

export interface StockDetailResponse {
  instrument: Instrument;
  latest_snapshot: MarketSnapshot | null;
  active_recommendation: StockRecommendation | null;
  latest_opportunity: StockOpportunitySnapshot | null;
  data_freshness?: {
    status: string;
    timestamp: string | null;
  };
  as_of?: string;
}

export interface OHLCVBar {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  source: string;
}

export interface StockOHLCVResponse {
  symbol: string;
  exchange: string;
  timeframe: string;
  bars_count: number;
  bars: OHLCVBar[];
  data_quality: {
    status: 'COMPLETE' | 'INCOMPLETE' | 'NO_DATA';
    gaps_detected: number;
  };
}

export interface TechnicalIndicatorValue {
  value: number | null;
  parameters: Record<string, any>;
  as_of: string;
}

export interface StockTechnicalsResponse {
  symbol: string;
  timeframe: string;
  as_of: string;
  indicators_count: number;
  indicators: Record<string, TechnicalIndicatorValue>;
  status: string;
}

// ── Fundamentals ─────────────────────────────────────────────────────────────

export interface IncomeStatement {
  id: string;
  fiscal_year: number;
  period_type: string;
  period_string: string;
  period_start: string | null;
  period_end: string | null;
  filing_date: string | null;
  revenue: number | null;
  expenses: number | null;
  ebitda: number | null;
  ebit: number | null;
  depreciation: number | null;
  interest: number | null;
  pbt: number | null;
  tax: number | null;
  pat: number | null;
  eps: number | null;
}

export interface BalanceSheetStatement {
  id: string;
  fiscal_year: number;
  period_type: string;
  period_string: string;
  period_start: string | null;
  period_end: string | null;
  filing_date: string | null;
  equity_capital: number | null;
  reserves: number | null;
  borrowings: number | null;
  other_liabilities: number | null;
  total_liabilities: number | null;
  fixed_assets: number | null;
  cwip: number | null;
  investments: number | null;
  other_assets: number | null;
  total_assets: number | null;
}

export interface CashFlowStatement {
  id: string;
  fiscal_year: number;
  period_type: string;
  period_string: string;
  period_start: string | null;
  period_end: string | null;
  filing_date: string | null;
  operating_cash_flow: number | null;
  investing_cash_flow: number | null;
  financing_cash_flow: number | null;
  free_cash_flow: number | null;
}

export interface DerivedFundamentalMetric {
  id: string;
  name: string;
  period_type: string;
  period_string: string;
  value: number | null;
}

export interface StockFundamentalsResponse {
  symbol: string;
  company_name: string;
  sector: string;
  industry: string;
  statements: {
    income_statement: IncomeStatement[];
    balance_sheet: BalanceSheetStatement[];
    cash_flow: CashFlowStatement[];
  };
  metrics: DerivedFundamentalMetric[];
  data_quality: {
    source: string;
    status: string;
  };
}

export interface NewsItem {
  id: string;
  symbol?: string;
  headline: string;
  summary: string;
  source: string;
  source_id?: string;
  url: string;
  published_at: string;
  event_type?: string;
  raw_metadata?: Record<string, any>;
}

export interface CorporateDisclosure {
  id: string;
  headline: string;
  category: string;
  source: string;
  announcement_id: string;
  url: string;
  published_at: string;
  details: Record<string, any>;
}

// ── Opportunities & Recommendations ──────────────────────────────────────────

export interface StockOpportunitySnapshot {
  id: string;
  symbol: string;
  company_name: string;
  sector: string;
  as_of: string;
  universe: string;
  horizon: 'INTRADAY' | 'DELIVERY_SWING' | 'DELIVERY_POSITIONAL' | string;
  opportunity_type: string;
  final_opportunity_score: number | string;
  component_scores: Record<string, number>;
  supporting_features: Record<string, any>;
  reasons?: string[];
  risks: string[];
  data_quality: Record<string, any>;
  created_at?: string;
}

export interface StockRecommendation {
  id: string;
  symbol: string;
  company_name: string;
  sector: string;
  as_of: string;
  horizon: 'INTRADAY' | 'DELIVERY_SWING' | 'DELIVERY_POSITIONAL';
  signal: 'BUY' | 'SELL' | 'NO_ACTION';
  setup_type: string;
  timeframe: string | null;
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  status: 'ACTIVE' | 'TRIGGERED' | 'TARGET_HIT' | 'STOPPED' | 'EXPIRED' | 'CANCELLED';
  entry_type: string;
  entry_price: number | null;
  entry_condition: string;
  stop_price: number | null;
  stop_method: string;
  invalidation_reason: string;
  target_price: number | null;
  target_method: string;
  target_2_price: number | null;
  target_2_method: string | null;
  risk: number | null;
  reward: number | null;
  risk_reward_ratio: number | null;
  session_window?: string;
  expires_at?: string;
  supporting_factors: string[];
  risk_factors: string[];
  setup_details: Record<string, any>;
  market_context: Record<string, any>;
  sector_context: Record<string, any>;
  data_quality: Record<string, any>;
  calculation_version: number;
  status_updated_at: string | null;
  generated_at: string;
}

export interface RecommendationOutcome {
  id: string;
  recommendation: string;
  symbol: string;
  signal: string;
  setup_type: string;
  timeframe: string | null;
  horizon: string;
  evaluation_version: number;
  evaluated_at: string;
  entry_triggered: boolean;
  entry_timestamp: string | null;
  actual_entry_price: number | null;
  exit_reason: string | null;
  exit_timestamp: string | null;
  actual_exit_price: number | null;
  net_pnl_percent: number | null;
  r_multiple: number | null;
  target_hit: boolean | null;
  stop_hit: boolean | null;
  ambiguous_intrabar: boolean;
  max_favorable_excursion: number | null;
  max_adverse_excursion: number | null;
  holding_duration_bars: number | null;
  holding_duration_seconds: number | null;
  bars_evaluated: number;
  data_quality_warnings: string[];
}

// ── Intraday ─────────────────────────────────────────────────────────────────

export interface IntradayOverviewResponse {
  market_session: MarketSessionInfo;
  summary: {
    active_signals: number;
    triggered_signals: number;
    timeframes_supported: string[];
  };
  as_of: string;
}

export interface IntradayReadinessResponse {
  symbol: string;
  timeframe: string;
  is_ready: boolean;
  reason: string;
  bar_count: number;
  required_bars: number;
  quality: Record<string, any> | null;
  checks_passed: string[];
  checks_failed: string[];
  checked_at: string;
}

// ── Strategy & Backtest ──────────────────────────────────────────────────────

export interface StrategyItem {
  key: string;
  name: string;
  horizon: string;
  timeframe: string;
  description: string;
}

export interface StrategyPerformanceResponse {
  strategy: string;
  sample_size: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_r_multiple: number;
  is_small_sample: boolean;
  evaluated_at: string;
}

export interface BacktestRun {
  id: string;
  run_id: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETE' | 'FAILED';
  universe_name: string;
  timeframe: string;
  horizon: string;
  start_date: string;
  end_date: string;
  strategy_version: string;
  config: Record<string, any>;
  result: Record<string, any> | null;
  data_quality_warnings: string[];
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface BacktestRunPayload {
  universe_name: string;
  timeframe: string;
  horizon: string;
  start_date: string;
  end_date: string;
  cost_mode?: 'NO_COST' | 'REALISTIC' | 'CUSTOM' | string;
  brokerage_pct?: number;
  stt_pct?: number;
  slippage_bps?: number;
  ambiguity_policy?: 'CONSERVATIVE' | 'OPTIMISTIC' | 'EXCLUDE' | string;
}

// ── AI Research ──────────────────────────────────────────────────────────────

export interface ResearchRequestPayload {
  symbol: string;
  question?: string;
  depth?: 'quick' | 'standard' | 'deep';
  as_of?: string;
}

export interface ResearchReportResponse {
  company: string;
  instrument: string;
  as_of: string | null;
  summary: string;
  market_snapshot: Record<string, any>;
  technical_analysis: string;
  fundamental_analysis: string;
  news_analysis: string;
  positive_factors: string[];
  risks: string[];
  contradictions: string[];
  unknowns: string[];
  evidence: string[];
  generated_at: string;
}
