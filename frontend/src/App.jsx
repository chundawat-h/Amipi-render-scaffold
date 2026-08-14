import { useCallback, useEffect, useRef, useState } from 'react'

const API = import.meta.env.VITE_API_URL || '/api'
const BASE_URL = import.meta.env.VITE_API_URL || ''

const getImageUrl = (path) => {
  if (!path) return ''
  if (path.startsWith('http')) return path
  return `${BASE_URL}${path}`
}

// ---------------------------------------------------------------------------

// Data hook
// ---------------------------------------------------------------------------
function useJobs() {
  const [jobs, setJobs] = useState([])
  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${API}/jobs`)
      if (res.ok) setJobs(await res.json())
    } catch (_) {}
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 4000)
    return () => clearInterval(id)
  }, [refresh])

  return { jobs, refresh }
}

// ---------------------------------------------------------------------------
// Lightbox — opens a full-size image in an overlay
// ---------------------------------------------------------------------------
function Lightbox({ src, onClose }) {
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(8,9,12,0.92)', backdropFilter: 'blur(8px)' }}
      onClick={onClose}
    >
      <div className="relative max-w-4xl w-full max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
        <img
          src={getImageUrl(src)}
          alt="Rendered output"
          className="w-full h-full object-contain rounded-xl shadow-2xl animate-fade-up"
          style={{ maxHeight: '85vh' }}
        />
        <button
          onClick={onClose}
          className="absolute -top-3 -right-3 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
          style={{ background: 'var(--gold)', color: '#0D0E12' }}
        >
          ✕
        </button>
        <a
          href={getImageUrl(src)}
          target="_blank"
          rel="noreferrer"
          className="absolute bottom-3 right-3 text-xs px-3 py-1 rounded-full glass-sm text-gold-soft hover:text-gold transition-colors"
          onClick={(e) => e.stopPropagation()}
        >
          Open full ↗
        </a>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Status pill
// ---------------------------------------------------------------------------
const STATUS_CONFIG = {
  queued:     { label: 'Queued',     dot: 'bg-gold-deep',         text: 'text-gold-soft' },
  processing: { label: 'Processing', dot: 'bg-gold animate-pulse-ring', text: 'text-gold' },
  done:       { label: 'Done',       dot: 'bg-emerald-400',        text: 'text-emerald-300' },
  failed:     { label: 'Failed',     dot: 'bg-red-500',            text: 'text-red-400' },
}

function StatusPill({ status }) {
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.queued
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium glass-sm ${cfg.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Upload panel
// ---------------------------------------------------------------------------
function UploadPanel({ onQueued }) {
  const [file, setFile]               = useState(null)
  const [sku, setSku]                 = useState('')
  const [requestedBy, setRequestedBy] = useState('')
  const [dragOver, setDragOver]       = useState(false)
  const [submitting, setSubmitting]   = useState(false)
  const [error, setError]             = useState(null)
  const inputRef = useRef(null)

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) setFile(f)
  }, [])

  const submit = async () => {
    if (!file) return
    setSubmitting(true)
    setError(null)
    const form = new FormData()
    form.append('file', file)
    if (sku) form.append('sku', sku)
    if (requestedBy) form.append('requested_by', requestedBy)
    try {
      const res = await fetch(`${API}/jobs`, { method: 'POST', body: form })
      if (!res.ok) throw new Error((await res.json()).detail ?? 'Upload failed')
      setFile(null)
      setSku('')
      setRequestedBy('')
      onQueued()
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  const ext = file?.name.split('.').pop()?.toUpperCase() ?? ''
  const is3D = ['STL', 'OBJ', '3DM'].includes(ext)

  return (
    <div className="glass rounded-2xl p-8 animate-fade-up" style={{ animationDelay: '0.1s' }}>

      {/* Header */}
      <p className="text-xs tracking-[0.22em] uppercase mb-1" style={{ color: 'var(--gold-deep)' }}>New render request</p>
      <h2 className="font-display text-3xl md:text-4xl mb-7" style={{ lineHeight: 1.2 }}>
        Drop a file,{' '}
        <span className="text-gradient-gold">get the standard.</span>
      </h2>

      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className="cursor-pointer rounded-xl p-10 text-center transition-all duration-300 relative overflow-hidden"
        style={{
          border: dragOver
            ? '1.5px solid var(--gold)'
            : '1.5px dashed rgba(201,162,75,0.25)',
          background: dragOver
            ? 'rgba(201,162,75,0.06)'
            : 'rgba(13,14,18,0.5)',
          boxShadow: dragOver ? '0 0 40px rgba(201,162,75,0.15)' : 'none',
        }}
      >
        {/* Shimmer overlay when dragging */}
        {dragOver && <div className="absolute inset-0 animate-shimmer pointer-events-none" />}

        <input
          ref={inputRef}
          type="file"
          accept=".stl,.obj,.3dm,.jpg,.jpeg,.png"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />

        {file ? (
          <div className="space-y-2">
            <div
              className="inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium"
              style={{ background: 'rgba(201,162,75,0.12)', color: 'var(--gold-soft)', border: '1px solid rgba(201,162,75,0.2)' }}
            >
              <span>{is3D ? '🗂' : '🖼'}</span>
              <span>{file.name}</span>
              <span className="opacity-50 text-xs">{(file.size / 1024).toFixed(0)} KB</span>
            </div>
            <p className="text-xs" style={{ color: 'rgba(247,245,241,0.35)' }}>
              {is3D ? 'Will render via Blender (Path A — 3D)' : 'Will normalise via rembg (Path B — 2D)'}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="text-3xl opacity-30">✦</div>
            <p className="font-medium" style={{ color: 'rgba(247,245,241,0.7)' }}>Drop a CAD, STL, or product photo</p>
            <p className="text-sm" style={{ color: 'rgba(247,245,241,0.3)' }}>.stl · .obj · .jpg · .png · .3dm  ·  or click to browse</p>
          </div>
        )}
      </div>

      {/* Fields */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mt-6">
        {[{ label: 'SKU / Style No.', value: sku, set: setSku, ph: 'e.g. LAE022050-14WQA' },
          { label: 'Requested by',    value: requestedBy, set: setRequestedBy, ph: 'e.g. Marketing' }]
          .map(({ label, value, set, ph }) => (
          <div key={label}>
            <label className="block text-xs uppercase tracking-wide mb-1.5" style={{ color: 'rgba(247,245,241,0.4)' }}>{label}</label>
            <input
              value={value}
              onChange={(e) => set(e.target.value)}
              placeholder={ph}
              className="w-full bg-transparent outline-none py-2 text-sm transition-colors"
              style={{
                borderBottom: '1px solid rgba(201,162,75,0.2)',
                color: 'var(--paper)',
              }}
              onFocus={e => e.target.style.borderBottomColor = 'var(--gold)'}
              onBlur={e  => e.target.style.borderBottomColor = 'rgba(201,162,75,0.2)'}
            />
          </div>
        ))}
      </div>

      {error && (
        <p className="mt-4 text-red-400 text-sm glass-sm rounded-lg px-4 py-2">{error}</p>
      )}

      <button
        onClick={submit}
        disabled={!file || submitting}
        className="btn-gold mt-7 w-full py-3.5 rounded-xl text-sm"
      >
        {submitting ? (
          <span className="flex items-center justify-center gap-2">
            <span className="animate-spin-slow inline-block">◌</span>
            Queuing render job…
          </span>
        ) : 'Generate standard render'}
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Job card
// ---------------------------------------------------------------------------
const OUTPUT_LINKS = [
  { key: 'hero',          label: 'Hero 2K' },
  { key: 'technical',     label: 'Technical' },
  { key: 'delivery',      label: 'JPG' },
  { key: 'front',         label: 'Front' },
  { key: 'top',           label: 'Top' },
  { key: 'hero_3quarter', label: '3-Quarter' },
]

function JobCard({ job, index, onLightbox, onDelete }) {
  const outputs = job.output_paths ?? {}
  const thumb   = outputs.thumbnail
  const hero    = outputs.hero ?? thumb

  return (
    <div
      className="glass rounded-xl overflow-hidden animate-fade-up"
      style={{ animationDelay: `${index * 0.06}s` }}
    >
      <div className="flex items-stretch">

        {/* Thumbnail column */}
        <button
          onClick={() => thumb && onLightbox(hero)}
          disabled={!thumb}
          className="flex-shrink-0 w-24 h-24 relative group overflow-hidden"
          style={{ background: 'rgba(13,14,18,0.8)' }}
        >
          {thumb ? (
            <>
              <img
                src={getImageUrl(thumb)}
                alt={`Job #${job.id}`}
                className="w-full h-full object-contain transition-transform duration-300 group-hover:scale-110"
              />
              <div className="absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                style={{ background: 'rgba(13,14,18,0.6)' }}
              >
                <span className="text-xl" style={{ color: 'var(--gold)' }}>⛶</span>
              </div>
            </>
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <span className="text-xl opacity-10">◻</span>
            </div>
          )}
        </button>

        {/* Info column */}
        <div className="flex-1 min-w-0 p-4">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div>
              <p className="font-medium text-sm">
                {job.product_id
                  ? `Product #${job.product_id}`
                  : (job.requested_by ? `From: ${job.requested_by}` : 'Unlinked upload')}
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'rgba(247,245,241,0.4)' }}>
                {job.input_type?.toUpperCase()} · {job.pipeline === 'render_3d' ? '3D Blender render' : '2D photo normalise'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <StatusPill status={job.status} />
              <button 
                onClick={() => onDelete(job.id)}
                className="text-xs px-2 py-1 rounded transition-colors"
                title="Delete this job"
                style={{ background: 'rgba(220,38,38,0.1)', color: '#f87171' }}
              >
                Delete
              </button>
            </div>
          </div>

          {/* Error message */}
          {job.status === 'failed' && job.error_message && (
            <p
              className="text-xs mt-2 rounded px-2 py-1"
              style={{ background: 'rgba(220,38,38,0.08)', color: '#f87171', border: '1px solid rgba(220,38,38,0.15)' }}
              title={job.error_message}
            >
              {job.error_message.slice(0, 100)}{job.error_message.length > 100 ? '…' : ''}
            </p>
          )}

          {/* Output links */}
          {Object.keys(outputs).length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {OUTPUT_LINKS.filter(({ key }) => outputs[key]).map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => onLightbox(outputs[key])}
                  className="text-xs px-2.5 py-1 rounded-full transition-all duration-200 hover:-translate-y-0.5"
                  style={{
                    background: 'rgba(201,162,75,0.08)',
                    color: 'var(--gold-soft)',
                    border: '1px solid rgba(201,162,75,0.18)',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Job ledger
// ---------------------------------------------------------------------------
function JobLedger({ jobs, onLightbox, onDelete }) {
  return (
    <section className="mt-10 animate-fade-up" style={{ animationDelay: '0.25s' }}>
      <div className="flex items-center justify-between mb-4">
        <p className="text-xs tracking-[0.22em] uppercase" style={{ color: 'var(--gold-deep)' }}>Render ledger</p>
        <p className="text-xs" style={{ color: 'rgba(247,245,241,0.25)' }}>{jobs.length} job{jobs.length !== 1 ? 's' : ''}</p>
      </div>

      {jobs.length === 0 ? (
        <div className="glass rounded-xl py-14 text-center">
          <p className="text-4xl mb-4 opacity-20">✦</p>
          <p className="text-sm" style={{ color: 'rgba(247,245,241,0.35)' }}>No render jobs yet — every file you upload appears here.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job, i) => (
            <JobCard key={job.id} job={job} index={i} onLightbox={onLightbox} onDelete={onDelete} />
          ))}
        </div>
      )}
    </section>
  )
}

// ---------------------------------------------------------------------------
// Root
// ---------------------------------------------------------------------------
export default function App() {
  const { jobs, refresh } = useJobs()
  const [lightbox, setLightbox] = useState(null)

  const deleteJob = async (jobId) => {
    if (!window.confirm("Are you sure you want to delete this job?")) return;
    try {
      await fetch(`${API}/jobs/${jobId}`, { method: 'DELETE' })
      refresh()
    } catch (e) {
      console.error("Failed to delete job", e)
    }
  }

  return (
    <div className="min-h-screen">

      {/* Lightbox */}
      {lightbox && <Lightbox src={lightbox} onClose={() => setLightbox(null)} />}

      {/* Header */}
      <header
        className="sticky top-0 z-40 px-6 py-4 flex items-center justify-between"
        style={{ borderBottom: '1px solid rgba(201,162,75,0.08)', background: 'rgba(13,14,18,0.9)', backdropFilter: 'blur(20px)' }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold"
            style={{ background: 'linear-gradient(135deg,#C9A24B,#8C6D2A)', color: '#0D0E12' }}
          >
            A
          </div>
          <div>
            <p className="text-xs tracking-[0.2em] uppercase" style={{ color: 'var(--gold-deep)' }}>AMIPI Inc.</p>
            <p className="font-display text-lg leading-none" style={{ color: 'var(--gold-soft)' }}>Render Studio</p>
          </div>
        </div>
        <p className="text-xs hidden sm:block" style={{ color: 'rgba(247,245,241,0.25)' }}>One standard · Every team</p>
      </header>

      {/* Main */}
      <main className="max-w-2xl mx-auto px-4 py-12">
        <UploadPanel onQueued={refresh} />
        <JobLedger jobs={jobs} onLightbox={setLightbox} onDelete={deleteJob} />
      </main>

      {/* Subtle bottom gradient */}
      <div
        className="fixed bottom-0 inset-x-0 h-24 pointer-events-none"
        style={{ background: 'linear-gradient(to top, rgba(13,14,18,0.8), transparent)' }}
      />
    </div>
  )
}









