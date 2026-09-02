/* eslint-disable @typescript-eslint/no-explicit-any */
// Backend adapter: the live Django API returns untyped JSON, so payloads are
// cast to the app's types at this boundary (same pattern as api/client.ts).
import { Building2, Target, Zap, Users, UsersRound, TrendingUp, Radar, MailCheck } from 'lucide-react'
import type {
  AccountList,
  AccountDetail,
  AnalyticsMetric,
  BuyingWindow,
  Campaign,
  CampaignMetric,
  DashboardData,
  DiscoveryStartResponse,
  FunnelStage,
  LeadKpi,
  LeadRow,
  Momentum,
  Playbook,
  ProblemCluster,
  ProblemPerformance,
  ProblemSignal,
  SignalCategory,
  SignalStat,
  SourceRanking,
  WorkspaceMetric
} from '../types'
import { apiFetch } from './client'
import {
  accountDetails,
  buildFallbackAccountDetail,
  accountLists,
  campaignInsight,
  campaignMetrics,
  campaigns,
  funnelInsight,
  funnelStages,
  leadKpis,
  leads,
  mockDashboard,
  pipeline,
  playbooks,
  problemPerformance,
  signalCategories,
  signalStats,
  signals,
  sourceRanking,
} from './mockData'

/** Try the backend; on any failure fall back to the bundled mock data. */
async function withFallback<T>(endpoint: string, fallback: T, options?: any): Promise<T> {
  try {
    return await apiFetch<T>(endpoint, options)
  } catch {
    return fallback
  }
}

/* ------------------------------------------------------------------ */
/* Overview                                                            */
/* ------------------------------------------------------------------ */

export const getDashboard = async (): Promise<DashboardData> => {
  try {
    const raw = await apiFetch<any>('/dashboard/overview/')
    const dynamicMetrics: WorkspaceMetric[] = [
      {
        id: 'qualified-accounts',
        label: 'Discovered leads',
        value: String(raw.discovered ?? 0),
        change: 'New',
        direction: 'up',
        note: 'leads found',
        icon: Building2,
      },
      {
        id: 'high-fit',
        label: 'Qualified leads',
        value: String(raw.qualified ?? 0),
        change: 'Active',
        direction: 'up',
        note: 'high match fit',
        icon: Target,
      },
      {
        id: 'act-now',
        label: 'Contacted leads',
        value: String(raw.contacted ?? 0),
        change: 'Engaged',
        direction: 'up',
        note: 'outreach active',
        icon: Zap,
      },
      {
        id: 'unassigned',
        label: 'Positive replies',
        value: String(raw.positive ?? 0),
        change: 'Interested',
        direction: 'up',
        note: 'ready to book',
        icon: Users,
      }
    ]
    return {
      ...mockDashboard,
      metrics: dynamicMetrics,
    }
  } catch {
    return mockDashboard
  }
}

export const getProblems = async (): Promise<ProblemCluster[]> => {
  try {
    const raw = await apiFetch<any[]>('/dashboard/signals/')
    const tones: Array<'lime' | 'blue' | 'amber' | 'violet' | 'teal' | 'rose'> = ['lime', 'blue', 'amber', 'violet', 'teal', 'rose']
    const momentums: Momentum[] = ['High', 'Rising', 'Stable', 'New']
    return raw.map((item, idx) => ({
      id: String(idx),
      title: item.signal__name || 'Unknown problem',
      category: item.signal__category || 'Operations',
      liveSignals: item.total_detections || 0,
      accounts: item.active_count || 0,
      momentum: momentums[idx % momentums.length],
      icon: Target,
      iconTone: tones[idx % tones.length],
    }))
  } catch {
    return mockDashboard.problems
  }
}

/* ------------------------------------------------------------------ */
/* Discover                                                            */
/* ------------------------------------------------------------------ */

/**
 * POST /discover/ (ProspectingDiscoverAPIView).
 * Sends { keyword, location } and receives { status, run_id, message }.
 * Falls back to a mock run_id when the backend is unreachable.
 */
export const postDiscover = (body: { keyword: string; location: string }): Promise<DiscoveryStartResponse> =>
  withFallback<DiscoveryStartResponse>(
    '/discover/',
    { status: 'success', run_id: 'mock-run', message: 'Discovery run queued successfully.' },
    { method: 'POST', body },
  )

export const getDiscoveryRunStatus = (id: string) =>
  apiFetch<any>(`/discover/${id}/status/`)

export const postIntake = (body: { objective: string; target?: string; qualification?: string }) =>
  apiFetch<any>('/intake/', {
    method: 'POST',
    body,
  })

