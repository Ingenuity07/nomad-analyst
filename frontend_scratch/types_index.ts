import type { LucideIcon } from 'lucide-react'

/* ------------------------------------------------------------------ */
/* Overview dashboard                                                  */
/* ------------------------------------------------------------------ */

export type MetricDirection = 'up' | 'down' | 'flat'

export interface WorkspaceMetric {
  id: string
  label: string
  value: string
  /** e.g. "18%", "3 new" */
  change: string
  direction: MetricDirection
  /** e.g. "vs. last 30 days" */
  note: string
  icon: LucideIcon
}

export type Momentum = 'Rising' | 'High' | 'New' | 'Stable'

export interface ProblemCluster {
  id: string
  /** e.g. "Manual route planning" */
  title: string
  /** e.g. "Routing & dispatch" */
  category: string
  liveSignals: number
  accounts: number
  momentum: Momentum
  icon: LucideIcon
  iconTone: 'lime' | 'blue' | 'amber' | 'violet' | 'teal' | 'rose'
}

export interface SignalPulse {
  /** Week labels, oldest first, e.g. ["Jun 23", "Jul 7", ...] */
  weeks: string[]
  /** New signals per week, oldest first */
  values: number[]
  /** Percent change shown in the trend chip */
  changePct: number
  /** Most recent week's total */
  total: number
  note: string
}

export type BuyingWindow = 'Act now' | 'This quarter' | 'This month' | 'Researching' | 'Monitoring' | 'Next quarter'

export interface PriorityAccount {
  /** URL slug, e.g. "northstar-logistics" */
  id: string
  name: string
  location: string
  initials: string
  markTone: 'navy' | 'orange' | 'green' | 'purple' | 'blue' | 'rose'
  problem: string
  window: BuyingWindow
  fitScore: number
}

export type ActivityTone = 'lime' | 'blue' | 'amber'

export interface ActivityEvent {
  id: string
  title: string
  detail: string
  /** e.g. "8 min" */
  time: string
  tone: ActivityTone
  icon: LucideIcon
}

export interface DashboardData {
  metrics: WorkspaceMetric[]
  problems: ProblemCluster[]
  pulse: SignalPulse
  priorityAccounts: PriorityAccount[]
  activity: ActivityEvent[]
}

/* ------------------------------------------------------------------ */
/* Discover                                                            */
/* ------------------------------------------------------------------ */

export type EvidenceKind = 'hiring' | 'technology' | 'language' | 'change'

export interface EvidenceOption {
  id: EvidenceKind
  title: string
  description: string
  icon: LucideIcon
}

export interface DiscoverySuggestion {
  id: string
  label: string
}

export type DiscoveryStageId =
  | 'queued'
  | 'discovering'
  | 'resolving'
  | 'researching'
  | 'completed'
  | 'failed'

/** POST /discover/ response (ProspectingDiscoverAPIView). */
export interface DiscoveryStartResponse {
  status: string
  run_id: string
  message: string
}

/** One progress step of a discovery run (mirrors backend broadcast_progress). */
export interface DiscoveryProgressStep {
  stage: DiscoveryStageId
  progress: number
  message: string
}

/** Front-end state of an in-flight discovery run. */
export interface DiscoveryRun {
  runId: string
  keyword: string
  location: string
  status: 'running' | 'completed' | 'failed'
  progress: number
  stage: DiscoveryStageId
}

/* ------------------------------------------------------------------ */
/* Signals                                                             */
/* ------------------------------------------------------------------ */

export interface SignalStat {
  id: string
  label: string
  value: string
  note: string
  highlight?: string
  tone: 'lime' | 'blue' | 'amber' | 'violet'
  icon: LucideIcon
}

export type Health = 'High precision' | 'Needs tuning'

export interface ProblemSignal {
  id: string
  title: string
  description: string
  category: string
  iconTone: 'lime' | 'blue' | 'amber' | 'violet' | 'rose' | 'teal'
  momentum: Momentum
  evidenceTypes: number
  updatedAgo: string
  accounts: number
  trend: number[]
  health: Health
  watching: boolean
}

