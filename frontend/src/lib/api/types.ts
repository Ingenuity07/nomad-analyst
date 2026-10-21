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
  timestamp?: string | null;
  regime?: string;
  trend_slope?: number | null;
  above_sma_200?: boolean | null;
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

export interface GlobalCueItem {
  name: string;
  close?: number | null;
  daily_change_percent?: number | null;
  last_timestamp?: string | null;
  stale?: boolean;
}

export type CrossMarketCues = Record<string, GlobalCueItem | any>;

export interface StockSummary {
  id: string;
  symbol: string;
  company_name?: string;
  name?: string;
  exchange: string;
  instrument_type?: string;
  is_active?: boolean;
  company?: Company | null;
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
  legal_name?: string | null;
  sector: string;
  industry: string;
  sub_industry?: string | null;
  description?: string | null;
  website?: string | null;
  isin?: string;
  is_active?: boolean;
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
  final_score?: number | string;
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

// ── Kite Connect Authentication & Data Health (Phase 17B) ───────────────────

export interface KiteStatusResponse {
  configured: boolean;
  authenticated: boolean;
  status: 'NOT_CONFIGURED' | 'AUTHENTICATION_REQUIRED' | 'AUTHENTICATING' | 'CONNECTED' | 'EXPIRED' | 'ERROR';
  user_id: string | null;
  user_name: string | null;
  authenticated_at: string | null;
  expires_at: string | null;
  last_error: string | null;
  login_url: string | null;
  provider: string;
}

export interface KiteDataHealthResponse {
  provider: string;
  authenticated: boolean;
  connection_status: string;
  market_session: string;
  is_market_open: boolean;
  data_status: 'LIVE' | 'WAITING_FOR_DATA' | 'MARKET CLOSED' | 'DISCONNECTED';
  subscribed_instruments_count: number;
  last_tick: {
    symbol: string;
    last_price: number;
    volume: number;
    exchange_timestamp: string | null;
    received_timestamp: string;
    is_suspicious: boolean;
  } | null;
  last_snapshot_timestamp: string | null;
  as_of: string;
}

// ── Phase 17C — Intraday Market Context & Signal Foundation ─────────────────

export interface IntradayIndexState {
  symbol: string;
  name: string;
  price: number;
  change: number;
  change_percent: number;
  open: number;
  high: number;
  low: number;
  vwap: number | null;
}

export interface IntradayBreadth {
  total_constituents: number;
  advance_count: number;
  decline_count: number;
  unchanged_count: number;
  advance_pct: number;
  decline_pct: number;
  unchanged_pct: number;
  advance_decline_ratio: number;
  above_vwap_count: number;
  below_vwap_count: number;
  above_vwap_pct: number;
  below_vwap_pct: number;
  at_high_count: number;
  at_low_count: number;
  breadth_state: 'STRONG_POSITIVE' | 'POSITIVE' | 'NEUTRAL' | 'NEGATIVE' | 'STRONG_NEGATIVE';
}

export interface IntradaySectorStrength {
  sector: string;
  constituent_count: number;
  average_return: number;
  median_return: number;
  advance_count: number;
  decline_count: number;
  advance_pct: number;
  above_vwap_pct: number;
  relative_strength_vs_nifty: number | null;
  rank: number;
}

export interface StockIntradayContextItem {
  symbol: string;
  company_name?: string;
  last_price: number;
  previous_close: number;
  open: number;
  high: number;
  low: number;
  change_pct: number;
  vwap: number | null;
  distance_from_vwap: number | null;
  is_above_vwap: boolean | null;
  volume: number;
  relative_volume: number | null;
  momentum_5m: number | null;
  momentum_15m: number | null;
  momentum_30m: number | null;
  relative_strength_vs_market: number | null;
  relative_strength_vs_sector: number | null;
  sector: string;
  sector_return: number | null;
  volume_confirmation: 'CONFIRMED_UP' | 'WEAK_UP' | 'CONFIRMED_DOWN' | 'WEAK_DOWN' | 'NEUTRAL';
  opening_gap_pct: number;
  opening_range_state: 'ABOVE_ORB' | 'BELOW_ORB' | 'INSIDE_ORB';
  component_scores: {
    momentum_score: number;
    relative_strength_score: number;
    volume_confirmation_score: number;
    vwap_alignment_score: number;
    sector_alignment_score: number;
    market_alignment_score: number;
  };
  context_score: number;
}

export interface IntradayMarketContextResponse {
  as_of: string;
  freshness: 'FRESH' | 'STALE' | 'UNAVAILABLE';
  freshness_age_seconds: number | null;
  is_fresh: boolean;
  market_direction: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  market_regime: 'TRENDING_UP' | 'TRENDING_DOWN' | 'RANGE' | 'VOLATILE' | 'TRANSITIONING' | 'UNKNOWN';
  regime_confidence: number;
  regime_reasons: string[];
  index_confirmation: 'CONFIRMED_BULLISH' | 'CONFIRMED_BEARISH' | 'DIVERGENT' | 'NEUTRAL';
  market_volatility: 'HIGH' | 'NORMAL';
  nifty: IntradayIndexState;
  banknifty: IntradayIndexState;
  breadth: IntradayBreadth;
  sectors: IntradaySectorStrength[];
  sector_leader: string | null;
  sector_laggard: string | null;
}

export interface IntradayStocksResponse {
  as_of: string;
  freshness: 'FRESH' | 'STALE' | 'UNAVAILABLE';
  count: number;
  stocks: StockIntradayContextItem[];
}

export interface IntradaySectorsResponse {
  as_of: string;
  freshness: 'FRESH' | 'STALE' | 'UNAVAILABLE';
  sector_leader: string | null;
  sector_laggard: string | null;
  count: number;
  sectors: IntradaySectorStrength[];
}

// ==============================================================================
// Phase 17D — Intraday Opportunity Engine Types
// ==============================================================================

export type OpportunityType =
  | 'MOMENTUM_CONTINUATION'
  | 'RELATIVE_STRENGTH'
  | 'VWAP_TREND'
  | 'OPENING_RANGE_BREAKOUT'
  | 'OPENING_RANGE_BREAKDOWN'
  | 'SECTOR_LEADERSHIP'
  | 'MEAN_REVERSION_CONTEXT'
  | 'NO_CLEAR_OPPORTUNITY';

export type OpportunityState =
  | 'EMERGING'
  | 'CONFIRMED'
  | 'WEAKENING'
  | 'INVALIDATED'
  | 'STALE';

export interface OpportunityScoreBreakdown {
  momentum_score: number;
  relative_strength_score: number;
  volume_score: number;
  vwap_score: number;
  market_alignment_score: number;
  sector_alignment_score: number;
  orb_score: number;
  data_quality_score: number;
}

export interface IntradayOpportunityItem {
  symbol: string;
  company_name?: string;
  timestamp: string;
  opportunity_type: OpportunityType;
  state: OpportunityState;
  score: number;
  base_score: number;
  confidence: number;
  bias: 'BULLISH' | 'BEARISH' | 'BULLISH_EXHAUSTION' | 'BEARISH_EXHAUSTION' | 'NEUTRAL';
  score_change?: number;
  component_scores: OpportunityScoreBreakdown;
  penalties: Array<{ reason: string; points: number }>;
  supporting_factors: string[];
  contradicting_factors: string[];
  warnings: string[];
  invalidation_condition: string;
  metrics: {
    last_price: number;
    change_pct: number;
    vwap: number | null;
    vwap_diff_pct: number;
    volume: number;
    relative_volume: number;
    momentum_5m: number;
    momentum_15m: number;
    relative_strength_vs_market: number;
    relative_strength_vs_sector: number;
    opening_range_state: string;
    volume_confirmation: string;
  };
  rank?: number;
  sector: {
    name: string;
    rank?: number | null;
    return_pct?: number;
  };
  market_alignment: 'STRONGLY_ALIGNED' | 'ALIGNED' | 'NEUTRAL' | 'DIVERGENT' | 'STRONGLY_DIVERGENT';
  sector_alignment: 'STRONGLY_ALIGNED' | 'ALIGNED' | 'NEUTRAL' | 'DIVERGENT';
  data_quality: 'HIGH' | 'MEDIUM' | 'LOW';
  freshness: 'FRESH' | 'STALE' | 'UNAVAILABLE';
  first_detected_at?: string;
  last_updated_at?: string;
}

export interface IntradayOpportunityResponse {
  timestamp: string;
  market_context: {
    regime: string;
    regime_confidence: number;
    breadth_state: string;
    advance_decline_ratio: number;
    sector_leader: string | null;
    sector_laggard: string | null;
  };
  total_evaluated: number;
  total_eligible: number;
  total_excluded: number;
  excluded_candidates: Array<{
    symbol: string;
    eligible: boolean;
    exclusion_reason: string;
    sector?: string;
  }>;
  ranking_mode: 'RAW_RANKING' | 'SECTOR_DIVERSIFIED';
  sector_concentration: Record<string, number>;
  opportunities: IntradayOpportunityItem[];
}

export interface IntradayTopOpportunitiesResponse {
  timestamp: string;
  market_regime: string;
  breadth_state: string;
  top_opportunities: IntradayOpportunityItem[];
}

// ── Phase 17E — On-Demand Research Engine ─────────────────────────────────────

export interface StructuredResearchOutput {
  summary: string;
  observed_facts: string[];
  analyst_interpretation: string;
  why_interesting: string[];
  supporting_evidence: string[];
  contradicting_evidence: string[];
  key_risks: string[];
  unknowns: string[];
  market_context_interpretation: string;
  sector_context_interpretation: string;
  thesis: string;
  thesis_strength: 'HIGH' | 'MEDIUM' | 'LOW';
  what_to_monitor: string[];
  invalidating_developments: string[];
  research_confidence: 'HIGH' | 'MEDIUM' | 'LOW';
}

export interface ResearchBasis {
  score: number | null;
  rank: number | null;
  state: string;
  market_regime: string;
  sector_name: string;
  sector_rank: number | null;
  timestamp: string | null;
}

export interface ResearchRunItem {
  id: string;
  symbol: string;
  mode: 'INTRADAY' | 'LONG_TERM' | 'GENERAL';
  status: 'queued' | 'running' | 'completed' | 'failed';
  started_at: string;
  completed_at: string | null;
  evidence_hash: string;
  output: StructuredResearchOutput;
  basis: ResearchBasis;
  model_name: string;
  provider: string;
  tokens_used: number;
  duration_ms: number;
  error_message?: string;
  error_category?: string;
}

export interface ResearchDeltaItem {
  research_id: string;
  symbol: string;
  mode: string;
  research_timestamp: string;
  evaluated_at: string;
  age_minutes: number;
  freshness: 'FRESH' | 'AGING' | 'STALE';
  staleness_reasons: string[];
  has_material_changes: boolean;
  changes_summary: string[];
  basis: {
    score: number | null;
    rank: number | null;
    state: string;
    market_regime: string;
    sector_rank: number | null;
    momentum_5m?: number | null;
    distance_from_vwap?: number | null;
    rs_vs_market?: number | null;
  };
  current: {
    score: number | null;
    rank: number | null;
    state: string;
    market_regime: string;
    sector_rank: number | null;
    momentum_5m?: number | null;
    distance_from_vwap?: number | null;
    rs_vs_market?: number | null;
  };
  deltas: {
    score_change: number;
    rank_change: number;
    state_changed: boolean;
    regime_changed: boolean;
    sector_rank_change: number;
    momentum_change: number;
    vwap_diff_change: number;
    relative_strength_change: number;
  };
  zero_llm_call_verified: boolean;
}

export interface ExamineResponse {
  reused: boolean;
  llm_calls_made: number;
  research: ResearchRunItem;
  delta?: ResearchDeltaItem | null;
}

// ── F&O Laboratory Contracts (Phase FNO-1) ───────────────────────────────────

export interface OptionQuoteSnapshotItem {
  id: number;
  instrument_token: number;
  tradingsymbol: string;
  strike_price?: number | string | null;
  option_type?: 'CE' | 'PE' | null;
  expiry_date?: string | null;
  exchange_timestamp_utc: string | null;
  received_wall_clock_utc: string;
  exchange_time_status: string;
  best_bid: string | number | null;
  best_ask: string | number | null;
  bid_quantity_l1: number | null;
  ask_quantity_l1: number | null;
  depth: Record<string, any>;
  quote_status: string;
  is_stale: boolean;
  is_locked: boolean;
  is_crossed: boolean;
  is_execution_eligible: boolean;
  spread_pct: string | null;
  spread_abs: string | null;
  created_at: string;
}

export interface FnoOverviewResponse {
  underlying: {
    symbol: string;
    spot_price: number | null;
    market_direction: string;
    market_regime: string;
    atm_strike: number | null;
    as_of?: string | null;
  };
  feed: {
    status: 'ACTIVE' | 'DEGRADED' | 'STANDBY_MARKET_CLOSED' | 'DISCONNECTED';
    market_session?: 'OPEN' | 'CLOSED';
    ticker_running?: boolean;
    ticker_pid?: number | null;
    latest_exchange_timestamp: string | null;
    latest_received_wall_clock: string | null;
    quote_age_seconds: number | null;
    active_contracts_tracked: number;
    total_quotes_today?: number;
    total_bars_today?: number;
  };
  quotes: OptionQuoteSnapshotItem[];
  timestamp: string;
}

export interface PaperTradeLedgerItem {
  trade_id: number;
  strategy_id: string;
  strategy_version: string;
  signal_id: string;
  instrument_token: number;
  tradingsymbol: string;
  option_type: 'CE' | 'PE';
  strike_price: string | number;
  expiry_date: string;
  entry_timestamp: string;
  entry_fill_price: string | number;
  entry_slippage: string | number;
  quantity: number;
  exit_timestamp: string | null;
  exit_trigger_reason: string | null;
  fill_type: string;
  exit_fill_price: string | number | null;
  exit_slippage: string | number;
  gross_pnl: string | number | null;
  total_frictions: string | number;
  net_pnl: string | number | null;
  friction_breakdown: Record<string, any>;
  statutory_breakdown: Record<string, any>;
  market_regime_at_entry: string | null;
  vix_level_at_entry: string | number | null;
  status: string;
  rejection_reason: string | null;
  created_at: string;
}

export interface FnoStrategyResponse {
  strategy: {
    strategy_id: string;
    name: string;
    version: string;
    status: string;
    runtime_telemetry_available: boolean;
    session_date: string;
    last_evaluation_time?: string | null;
  };
  opening_range: {
    expected_bars: number;
    available_bars: number;
    runtime_established?: boolean;
    range_high: number | null;
    range_low: number | null;
    range_width: number | null;
    status: 'PENDING_OPEN' | 'FORMING' | 'LOCKED' | 'FAIL_CLOSED' | 'UNAVAILABLE' | 'INCOMPLETE';
    time_window: string;
  };
  audit_trail: {
    evaluations_count?: number | null;
    eligible_evaluations?: number | null;
    signals_count?: number;
    rejections_count?: number;
    rejection_summary: Record<string, number>;
    recent_signals: PaperTradeLedgerItem[];
    total_signals_today: number;
  };
  timestamp: string;
}

export interface FnoTradesResponse {
  summary: {
    ledger_status?: 'EMPTY' | 'POPULATED' | 'UNAVAILABLE';
    total_trades: number;
    open_positions_count: number;
    wins: number;
    losses: number;
    win_rate_pct: number;
    gross_pnl: string;
    net_pnl: string;
    total_frictions: string;
    is_paper_trading: boolean;
  };
  open_positions: PaperTradeLedgerItem[];
  closed_trades: PaperTradeLedgerItem[];
  rejections: PaperTradeLedgerItem[];
  timestamp: string;
}

export interface FnoDiagnosticsResponse {
  session_date: string;
  bars: {
    total_today: number;
    complete_count: number;
    partial_count: number;
    partial_ratio_pct: number;
    quality_status: 'EXCELLENT' | 'DEGRADED' | 'CRITICAL';
  };
  quotes: {
    total_today: number;
    eligible_count: number;
    stale_count: number;
    latest_feed_latency_seconds: number | null;
  };
  components: {
    postgresql: string;
    ticker_daemon?: string;
    ticker_pid?: number | null;
    fee_schedule: string;
    paper_execution_mode: string;
  };
  timestamp: string;
}

