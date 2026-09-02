import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ArrowRight, Check, MapPin, Radar, Sparkles, RefreshCw, X, ChevronRight, HelpCircle } from 'lucide-react'
import { Link } from 'react-router-dom'
import {
  postIntake,
  getIntakeDetail,
  getDiscoveryRunStatus,
  postIntakeClarify,
  patchIntakeSpecification,
  postIntakeConfirm,
  postIntakeCancel
} from '../api/dashboard'
import { DISCOVER } from '../constants'
import type { DiscoveryRun, DiscoveryStageId } from '../types'
import type { IntakeRequest, SpecificationVersion, ProspectingSpecification } from '../types/intake'

const MOCK_SUMMARY = { discovered: 12, new: 9, duplicates: 3 }
const STAGE_ORDER: DiscoveryStageId[] = DISCOVER.runStages.map((step) => step.stage)

export function DiscoverPage() {
  const [sell, setSell] = useState('')
  const [problem, setProblem] = useState('')
  const [location, setLocation] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [run, setRun] = useState<DiscoveryRun | null>(null)
  const [runMetrics, setRunMetrics] = useState<{ discovered: number; new: number; duplicates: number } | null>(null)
  
  // Intake specific state
  const [intake, setIntake] = useState<IntakeRequest | null>(null)
  const [version, setVersion] = useState<SpecificationVersion | null>(null)
  const [clarificationAnswer, setClarificationAnswer] = useState('')
  const [editedSpec, setEditedSpec] = useState<ProspectingSpecification | null>(null)
  const [activeTab, setActiveTab] = useState<'review' | 'raw'>('review')

  const timers = useRef<number[]>([])

  useEffect(() => () => timers.current.forEach((id) => window.clearTimeout(id)), [])

  // Poll intake status when in PARSING state
  useEffect(() => {
    if (!intake || intake.status !== 'PARSING') return

    let active = true
    const pollId = window.setInterval(async () => {
      try {
        const response = await getIntakeDetail(intake.id)
        if (!active) return

        // Update intake request state
        setIntake(response.request)
        
        // Find latest spec version if it exists
        if (response.versions && response.versions.length > 0) {
          const sorted = [...response.versions].sort((a, b) => b.version - a.version)
          const latest = sorted[0]
          setVersion(latest)
          setEditedSpec(latest.specification_json)
        }

        // Stop polling if status is no longer PARSING
        if (response.request.status !== 'PARSING') {
          window.clearInterval(pollId)
        }
      } catch (err: any) {
        console.error("Polling failed:", err)
      }
    }, 2000)

    return () => {
      active = false
      window.clearInterval(pollId)
    }
  }, [intake])

  // Poll discovery run status when in running state
  useEffect(() => {
    if (!run || run.status !== 'running') return

    let active = true
    const pollId = window.setInterval(async () => {
      try {
        const response = await getDiscoveryRunStatus(run.runId)
        if (!active) return

        setRun((current) => {
          if (!current) return null
          return {
            ...current,
            status: response.status === 'completed' ? 'completed' : (response.status === 'failed' ? 'failed' : 'running'),
            progress: response.progress,
            stage: response.stage as DiscoveryStageId
          }
        })

        if (response.status === 'completed' || response.status === 'failed') {
          if (response.metrics) {
            setRunMetrics({
              discovered: response.metrics.discovered,
              new: response.metrics.new,
              duplicates: response.metrics.duplicates
            })
          }
          window.clearInterval(pollId)
        }
      } catch (err: any) {
        console.error("Discovery run status polling failed:", err)
      }
    }, 7000)

    return () => {
      active = false
      window.clearInterval(pollId)
    }
  }, [run])

  const startRun = (runId: string, keyword: string, place: string) => {
    setRun({ runId, keyword, location: place, status: 'running', progress: 5, stage: 'queued' })
    setRunMetrics(null)
  }

  const submitIntake = async (event: FormEvent) => {
    event.preventDefault()
    const objectiveText = problem.trim()
    const targetText = sell.trim()
    const locationText = location.trim()

    if (!objectiveText) {
      setError(DISCOVER.problemRequired)
      return
    }
    if (!locationText) {
      setError(DISCOVER.locationRequired)
      return
    }
    setError('')
    setSubmitting(true)

    try {
      const response = await postIntake({
        objective: objectiveText,
        target: targetText,
        qualification: `Located in or targeting: ${locationText}`
      })
      setIntake(response.request)
      setVersion(null)
      setEditedSpec(null)
    } catch (err: any) {
      setError(err?.message || 'Failed to submit prospecting request. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const submitClarification = async (event: FormEvent) => {
    event.preventDefault()
    if (!intake || !clarificationAnswer.trim()) return
    setError('')
    setSubmitting(true)

    try {
      const lastQuestion = intake.clarification_history[intake.clarification_history.length - 1]?.question || 
        "Please clarify details regarding your missing target criteria."
      
      const response = await postIntakeClarify(intake.id, {
        question: lastQuestion,
        answer: clarificationAnswer.trim()
      })
      setIntake(response.request)
      setVersion(null)
      setEditedSpec(null)
      setClarificationAnswer('')
    } catch (err: any) {
      setError(err?.message || 'Failed to submit clarification. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const saveSpecificationDraft = async () => {
    if (!intake || !editedSpec) return
    setError('')
    setSubmitting(true)

    try {
      const response = await patchIntakeSpecification(intake.id, {
        specification_json: editedSpec
      })
      setIntake(response.request)
      setVersion(response.specification_version)
      if (response.specification_version) {
        setEditedSpec(response.specification_version.specification_json)
      }
      alert('Specification draft saved successfully.')
    } catch (err: any) {
      setError(err?.message || 'Failed to save specification draft.')
    } finally {
      setSubmitting(false)
    }
  }

  const confirmAndLaunch = async () => {
    if (!intake || !version) return
    setError('')
    setSubmitting(true)

    try {
      const response = await postIntakeConfirm(intake.id, {
        version: version.version
      })
      const keyword = editedSpec?.target.description.value || editedSpec?.objective.value || problem
      const place = location || "Leeds"
      
      startRun(response.discovery.id || 'run-1', keyword, place)
    } catch (err: any) {
      setError(err?.message || 'Failed to confirm and launch discovery.')
    } finally {
      setSubmitting(false)
    }
  }

  const cancelIntake = async () => {
    if (!intake) return
    if (!confirm('Are you sure you want to cancel this prospecting session?')) return
    try {
      await postIntakeCancel(intake.id)
      reset()
    } catch (err: any) {
      setError(err?.message || 'Failed to cancel request.')
    }
  }

  const reset = () => {
    timers.current.forEach((id) => window.clearTimeout(id))
    timers.current = []
    setRun(null)
    setIntake(null)
    setVersion(null)
    setEditedSpec(null)
    setSell('')
    setProblem('')
    setLocation('')
    setError('')
  }

  return (
    <div className="page page-enter">
      <header className="page-header">
        <div className="page-heading-copy">
          <span className="page-eyebrow">{DISCOVER.eyebrow}</span>
          <h1>{DISCOVER.title}</h1>
          <p>{DISCOVER.description}</p>
        </div>
      </header>

      {run && <RunPanel run={run} metrics={runMetrics} onReset={reset} />}

      {!run && !intake && (
        <form className="discovery-layout" onSubmit={submitIntake} noValidate>
          <section className="card discovery-card">
            <h2>Start a discovery</h2>
            <p>{DISCOVER.intro}</p>

            {error && <div className="discovery-error">{error}</div>}

            <div className="discovery-field">
              <label htmlFor="discovery-sell">
                {DISCOVER.sellLabel} <span>{DISCOVER.sellOptional}</span>
              </label>
              <input
                id="discovery-sell"
                className="discovery-input"
                value={sell}
                onChange={(event) => setSell(event.target.value)}
                placeholder={DISCOVER.sellPlaceholder}
              />
              <span className="discovery-hint">{DISCOVER.sellHint}</span>
              <div className="discovery-examples">
                {DISCOVER.sellExamples.map((example) => (
                  <button key={example} type="button" onClick={() => setSell(example)}>
                    {example}
                  </button>
                ))}
              </div>
            </div>

            <div className="discovery-field">
              <label htmlFor="discovery-problem">
                What problem do your customers have? <span>(required)</span>
              </label>
              <textarea
                id="discovery-problem"
                className="discovery-input"
                value={problem}
                onChange={(event) => setProblem(event.target.value)}
                placeholder="Describe their operational problem, e.g. Courier dispatchers spend hours manually building routes"
              />
              <span className="discovery-hint">Explain the objective and pain points in natural language.</span>
              <div className="discovery-examples">
                {DISCOVER.problemExamples.map((example) => (
                  <button key={example} type="button" onClick={() => setProblem(example)}>
                    {example}
                  </button>
                ))}
              </div>
            </div>

            <div className="discovery-field">
              <label htmlFor="discovery-location">
                Where are they based? <span>(required)</span>
              </label>
              <div style={{ position: 'relative' }}>
                <MapPin
                  size={16}
                  style={{ position: 'absolute', left: 14, top: '50%', transform: 'translateY(-50%)', color: 'var(--muted-2)' }}
                />
                <input
                  id="discovery-location"
                  className="discovery-input"
                  style={{ paddingLeft: 40 }}
                  value={location}
                  onChange={(event) => setLocation(event.target.value)}
                  placeholder="e.g. West Yorkshire, Leeds, or UK"
                />
              </div>
              <div className="discovery-examples">
                {DISCOVER.locationExamples.map((example) => (
                  <button key={example} type="button" onClick={() => setLocation(example)}>
                    {example}
                  </button>
                ))}
              </div>
            </div>

            <button className="button button-primary discovery-submit" type="submit" disabled={submitting}>
              {submitting ? <RefreshCw className="button-spinner animate-spin" size={16} /> : <Radar size={16} />}
              {submitting ? 'Analyzing Intent...' : 'Submit Intent'}
            </button>
          </section>

          <aside className="card discovery-steps">
            <h3>
              <Sparkles size={15} style={{ verticalAlign: -2, marginRight: 6, color: 'var(--lime-dark)' }} />
              {DISCOVER.howTitle}
            </h3>
            <ol>
              {DISCOVER.howSteps.map((step) => (
                <li key={step.title}>
                  <div>
                    <strong>{step.title}</strong>
                    <small>{step.detail}</small>
                  </div>
                </li>
              ))}
            </ol>
          </aside>
        </form>
      )}

      {/* NEEDS_CLARIFICATION SCREEN */}
      {!run && intake && intake.status === 'NEEDS_CLARIFICATION' && (
        <form className="discovery-layout" onSubmit={submitClarification}>
          <section className="card discovery-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--amber-dark)', marginBottom: 16 }}>
              <HelpCircle size={20} />
              <h2>Clarification Needed</h2>
            </div>
            
            <p style={{ color: 'var(--text-muted)', marginBottom: 20 }}>
              The intent parser requires more details to structure a high-quality specification.
            </p>

            {error && <div className="discovery-error">{error}</div>}

            <div className="discovery-field" style={{ background: 'rgba(245, 158, 11, 0.06)', border: '1px solid rgba(245, 158, 11, 0.15)', borderRadius: 12, padding: 16, marginBottom: 20 }}>
              <strong style={{ display: 'block', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--amber-dark)', marginBottom: 6 }}>
                Question from AI intake architect:
              </strong>
              <p style={{ fontSize: '1rem', lineHeight: 1.5 }}>
                {intake.clarification_history[intake.clarification_history.length - 1]?.question || "Could you specify the target audience size or business sector in more detail?"}
              </p>
            </div>

            <div className="discovery-field">
              <label htmlFor="clarification-answer">Your Answer</label>
              <textarea
                id="clarification-answer"
                className="discovery-input"
                value={clarificationAnswer}
                onChange={(e) => setClarificationAnswer(e.target.value)}
                placeholder="Type your response here..."
                required
              />
            </div>

            <div style={{ display: 'flex', gap: 12 }}>
              <button className="button button-primary" type="submit" disabled={submitting}>
                {submitting ? <RefreshCw className="button-spinner animate-spin" size={16} /> : <ChevronRight size={16} />}
                {submitting ? 'Parsing Answer...' : 'Submit Answer'}
              </button>
              <button className="button button-secondary" type="button" onClick={cancelIntake}>
                Cancel Session
              </button>
            </div>
          </section>

          <aside className="card discovery-steps">
            <h3>Clarification History</h3>
            {intake.clarification_history.length <= 1 ? (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No history items yet.</p>
            ) : (
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 16 }}>
                {intake.clarification_history.slice(0, -1).map((item, idx) => (
                  <li key={idx} style={{ fontSize: '0.85rem', borderBottom: '1px solid var(--glass-border)', paddingBottom: 10 }}>
                    <div style={{ color: 'var(--text-muted)', marginBottom: 4 }}>Q: {item.question}</div>
                    <div style={{ fontWeight: 500 }}>A: {item.answer}</div>
                  </li>
                ))}
              </ul>
            )}
          </aside>
        </form>
      )}

      {/* PARSING LOADING PANEL */}
      {!run && intake && intake.status === 'PARSING' && (
        <section className="card discovery-run" style={{ textAlign: 'center', padding: '60px 40px' }}>
          <RefreshCw className="animate-spin text-primary" size={32} style={{ margin: '0 auto 20px auto', color: 'var(--primary)' }} />
          <h2>Parsing Specification...</h2>
          <p style={{ color: 'var(--text-muted)', marginTop: 8 }}>
            The AI parser is structuring your campaigns goals into validated criteria. This takes a few seconds.
          </p>
        </section>
      )}

      {/* READY_FOR_REVIEW SPECIFICATION SCREEN */}
      {!run && intake && intake.status === 'READY_FOR_REVIEW' && editedSpec && version && (
        <div className="discovery-layout">
          <section className="card discovery-card" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <span className="discovery-run-id" style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#34d399', padding: '4px 10px', borderRadius: 9999, fontSize: '0.75rem', fontWeight: 600 }}>
                  Ready for Review (Version {version.version})
                </span>
                <h2 style={{ marginTop: 8 }}>Review Prospecting Specification</h2>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  className={`button button-secondary ${activeTab === 'review' ? 'active' : ''}`}
                  onClick={() => setActiveTab('review')}
                  style={{ background: activeTab === 'review' ? 'rgba(255,255,255,0.08)' : 'transparent', padding: '6px 12px', fontSize: '0.85rem' }}
                >
                  Edit Spec
                </button>
                <button
                  className={`button button-secondary ${activeTab === 'raw' ? 'active' : ''}`}
                  onClick={() => setActiveTab('raw')}
                  style={{ background: activeTab === 'raw' ? 'rgba(255,255,255,0.08)' : 'transparent', padding: '6px 12px', fontSize: '0.85rem' }}
                >
                  Raw Objective
                </button>
              </div>
            </div>

            {error && <div className="discovery-error">{error}</div>}

            {activeTab === 'raw' ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={{ background: 'rgba(255,255,255,0.02)', padding: 16, borderRadius: 8, border: '1px solid var(--glass-border)' }}>
                  <strong style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Original Objective:</strong>
                  <p style={{ marginTop: 6, lineHeight: 1.5 }}>{intake.raw_objective}</p>
                </div>
                {intake.raw_target && (
                  <div style={{ background: 'rgba(255,255,255,0.02)', padding: 16, borderRadius: 8, border: '1px solid var(--glass-border)' }}>
                    <strong style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Original Target:</strong>
                    <p style={{ marginTop: 6, lineHeight: 1.5 }}>{intake.raw_target}</p>
                  </div>
                )}
                <div style={{ display: 'flex', gap: 10, marginTop: 10 }}>
                  <button className="button button-secondary" onClick={() => setActiveTab('review')}>
                    Back to Edit Spec
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {/* 1. Objective type & explanation */}
                <div className="discovery-field">
                  <label htmlFor="spec-objective-type">Campaign Intent / Objective Category</label>
                  <select
                    id="spec-objective-type"
                    className="discovery-input"
                    style={{ background: 'var(--bg-color)', color: 'var(--text-main)' }}
                    value={editedSpec.objective_type.value}
                    onChange={(e) => setEditedSpec({
                      ...editedSpec,
                      objective_type: { value: e.target.value, provenance: 'USER_CONFIRMED' }
                    })}
                  >
                    <option value="SELL">Direct sales outreach (SELL)</option>
                    <option value="SERVICE">Offer services (SERVICE)</option>
                    <option value="PARTNERSHIP">Partnership discovery (PARTNERSHIP)</option>
                    <option value="SUPPLIER_SEARCH">Supplier sourcing (SUPPLIER_SEARCH)</option>
                    <option value="RECRUITING">Recruiting/Talent search (RECRUITING)</option>
                    <option value="MARKET_RESEARCH">Market research (MARKET_RESEARCH)</option>
                    <option value="COMPETITIVE_RESEARCH">Competitive analysis (COMPETITIVE_RESEARCH)</option>
                    <option value="INVESTMENT_RESEARCH">Investment sourcing (INVESTMENT_RESEARCH)</option>
                    <option value="OTHER">Other custom workflow (OTHER)</option>
                  </select>
                </div>

                {/* 2. Text Target Description */}
                <div className="discovery-field">
                  <label htmlFor="spec-target-desc">Derived Target Profile Description</label>
                  <input
                    id="spec-target-desc"
                    className="discovery-input"
                    value={editedSpec.target.description.value}
                    onChange={(e) => setEditedSpec({
                      ...editedSpec,
                      target: {
                        ...editedSpec.target,
                        description: { value: e.target.value, provenance: 'USER_CONFIRMED' }
                      }
                    })}
                  />
                </div>

                {/* 3. Target categories */}
                <TagEditor
                  label="Target Directory Categories (used by OpenStreetMap/Nominatim)"
                  tags={editedSpec.target.categories.value}
                  onChange={(newTags) => setEditedSpec({
                    ...editedSpec,
                    target: {
                      ...editedSpec.target,
                      categories: { value: newTags, provenance: 'USER_CONFIRMED' }
                    }
                  })}
                  placeholder="e.g. Logistics, Courier, Delivery service"
                />

                {/* 4. Geography countries and cities */}
                <TagEditor
                  label="Target Countries"
                  tags={editedSpec.geography.countries.value}
                  onChange={(newTags) => setEditedSpec({
                    ...editedSpec,
                    geography: {
                      ...editedSpec.geography,
                      countries: { value: newTags, provenance: 'USER_CONFIRMED' }
                    }
                  })}
                  placeholder="e.g. United Kingdom, Canada"
                />

                <TagEditor
                  label="Target Cities"
                  tags={editedSpec.geography.cities.value}
                  onChange={(newTags) => setEditedSpec({
                    ...editedSpec,
                    geography: {
                      ...editedSpec.geography,
                      cities: { value: newTags, provenance: 'USER_CONFIRMED' }
                    }
                  })}
                  placeholder="e.g. Leeds, Manchester"
                />

                {/* 5. Company Constraints min/max employees */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                  <div className="discovery-field">
                    <label htmlFor="spec-min-emp">Min Employees</label>
                    <input
                      id="spec-min-emp"
                      type="number"
                      className="discovery-input"
                      value={editedSpec.company_constraints.min_employees.value ?? ''}
                      onChange={(e) => setEditedSpec({
                        ...editedSpec,
                        company_constraints: {
                          ...editedSpec.company_constraints,
                          min_employees: { value: e.target.value ? parseInt(e.target.value) : null, provenance: 'USER_CONFIRMED' }
                        }
                      })}
                      placeholder="No limit"
                    />
                  </div>
                  <div className="discovery-field">
                    <label htmlFor="spec-max-emp">Max Employees</label>
                    <input
                      id="spec-max-emp"
                      type="number"
                      className="discovery-input"
                      value={editedSpec.company_constraints.max_employees.value ?? ''}
                      onChange={(e) => setEditedSpec({
                        ...editedSpec,
                        company_constraints: {
                          ...editedSpec.company_constraints,
                          max_employees: { value: e.target.value ? parseInt(e.target.value) : null, provenance: 'USER_CONFIRMED' }
                        }
                      })}
                      placeholder="No limit"
                    />
                  </div>
                </div>

                {/* 6. Target Buyer Roles */}
                <TagEditor
                  label="Target Decision Maker Roles"
                  tags={editedSpec.people_constraints.roles.value}
                  onChange={(newTags) => setEditedSpec({
                    ...editedSpec,
                    people_constraints: {
                      ...editedSpec.people_constraints,
                      roles: { value: newTags, provenance: 'USER_CONFIRMED' }
                    }
                  })}
                  placeholder="e.g. Operations Director, Dispatch Manager"
                />

                {/* 7. Exclusions */}
                <TagEditor
                  label="Exclusion Keywords / Rules"
                  tags={editedSpec.exclusion_rules.value}
                  onChange={(newTags) => setEditedSpec({
                    ...editedSpec,
                    exclusion_rules: { value: newTags, provenance: 'USER_CONFIRMED' }
                  })}
                  placeholder="e.g. Freelancers, Consultant"
                />

                <div style={{ display: 'flex', gap: 12, marginTop: 10 }}>
                  <button className="button button-primary" type="button" onClick={confirmAndLaunch} disabled={submitting}>
                    {submitting ? <RefreshCw className="button-spinner animate-spin" size={16} /> : <Radar size={16} />}
                    Confirm & Launch
                  </button>
                  <button className="button button-secondary" type="button" onClick={saveSpecificationDraft} disabled={submitting}>
                    Save Draft
                  </button>
                  <button className="button button-secondary" type="button" style={{ color: 'var(--rose-dark)' }} onClick={cancelIntake} disabled={submitting}>
                    Cancel Session
                  </button>
                </div>
              </div>
            )}
          </section>

          <aside className="card discovery-steps" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
            <h3>Inferred Telemetry</h3>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 12, fontSize: '0.85rem' }}>
              <li style={{ borderBottom: '1px solid var(--glass-border)', paddingBottom: 8 }}>
                <span style={{ color: 'var(--text-muted)' }}>Parser AI:</span>
                <div style={{ fontWeight: 500, marginTop: 2 }}>{version.parser_model} ({version.parser_provider})</div>
              </li>
              <li style={{ borderBottom: '1px solid var(--glass-border)', paddingBottom: 8 }}>
                <span style={{ color: 'var(--text-muted)' }}>Prompt Context:</span>
                <div style={{ fontWeight: 500, marginTop: 2 }}>System Prompt v1</div>
              </li>
              <li style={{ borderBottom: '1px solid var(--glass-border)', paddingBottom: 8 }}>
                <span style={{ color: 'var(--text-muted)' }}>Target Entity:</span>
                <div style={{ fontWeight: 500, marginTop: 2 }}>{editedSpec.target.entity_type.value}</div>
              </li>
            </ul>

            <div style={{ background: 'rgba(139, 92, 246, 0.05)', border: '1px solid rgba(139, 92, 246, 0.1)', borderRadius: 10, padding: 12 }}>
              <h4 style={{ fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: 6, color: 'var(--primary)' }}>
                <Sparkles size={13} /> Provenance Key
              </h4>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.4, marginTop: 6 }}>
                Fields highlighted with values were parsed from natural text. Saving edits updates their status from LLM_INFERRED to USER_CONFIRMED to maintain audits.
              </p>
            </div>
          </aside>
        </div>
      )}
    </div>
  )
}