export interface SignalCategory {
  id: string
  label: string
}

/* ------------------------------------------------------------------ */
/* Leads                                                               */
/* ------------------------------------------------------------------ */

export interface LeadKpi {
  id: string
  label: string
  value: string
  note?: string
  tone?: 'up' | 'hot'
  icon: LucideIcon
}

export interface LeadRow {
  id: string
  name: string
  industry: string
  location: string
  initials: string
  markTone: PriorityAccount['markTone']
  problem: string
  signals: number
  sources: number
  window: BuyingWindow
  fitScore: number
  owner: string
  ownerInitials: string
  unassigned?: boolean
  lastSeen: string
  discoveryRunId?: string
  discoveryRunKeyword?: string
  discoveryRunLocation?: string
}

/* ------------------------------------------------------------------ */
/* Lists                                                               */
/* ------------------------------------------------------------------ */

export interface AccountList {
  id: string
  name: string
  description: string
  kind: 'smart' | 'static'
  iconTone: 'lime' | 'blue' | 'amber' | 'violet' | 'teal'
  accounts: number
  newThisWeek: number
  actNow: number
  owners: string[]
  updated: string
}

/* ------------------------------------------------------------------ */
/* Campaigns                                                           */
/* ------------------------------------------------------------------ */

export interface CampaignMetric {
  id: string
  label: string
  value: string
  note: string
  change: string
  flat?: boolean
  icon: LucideIcon
}

export type CampaignStatus = 'Live' | 'Paused' | 'Draft' | 'Completed'

export interface Campaign {
  id: string
  name: string
  problem: string
  updated: string
  status: CampaignStatus
  sent: number
  total: number
  positiveReplies: number
  meetings: number
  owner: string
  iconTone: 'lime' | 'blue' | 'amber'
}

export interface Playbook {
  id: string
  title: string
  problem: string
  steps: number
  avgReply: string
  iconTone: 'lime' | 'blue' | 'amber'
}

/* ------------------------------------------------------------------ */
/* Analytics                                                           */
/* ------------------------------------------------------------------ */

export interface AnalyticsMetric {
  id: string
  label: string
  value: string
  /** Bold change shown before the note, e.g. "↗ 22.8%" */
  change?: string
  note: string
  featured?: boolean
  spark?: number[]
  icon: LucideIcon
}

export interface FunnelStage {
  id: string
  label: string
  count: number
  pct: string
  width: number
}

export interface ProblemPerformance {
  id: string
  problem: string
  tone: 'lime' | 'blue' | 'amber' | 'violet'
  accounts: number
  qualified: number
  positiveReply: number
  meetings: number
  pipeline: string
}

export interface SourceRanking {
  id: string
  name: string
  rate: string
  bar: number
}

/* ------------------------------------------------------------------ */
/* Account detail                                                      */
/* ------------------------------------------------------------------ */

export interface ScoreFactor {
  id: string
  label: string
  value: number
}

export type EvidenceStrength = 'strong' | 'medium'

export interface EvidenceItem {
  id: string
  title: string
  time: string
  detail: string
  source: string
  strength: EvidenceStrength
  tone: 'lime' | 'blue' | 'amber'
}

export interface Contact {
  id: string
  name: string
  role: string
  initials: string
  relevance: string
  relevancePct: number
  avatarClass: string
  relevanceClass: string
}

export interface AccountDetail {
  id: string
  name: string
  domain: string
  industry: string
  location: string
  initials: string
  markTone: PriorityAccount['markTone']
  status: string
  /** Detected operational problem, e.g. "Manual route planning" */
  problem: string
  score: number
  scoreLabel: string
  scoreNote: string
  factors: ScoreFactor[]
  nextStep: string
  thesis: string
  confidence: string
  evidenceTotal: number
  evidence: EvidenceItem[]
  contacts: Contact[]
  window: BuyingWindow
  windowScore: number
  windowNote: string
  windowReasons: string[]
  windowUpdated: string
  snapshot: { label: string; value: string }[]
  talkingPoints: string[]
}