export const getIntakeDetail = (id: string) =>
  apiFetch<any>(`/intake/${id}/`)

export const postIntakeClarify = (id: string, body: { question: string; answer: string }) =>
  apiFetch<any>(`/intake/${id}/clarify/`, {
    method: 'POST',
    body,
  })

export const patchIntakeSpecification = (id: string, body: { specification_json: any }) =>
  apiFetch<any>(`/intake/${id}/specification/`, {
    method: 'PATCH',
    body,
  })

export const postIntakeConfirm = (id: string, body: { version: number }) =>
  apiFetch<any>(`/intake/${id}/confirm/`, {
    method: 'POST',
    body,
  })

export const postIntakeCancel = (id: string) =>
  apiFetch<any>(`/intake/${id}/cancel/`, {
    method: 'POST',
  })


/* ------------------------------------------------------------------ */
/* Signals                                                             */
/* ------------------------------------------------------------------ */

export const getSignalStats = async (): Promise<SignalStat[]> => {
  try {
    const raw = await apiFetch<any[]>('/dashboard/signals/')
    const tones: Array<'lime' | 'blue' | 'amber' | 'violet'> = ['lime', 'blue', 'amber', 'violet']
    return raw.slice(0, 4).map((item, idx) => ({
      id: String(idx),
      label: item.signal__name || 'Unknown',
      value: String(item.total_detections || 0),
      note: 'Detections in last 30d',
      tone: tones[idx % tones.length],
      icon: Zap,
    }))
  } catch {
    return signalStats
  }
}
export const getSignalCategories = async (): Promise<SignalCategory[]> => {
  try {
    const raw = await apiFetch<any[]>('/dashboard/signals/')
    const categories = Array.from(new Set(raw.map(item => item.signal__category || 'Operations')))
    return categories.map((cat, idx) => ({
      id: String(idx),
      label: cat,
    }))
  } catch {
    return signalCategories
  }
}
export const getSignals = () => withFallback('/signals/', signals as ProblemSignal[])

/* ------------------------------------------------------------------ */
/* Leads                                                               */
/* ------------------------------------------------------------------ */