interface TagEditorProps {
  label: string
  tags: string[]
  onChange: (tags: string[]) => void
  placeholder?: string
}

function TagEditor({ label, tags, onChange, placeholder }: TagEditorProps) {
  const [input, setInput] = useState('')

  const addTag = () => {
    const val = input.trim()
    if (val && !tags.includes(val)) {
      onChange([...tags, val])
      setInput('')
    }
  }

  const removeTag = (t: string) => {
    onChange(tags.filter((item) => item !== t))
  }

  return (
    <div className="discovery-field">
      <label>{label}</label>
      <div className="tag-input-container" style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <input
          type="text"
          className="discovery-input"
          style={{ flex: 1 }}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              addTag()
            }
          }}
          placeholder={placeholder}
        />
        <button
          type="button"
          className="button button-secondary"
          style={{ padding: '0 16px', borderRadius: 10, fontSize: '0.85rem' }}
          onClick={addTag}
        >
          Add
        </button>
      </div>
      <div className="tags-list" style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {tags.length === 0 && <span style={{ color: 'var(--muted-2)', fontSize: '0.85rem', fontStyle: 'italic' }}>None specified</span>}
        {tags.map((tag) => (
          <span
            key={tag}
            className="tag-badge"
            style={{
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid var(--glass-border)',
              borderRadius: 6,
              padding: '4px 10px',
              fontSize: '0.85rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8
            }}
          >
            {tag}
            <button
              type="button"
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--muted-2)',
                cursor: 'pointer',
                padding: 0,
                fontSize: '0.75rem',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}
              onClick={() => removeTag(tag)}
            >
              <X size={10} strokeWidth={3} />
            </button>
          </span>
        ))}
      </div>
    </div>
  )
}

