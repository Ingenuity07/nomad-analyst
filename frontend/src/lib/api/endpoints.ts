/**
 * Nomad Analyst v1 Endpoint Registry
 */

export const ENDPOINTS = {
  // Market Context
  MARKET_OVERVIEW: '/api/v1/market/overview/',
  MARKET_INDICES: '/api/v1/market/indices/',
  MARKET_REGIME: '/api/v1/market/regime/',
  MARKET_BREADTH: '/api/v1/market/breadth/',
  MARKET_SECTORS: '/api/v1/market/sectors/',
  MARKET_GLOBAL: '/api/v1/market/global/',

  // Stocks
  STOCKS: '/api/v1/stocks/',
  STOCK_SEARCH: '/api/v1/stocks/search/',
  STOCK_DETAIL: (symbol: string) => `/api/v1/stocks/${encodeURIComponent(symbol)}/`,
  STOCK_OHLCV: (symbol: string) => `/api/v1/stocks/${encodeURIComponent(symbol)}/ohlcv/`,
  STOCK_TECHNICALS: (symbol: string) => `/api/v1/stocks/${encodeURIComponent(symbol)}/technicals/`,
  STOCK_FUNDAMENTALS: (symbol: string) => `/api/v1/stocks/${encodeURIComponent(symbol)}/fundamentals/`,
  STOCK_NEWS: (symbol: string) => `/api/v1/stocks/${encodeURIComponent(symbol)}/news/`,
  STOCK_EVENTS: (symbol: string) => `/api/v1/stocks/${encodeURIComponent(symbol)}/events/`,

  // Opportunities & Recommendations
  OPPORTUNITIES: '/api/v1/opportunities/',
  OPPORTUNITY_DETAIL: (id: string) => `/api/v1/opportunities/${id}/`,
  RECOMMENDATIONS: '/api/v1/recommendations/',
  RECOMMENDATION_DETAIL: (id: string) => `/api/v1/recommendations/${id}/`,
  RECOMMENDATION_OUTCOME: (id: string) => `/api/v1/recommendations/${id}/outcome/`,

  // Intraday
  INTRADAY_OVERVIEW: '/api/v1/intraday/overview/',
  INTRADAY_RECOMMENDATIONS: '/api/v1/intraday/recommendations/',
  INTRADAY_DATA_QUALITY: '/api/v1/intraday/data-quality/',

  // Outcomes & Strategies
  OUTCOMES: '/api/v1/outcomes/',
  STRATEGIES: '/api/v1/strategies/',
  STRATEGY_PERFORMANCE: (strategy: string) => `/api/v1/strategies/${encodeURIComponent(strategy)}/performance/`,

  // Backtest
  BACKTESTS: '/api/v1/backtests/',
  BACKTEST_RUN: '/api/v1/backtests/run/',
  BACKTEST_DETAIL: (runId: string) => `/api/v1/backtests/${encodeURIComponent(runId)}/`,

  // Research
  RESEARCH: '/api/v1/research/',
  RESEARCH_EXAMINE: '/api/v1/research/examine/',
  RESEARCH_DETAIL: (id: string) => `/api/v1/research/${id}/`,
  RESEARCH_COMPANY: (symbol: string, mode: string = 'INTRADAY') => `/api/v1/research/company/${encodeURIComponent(symbol)}/?mode=${encodeURIComponent(mode)}`,
  RESEARCH_REFRESH: (id: string) => `/api/v1/research/${id}/refresh/`,
  RESEARCH_DELTA: (id: string) => `/api/v1/research/${id}/delta/`,
};