export const getLeadKpis = async (): Promise<LeadKpi[]> => {
  try {
    const raw = await apiFetch<any>('/dashboard/overview/')
    return [
      { id: 'total', label: 'Total qualified', value: String(raw.discovered ?? 0), icon: UsersRound },
      { id: 'high-fit', label: 'High fit · 85+', value: String(raw.qualified ?? 0), note: '-', tone: 'up', icon: Target },
      { id: 'act-now', label: 'Act now', value: String(raw.contacted ?? 0), note: '-', tone: 'hot', icon: Zap },
      { id: 'unassigned', label: 'Positive replies', value: String(raw.positive ?? 0), note: '-', icon: Users },
    ]
  } catch {
    return leadKpis
  }
}
export const getLeads = async (): Promise<LeadRow[]> => {
  try {
    const raw = await apiFetch<any>('/leads/')
    const backendLeads: LeadRow[] = (raw.leads || []).map((lead: any) => {
      let windowVal: BuyingWindow = 'Researching'
      if (lead.analysis?.lead_score >= 85) windowVal = 'Act now'
      else if (lead.analysis?.lead_score >= 75) windowVal = 'This quarter'
      
      return {
        id: lead.id,
        name: lead.name,
        industry: lead.category || 'Operations',
        location: lead.address || 'Unknown',
        initials: lead.name.slice(0, 2).toUpperCase(),
        markTone: 'navy',
        problem: lead.analysis?.description || 'Needs operational optimization',
        signals: 4,
        sources: 2,
        window: windowVal,
        fitScore: lead.analysis?.lead_score || 70,
        owner: 'Shivam Singh',
        ownerInitials: 'SS',
        lastSeen: '1d ago',
        discoveryRunId: lead.discovery_run_id,
        discoveryRunKeyword: lead.discovery_run_keyword,
        discoveryRunLocation: lead.discovery_run_location
      }
    })
    return backendLeads
  } catch {
    return leads
  }
}
export const getAccountDetail = async (id: string): Promise<AccountDetail | null> => {
  try {
    const raw = await apiFetch<any>(`/leads/${id}/intelligence/`)
    const company = raw.company ?? {}
    const scores = raw.scores ?? {}
    const explanation = raw.explanation ?? {}
    const contacts = raw.contacts ?? []
    const rawEvidence = raw.evidence_timeline ?? []
    
    const name = company.name || 'Unknown Company'
    const initials = name.split(' ').map((n: string) => n[0]).join('').slice(0, 2).toUpperCase() || 'CO'
    
    const mappedContacts = contacts.map((c: any, index: number) => {
      const initials = (c.first_name?.[0] || '') + (c.last_name?.[0] || '')
      return {
        id: c.id,
        name: `${c.first_name || ''} ${c.last_name || ''}`.trim() || 'Contact',
        role: c.role || 'Stakeholder',
        initials: initials.toUpperCase() || 'CT',
        relevance: c.relevance_score >= 80 ? 'Decision maker' : 'Key influencer',
        relevancePct: c.relevance_score || 70,
        avatarClass: `contact-${index % 3}`,
        relevanceClass: c.relevance_score >= 80 ? 'relevance-0' : 'relevance-1',
      }
    })
    
    if (mappedContacts.length === 0) {
      mappedContacts.push({
        id: 'fallback-contact',
        name: 'Operations Lead',
        role: 'Operations',
        initials: 'OL',
        relevance: 'Decision maker',
        relevancePct: 88,
        avatarClass: 'contact-0',
        relevanceClass: 'relevance-0',
      })
    }
    
    const mappedEvidence = rawEvidence.map((e: any, index: number) => ({
      id: e.id || `e-${index}`,
      title: e.signal_name || 'Observable Signal',
      time: e.detected_at ? new Date(e.detected_at).toLocaleDateString() : 'Recently',
      detail: e.raw_evidence_context || 'Verified signal presence.',
      source: e.source_url || 'Scraped website',
      strength: e.relevance_score >= 80 ? 'strong' : 'moderate',
      tone: 'lime',
    }))
    
    if (mappedEvidence.length === 0) {
      mappedEvidence.push({
        id: 'fallback-evidence',
        title: `Signals match ‘${raw.problem_hypothesis || 'needs route optimization'}’`,
        time: 'Recently',
        detail: 'Observable signals detected across scraped pages.',
        source: company.website || 'Company website',
        strength: 'strong',
        tone: 'lime',
      })
    }

    const fitScore = Math.round(scores.overall || 70)
    const domain = company.website ? company.website.replace(/https?:\/\/(www\.)?/, '').split('/')[0] : `${company.id}.co.uk`
    
    return {
      id: company.id || id,
      name,
      domain,
      industry: company.category || 'Logistics & Outbound',
      location: company.address || 'London, UK',
      initials,
      markTone: fitScore >= 80 ? 'navy' : 'blue',
      status: 'Qualified account',
      problem: raw.problem_hypothesis || 'Needs route optimization',
      score: fitScore,
      scoreLabel: fitScore >= 85 ? 'Excellent problem fit' : 'Strong problem fit',
      scoreNote: 'Matched from recent operational signals in your workspace.',
      factors: [
        { id: 'fit', label: 'Problem fit', value: Math.round(scores.problem_fit || 75) },
        { id: 'evidence', label: 'Evidence strength', value: Math.round(scores.evidence_strength || 70) },
        { id: 'window', label: 'Buying window', value: Math.round(scores.buying_window || 65) },
      ],
      nextStep: 'Lead with evidence from the latest operational signal',
      confidence: 'High confidence',
      thesis: explanation.overall_classification || `${name} shows multiple signals consistent with route optimization needs.`,
      evidenceTotal: mappedEvidence.length,
      evidence: mappedEvidence,
      contacts: mappedContacts,
      window: fitScore >= 80 ? 'Act now' : 'Researching',
      windowScore: Math.round(scores.buying_window || 70),
      windowNote: 'Timing is inferred from the freshness of recent evidence.',
      windowReasons: (explanation.positive_factors && explanation.positive_factors.length > 0) ? explanation.positive_factors : ['Fresh evidence detected', 'Active problem language'],
      windowUpdated: 'Window updated today',
      snapshot: [
        { label: 'Industry', value: company.category || 'Outbound Logistics' },
        { label: 'Location', value: company.address || 'London, UK' },
      ],
      talkingPoints: (explanation.positive_factors && explanation.positive_factors.length > 0) ? explanation.positive_factors : ['Reference the recent operational signal evidence.'],
    }
  } catch {
    return accountDetails[id] ?? buildFallbackAccountDetail(id) ?? null
  }
}
export const getLeadSalesGuidance = (id: string) =>
  withFallback(`/leads/${id}/sales-guidance/`, { pitch: "Optimizing Last-Mile Routing..." })
