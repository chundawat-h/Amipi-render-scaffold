import { useEffect, useRef, useState } from 'react'

const API = '/api'

function useJobs() {
  const [jobs, setJobs] = useState([])

  const refresh = async () => {
    const res = await fetch(`${API}/jobs`)
    if (res.ok) setJobs(await res.json())
  }

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 4000) // poll — fine at this volume, swap for websockets if it grows
    return () => clearInterval(id)
  }, [])

  return { jobs, refresh }
}

function StatusPill({ status }) {
  const styles = {
    queued: 'bg-gold-soft text-gold-deep',
    processing: 'bg-gold text-white animate-pulse',
    done: 'bg-ink text-paper',
    failed: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`px-2.5 py-1 rounded-full text-xs font-medium tracking-wide uppercase ${styles[status] ?? ''}`}>
      {status}
    </span>
  )
}

function UploadPanel({ onQueued }) {
  const [file, setFile] = useState(null)
  const [sku, setSku] = useState('')
  const [requestedBy, setRequestedBy] = useState('')
  const [dragOver, setDragOver] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

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
      onQueued()
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="bg-ink text-paper rounded-2xl p-8 md:p-10">
      <p className="text-gold-soft text-xs tracking-[0.2em] uppercase mb-2">New render request</p>
      <h2 className="font-display text-3xl mb-6">Bring a file, get the standard.</h2>

      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0])
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer border rounded-xl p-8 text-center transition-colors ${
          dragOver ? 'border-gold bg-white/5' : 'border-white/20'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".stl,.obj,.3dm,.jpg,.jpeg,.png"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        {file ? (
          <p className="text-gold">{file.name}</p>
        ) : (
          <>
            <p className="text-paper/80">Drop a CAD, STL, or product JPEG here</p>
            <p className="text-paper/40 text-sm mt-1">or click to browse</p>
          </>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4 mt-6">
        <div>
          <label className="text-xs uppercase tracking-wide text-paper/50">SKU / Style No.</label>
          <input
            value={sku}
            onChange={(e) => setSku(e.target.value)}
            placeholder="e.g. LAE022050-14WQA"
            className="w-full mt-1 bg-transparent border-b border-white/20 focus:border-gold outline-none py-1.5 text-paper placeholder:text-paper/30"
          />
        </div>
        <div>
          <label className="text-xs uppercase tracking-wide text-paper/50">Requested by</label>
          <input
            value={requestedBy}
            onChange={(e) => setRequestedBy(e.target.value)}
            placeholder="e.g. Marketing"
            className="w-full mt-1 bg-transparent border-b border-white/20 focus:border-gold outline-none py-1.5 text-paper placeholder:text-paper/30"
          />
        </div>
      </div>

      {error && <p className="text-red-400 text-sm mt-4">{error}</p>}

      <button
        onClick={submit}
        disabled={!file || submitting}
        className="mt-8 bg-gold text-ink font-medium px-6 py-3 rounded-full disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gold-soft transition-colors"
      >
        {submitting ? 'Queuing…' : 'Generate standard render'}
      </button>
    </div>
  )
}

function JobLedger({ jobs }) {
  return (
    <div className="mt-10">
      <p className="text-gold-deep text-xs tracking-[0.2em] uppercase mb-3">Render ledger</p>
      <div className="border-t border-line">
        {jobs.length === 0 && (
          <p className="py-8 text-ink/40 text-sm">No render requests yet — the first one will show up here.</p>
        )}
        {jobs.map((job) => (
          <div key={job.id} className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-4 border-b border-line/60 py-4">
            <span className="text-ink/40 text-sm w-10">#{job.id}</span>
            <div>
              <p className="font-medium">{job.product_id ? `Product #${job.product_id}` : 'Unlinked SKU'}</p>
              <p className="text-ink/50 text-xs uppercase tracking-wide">{job.input_type} · {job.pipeline === 'render_3d' ? '3D render' : '2D normalize'}</p>
            </div>
            <StatusPill status={job.status} />
            <div className="flex gap-2">
              {job.output_paths?.hero && (
                <a href={job.output_paths.hero} target="_blank" rel="noreferrer" className="text-xs underline decoration-gold underline-offset-4">hero</a>
              )}
              {job.output_paths?.technical && (
                <a href={job.output_paths.technical} target="_blank" rel="noreferrer" className="text-xs underline decoration-gold underline-offset-4">technical</a>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function App() {
  const { jobs, refresh } = useJobs()

  return (
    <div className="min-h-screen">
      <header className="border-b border-line/20 px-8 py-6 flex items-baseline justify-between">
        <div>
          <p className="text-gold-deep text-xs tracking-[0.3em] uppercase">AMIPI Inc.</p>
          <h1 className="font-display text-2xl">Render Studio</h1>
        </div>
        <p className="text-ink/40 text-sm">One standard. Every team.</p>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12">
        <UploadPanel onQueued={refresh} />
        <JobLedger jobs={jobs} />
      </main>
    </div>
  )
}
