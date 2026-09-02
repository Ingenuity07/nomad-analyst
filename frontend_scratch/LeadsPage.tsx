import { useMemo, useState, Fragment, type ReactNode } from 'react'
import {
  ArrowRight,
  Check,
  ChevronDown,
  Download,
  Search,
  Target,
  Users,
  UsersRound,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { getLeads, getLeadKpis } from '../api/dashboard'
import { useAsyncData } from '../hooks/useAsyncData'
import type { BuyingWindow, LeadKpi, LeadRow } from '../types'

const PAGE_SIZE = 6

const kpiIcon: Record<LeadKpi['id'], LucideIcon> = {
  total: UsersRound,
  'high-fit': Target,
  'act-now': Zap,
  unassigned: Users,
}

const windowClass: Record<BuyingWindow, string> = {
  'Act now': 'window-hot',
  'This quarter': 'window-warm',
  'This month': 'window-hot',
  Researching: 'window-cool',
  Monitoring: 'window-neutral',
  'Next quarter': 'window-neutral',
}

const problemOptions = [
  'Manual route planning',
  'Scheduling bottlenecks',
  'Poor delivery visibility',
  'Last-mile margin pressure',
  'Unplanned fleet downtime',
]

function downloadLeads(leads: LeadRow[]) {
  const header = ['Account', 'Industry', 'Location', 'Problem', 'Fit score', 'Buying window']
  const body = leads.map((lead) => [
    lead.name,
    lead.industry,
    lead.location,
    lead.problem,
    lead.fitScore,
    lead.window,
  ])
  const csv = [header, ...body]
    .map((row) => row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'nomad-leads.csv'
  link.click()
  URL.revokeObjectURL(url)
}

export function LeadsPage() {
  const { data: leadsList } = useAsyncData(getLeads, [])
  const { data: kpisList } = useAsyncData(getLeadKpis, [])

  const [query, setQuery] = useState('')
  const [problem, setProblem] = useState('All problems')
  const [minScore, setMinScore] = useState('All scores')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(1)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return leadsList.filter((lead) => {
      const matchesQuery =
        !q || `${lead.name} ${lead.industry} ${lead.location}`.toLowerCase().includes(q)
      const matchesProblem = problem === 'All problems' || lead.problem === problem
      const matchesScore = minScore === 'All scores' || lead.fitScore >= Number(minScore)
      return matchesQuery && matchesProblem && matchesScore
    })
  }, [query, problem, minScore, leadsList])

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE))
  const safePage = Math.min(page, pageCount)
  const pageItems = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE)

  const groupedPageItems = useMemo(() => {
    const groups: Array<{ id: string; keyword: string; location: string; items: LeadRow[] }> = []
    pageItems.forEach((lead) => {
      const runId = lead.discoveryRunId || 'manual'
      const keyword = lead.discoveryRunKeyword || 'Manual / Imported Leads'
      const loc = lead.discoveryRunLocation || ''

      let group = groups.find((g) => g.id === runId)
      if (!group) {
        group = { id: runId, keyword, location: loc, items: [] }
        groups.push(group)
      }
      group.items.push(lead)
    })
    return groups
  }, [pageItems])

  const allChecked = pageItems.length > 0 && pageItems.every((lead) => selected.has(lead.id))

  const toggleRow = (id: string) => {
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    setSelected((current) => {
      const next = new Set(current)
      if (allChecked) pageItems.forEach((lead) => next.delete(lead.id))
      else pageItems.forEach((lead) => next.add(lead.id))
      return next
    })
  }

  return (
    <div className="page page-enter leads-page">
      <header className="page-header">
        <div className="page-heading-copy">
          <span className="page-eyebrow">Qualified accounts</span>
          <h1>Leads with a reason to buy.</h1>
          <p>
            Every account is ranked by problem fit, the evidence we found, and how soon they
            might buy — so your team knows who to contact and why.
          </p>
        </div>
        <div className="page-actions">
          <button
            className="button button-secondary"
            type="button"
            onClick={() => downloadLeads(filtered)}
            disabled={filtered.length === 0}
          >
            <Download size={14} /> Export
          </button>
          <Link to="/discover" className="button button-primary">
            Find more leads
          </Link>
        </div>
      </header>

      <section className="lead-kpi-strip card">
        {kpisList.map((kpi, index) => {
          const Icon = kpiIcon[kpi.id] || UsersRound
          return (
            <ReactFragment key={kpi.id} index={index}>
              <div>
                {index === 0 && (
                  <span className="kpi-symbol">
                    <Icon size={16} />
                  </span>
                )}
                <p>
                  <small>{kpi.label}</small>
                  <strong>{kpi.value}</strong>
                  {kpi.note && (
                    <span className={kpi.tone === 'hot' ? 'hot-text' : kpi.tone === 'up' ? 'tiny-trend' : ''}>
                      {kpi.note}
                    </span>
                  )}
                </p>
              </div>
            </ReactFragment>
          )
        })}
      </section>

      <section className="lead-directory card">
        <div className="lead-toolbar">
          <label className="lead-search">
            <Search size={14} />
            <input
              value={query}
              onChange={(event) => {
                setQuery(event.target.value)
                setPage(1)
              }}
              placeholder="Search account, industry, or location…"
              aria-label="Search accounts"
            />
          </label>
          <label className="toolbar-select">
            <select
              value={problem}
              onChange={(event) => {
                setProblem(event.target.value)
                setPage(1)
              }}
              aria-label="Filter by problem"
            >
              {['All problems', ...problemOptions].map((option) => (
                <option key={option}>{option}</option>
              ))}
            </select>
            <ChevronDown size={12} />
          </label>
          <label className="toolbar-select">
            <select
              value={minScore}
              onChange={(event) => {
                setMinScore(event.target.value)
                setPage(1)
              }}
              aria-label="Filter by score"
            >
              <option>All scores</option>
              <option value="85">85+ fit</option>
              <option value="80">80+ fit</option>
              <option value="75">75+ fit</option>
            </select>
            <ChevronDown size={12} />
          </label>
          <span className="toolbar-count">
            {filtered.length} of {leadsList.length} accounts
          </span>
        </div>

        <div className="table-wrap lead-table-wrap">
          <table className="data-table lead-table">
            <thead>
              <tr>
                <th className="check-cell">
                  <button className={`table-check ${allChecked ? 'checked' : ''}`} onClick={toggleAll} aria-label="Select all">
                    {allChecked && <Check size={11} strokeWidth={3} />}
                  </button>
                </th>
                <th>Account</th>
                <th>Operational problem</th>
                <th>Evidence</th>
                <th>Buying window</th>
                <th>Fit score</th>
                <th>Owner</th>
                <th>Last signal</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {groupedPageItems.map((group) => (
                <Fragment key={group.id}>
                  {/* Group Header Separator Row */}
                  <tr className="table-group-header" style={{ backgroundColor: 'rgba(var(--primary-rgb, 142, 172, 80), 0.05)', fontWeight: 'bold' }}>
                    <td colSpan={9} style={{ padding: '10px 16px', fontSize: '12px', color: 'var(--text-muted, #6b7280)', borderBottom: '1px solid var(--border)' }}>
                      📁 Discovery Run: <strong style={{ color: 'var(--text)' }}>{group.keyword}</strong> {group.location ? `(${group.location})` : ''}
                    </td>
                  </tr>
                  {group.items.map((lead) => {
                    const checked = selected.has(lead.id)
                    return (
                      <tr key={lead.id}>
                        <td className="check-cell">
                          <button
                            className={`table-check ${checked ? 'checked' : ''}`}
                            onClick={() => toggleRow(lead.id)}
                            aria-label={`Select ${lead.name}`}
                          >
                            {checked && <Check size={11} strokeWidth={3} />}
                          </button>
                        </td>
                        <td>
                          <Link to={`/leads/${lead.id}`} className="company-cell lead-company">
                            <span className={`company-mark mark-${lead.markTone} mark-normal`} aria-hidden="true">
                              {lead.initials}
                            </span>
                            <span>
                              <strong>{lead.name}</strong>
                              <small>
                                {lead.industry} · {lead.location}
                              </small>
                            </span>
                          </Link>
                        </td>
                        <td>
                          <span className="problem-tag">{lead.problem}</span>
                        </td>
                        <td>
                          <span className="signal-count">
                            <i>{lead.signals}</i>
                            <span>
                              <strong>{lead.signals} signals</strong>
                              <small>{lead.sources} sources</small>
                            </span>
                          </span>
                        </td>
                        <td>
                          <span className={`window-badge ${windowClass[lead.window]}`}>{lead.window}</span>
                        </td>
                        <td>
                          <span className={`score-badge ${lead.fitScore >= 85 ? 'score-high' : 'score-good'}`}>
                            {lead.fitScore}
                          </span>
                        </td>
                        <td>
                          <span className={`owner-pill ${lead.unassigned ? 'unassigned' : ''}`}>
                            <i>{lead.ownerInitials}</i>
                            {lead.owner}
                          </span>
                        </td>
                        <td>
                          <span className="last-seen">{lead.lastSeen}</span>
                        </td>
                        <td>
                          <Link to={`/leads/${lead.id}`} className="icon-button mini" aria-label={`Open ${lead.name}`}>
                            <ArrowRight size={14} />
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
                </Fragment>
              ))}
            </tbody>
          </table>
          {filtered.length === 0 && (
            <div className="table-empty">
              <p>No accounts match your search.</p>
            </div>
          )}
        </div>

        <div className="table-footer">
          <span>
            Showing {filtered.length === 0 ? 0 : (safePage - 1) * PAGE_SIZE + 1}–
            {Math.min(safePage * PAGE_SIZE, filtered.length)} of {filtered.length}
          </span>
          <div>
            <button type="button" disabled={safePage === 1} onClick={() => setPage(safePage - 1)}>
              Previous
            </button>
            {Array.from({ length: pageCount }, (_, i) => i + 1).map((number) => (
              <button
                key={number}
                type="button"
                className={safePage === number ? 'current' : ''}
                onClick={() => setPage(number)}
              >
                {number}
              </button>
            ))}
            <button type="button" disabled={safePage === pageCount} onClick={() => setPage(safePage + 1)}>
              Next
            </button>
          </div>
        </div>
      </section>
    </div>
  )
}

function ReactFragment({ index, children }: { index: number; children: ReactNode }) {
  return (
    <>
      {index > 0 && <i />}
      {children}
    </>
  )
}