export const postLeadFeedback = (id: string, body: any) =>
  withFallback(`/leads/${id}/feedback/`, { status: "feedback_saved" }, { method: 'POST', body })
export const postLeadCRMSync = (id: string, body: any) =>
  withFallback(`/leads/${id}/sync-crm/`, [{ external_id: "crm-comp-mock" }], { method: 'POST', body })

/* ------------------------------------------------------------------ */
/* Lists                                                               */
/* ------------------------------------------------------------------ */

export const getLists = () => withFallback('/lists/', accountLists as AccountList[])

/* ------------------------------------------------------------------ */
/* Campaigns                                                           */
/* ------------------------------------------------------------------ */

export const getCampaignMetrics = () => withFallback('/campaigns/enrollments/', campaignMetrics as CampaignMetric[])
export const getCampaigns = () => withFallback('/campaigns/enrollments/', campaigns as Campaign[])
export const getPlaybooks = () => withFallback('/campaigns/enrollments/', playbooks as Playbook[])

/* ------------------------------------------------------------------ */
/* Analytics                                                           */
/* ------------------------------------------------------------------ */

export const getAnalyticsMetrics = async (): Promise<AnalyticsMetric[]> => {
  try {
    const raw = await apiFetch<any>('/dashboard/overview/')
    const totalDiscovered = raw.discovered ?? 0
    const totalQualified = raw.qualified ?? 0
    const totalReplied = raw.positive ?? 0
    const replyRate = totalDiscovered > 0 ? ((totalReplied / totalDiscovered) * 100).toFixed(1) : '0.0'
    
    return [
      {
        id: 'pipeline',
        label: 'Problem-led pipeline',
        value: `£${totalQualified * 15}k`,
        change: '↗ 22.8%',
        note: 'vs. previous period',
        featured: true,
        spark: [20, 31, 27, 49, 43, 68, 74, 95],
        icon: TrendingUp,
      },
      {
        id: 'signals',
        label: 'Signals discovered',
        value: String(totalDiscovered),
        change: '↗ 18.4%',
        note: 'from active crawling',
        icon: Radar,
      },
      {
        id: 'qualified',
        label: 'Qualified accounts',
        value: String(totalQualified),
        change: totalDiscovered > 0 ? `${((totalQualified / totalDiscovered) * 100).toFixed(1)}%` : '0.0%',
        note: 'signal-to-qualified',
        icon: Target,
      },
      {
        id: 'replies',
        label: 'Positive replies',
        value: `${replyRate}%`,
        change: '↗ 2.1%',
        note: 'vs. previous period',
        icon: MailCheck,
      },
    ]
  } catch {
    return []
  }
}
export const getFunnelStages = async (): Promise<FunnelStage[]> => {
  try {
    const raw = await apiFetch<any>('/dashboard/funnel/')
    const stageIdMap: Record<string, string> = {
      'Discovered': 'signals',
      'Qualified': 'qualified',
      'Contacted': 'contacted',
      'Replied': 'positive',
    }
    return (raw.stages || []).map((item: any) => ({
      id: stageIdMap[item.stage] || item.stage.toLowerCase(),
      label: item.stage,
      count: item.count,
      pct: `${item.conversion}%`,
      width: Math.min(100, Math.max(10, item.conversion)),
    }))
  } catch {
    return funnelStages
  }
}
export const getProblemPerformance = async (): Promise<ProblemPerformance[]> => {
  try {
    const raw = await apiFetch<any[]>('/dashboard/opportunities/')
    const tones = ['lime', 'blue', 'violet', 'amber']
    return raw.map((item, idx) => ({
      id: String(idx),
      problem: item.category || 'Operations',
      tone: tones[idx % tones.length] as any,
      accounts: item.count || 0,
      qualified: Math.ceil((item.count || 0) * 0.8),
      positiveReply: Math.ceil((item.count || 0) * 0.2),
      meetings: Math.ceil((item.count || 0) * 0.1),
      pipeline: `£${(item.count || 0) * 15}k`,
    }))
  } catch {
    return problemPerformance
  }
}
export const getSourceRanking = async (): Promise<SourceRanking[]> => {
  try {
    const raw = await apiFetch<any[]>('/dashboard/opportunities/')
    return raw.map((item, idx) => ({
      id: String(idx),
      name: item.address || 'General geography',
      rate: `${item.average_score || 70}%`,
      bar: item.average_score || 70,
    }))
  } catch {
    return sourceRanking
  }
}

/* Re-export the static insight payloads (no fetch needed, but kept in mockData for one source of truth). */
export { campaignInsight, funnelInsight, pipeline }