function RunPanel({ 
  run, 
  metrics, 
  onReset 
}: { 
  run: DiscoveryRun; 
  metrics: { discovered: number; new: number; duplicates: number } | null;
  onReset: () => void 
}) {
  const completed = run.status === 'completed'
  const failed = run.status === 'failed'
  const currentStageIndex = Math.max(0, STAGE_ORDER.indexOf(run.stage))
  const currentStep = DISCOVER.runStages[currentStageIndex]
  const displayMetrics = metrics || MOCK_SUMMARY

  return (
    <section className="card discovery-run">
      <div className="discovery-run-head">
        <strong>{completed ? DISCOVER.completeTitle : failed ? DISCOVER.failedTitle : DISCOVER.runStarted}</strong>
        <span className="discovery-run-id">run #{run.runId.slice(0, 8)}</span>
      </div>

      <p className="discovery-run-context">
        {DISCOVER.runFor} <strong>“{run.keyword}”</strong> near <strong>“{run.location}”</strong>.
      </p>

      {!completed && !failed && (
        <>
          <div className="discovery-progress">
            <span style={{ width: `${run.progress}%` }} />
          </div>
          <div className="discovery-progress-label">
            <span>
              {DISCOVER.runStagePrefix} {Math.min(currentStageIndex + 1, STAGE_ORDER.length)} of {STAGE_ORDER.length} —{' '}
              {currentStep.message}
            </span>
            <span>{run.progress}%</span>
          </div>
        </>
      )}

      <ul className="discovery-stages">
        {DISCOVER.runStages.map((step, index) => {
          const state = index < currentStageIndex || completed ? 'done' : index === currentStageIndex && !completed ? 'active' : ''
          return (
            <li key={step.stage} className={state}>
              <i>{state === 'done' && <Check size={12} strokeWidth={3} />}</i>
              {step.message}
            </li>
          )
        })}
      </ul>

      {completed && (
        <>
          <div className="discovery-summary">
            <div>
              <strong>{displayMetrics.discovered}</strong>
              <small>{DISCOVER.foundLabel}</small>
            </div>
            <div>
              <strong>{displayMetrics.new}</strong>
              <small>{DISCOVER.newLabel}</small>
            </div>
            <div>
              <strong>{displayMetrics.duplicates}</strong>
              <small>{DISCOVER.duplicateLabel}</small>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Link to="/leads" className="button button-primary">
              {DISCOVER.viewLeads} <ArrowRight size={15} />
            </Link>
            <button className="button button-secondary" type="button" onClick={onReset}>
              {DISCOVER.startAnother}
            </button>
          </div>
        </>
      )}

      {failed && (
        <button className="button button-secondary" type="button" onClick={onReset}>
          {DISCOVER.tryAgain}
        </button>
      )}
    </section>
  )
}
