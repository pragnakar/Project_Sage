"""Sage Cloud built-in pages — landing page, artifact browser, and job dashboard."""

import logging

from sage_cloud.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dashboard JSX — Sage Cloud landing page with navigation cards
# ---------------------------------------------------------------------------

_DASHBOARD_JSX = """\
function fmtUptime(s) {
  if (!s && s !== 0) return '--';
  s = Math.floor(s);
  if (s < 60)   return s + 's';
  if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's';
  return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
}

function Page() {
  const [stats, setStats] = React.useState(null);
  const [connected, setConnected] = React.useState(false);
  const [loading, setLoading] = React.useState(true);
  const [hoveredCard, setHoveredCard] = React.useState(null);

  React.useEffect(() => {
    const key = sessionStorage.getItem('sage_key') || '';
    fetch('/api/config').then(r => r.ok ? r.json() : null).then(cfg => {
      const apiKey = (cfg && cfg.api_key) ? cfg.api_key : key;
      if (cfg && cfg.api_key) sessionStorage.setItem('sage_key', cfg.api_key);
      return fetch('/api/system/state', { headers: apiKey ? { 'X-Sage-Key': apiKey } : {} });
    })
      .then(r => { if (r.ok) { setConnected(true); return r.json(); } return null; })
      .then(d => { setStats(d); setLoading(false); })
      .catch(() => setLoading(false));
  }, []);

  const navigate = href => {
    window.history.pushState({}, '', href);
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  const colors = {
    bg:      '#0d1117',
    surface: '#161b22',
    border:  '#1e2a3a',
    accent:  '#3b82f6',
    accentH: '#60a5fa',
    text:    '#e2e8f0',
    muted:   '#8b949e',
    dimmed:  '#4a5568',
    green:   '#34d399',
    greenBg: '#0d2a1f',
  };

  const s = {
    wrapper: {
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      minHeight: '70vh', padding: '3rem 1.5rem 2rem',
    },
    header: {
      textAlign: 'center', marginBottom: '2.5rem',
    },
    title: {
      fontSize: '2.2rem', fontWeight: 700, color: colors.text,
      letterSpacing: '-0.02em', marginBottom: '.5rem',
    },
    titleAccent: {
      color: colors.accent,
    },
    subtitle: {
      fontSize: '.95rem', color: colors.muted, fontWeight: 400,
    },
    statusRow: {
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      gap: '.5rem', marginTop: '.75rem',
    },
    statusDot: {
      width: 8, height: 8, borderRadius: '50%',
      background: connected ? colors.green : colors.dimmed,
      display: 'inline-block', flexShrink: 0,
    },
    statusText: {
      fontSize: '.8rem', color: connected ? colors.green : colors.dimmed,
    },
    grid: {
      display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
      gap: '1rem', width: '100%', maxWidth: 920, marginBottom: '2rem',
    },
    card: (id) => ({
      background: colors.surface,
      border: '1px solid ' + (hoveredCard === id ? colors.accent : colors.border),
      borderRadius: 10, padding: '1.5rem',
      cursor: 'pointer', transition: 'border-color .2s, box-shadow .2s',
      boxShadow: hoveredCard === id ? '0 0 0 1px ' + colors.accent + '30' : 'none',
    }),
    cardTitle: {
      fontSize: '1.05rem', fontWeight: 600, color: colors.text,
      marginBottom: '.35rem',
    },
    cardDesc: {
      fontSize: '.85rem', color: colors.muted, lineHeight: 1.5,
    },
    cardIcon: {
      fontSize: '1.6rem', marginBottom: '.75rem', display: 'block',
    },
    statsGrid: {
      display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
      gap: '.75rem', marginTop: '1rem', width: '100%',
    },
    statItem: {
      textAlign: 'center', padding: '.5rem',
    },
    statNum: {
      fontSize: '1.4rem', fontWeight: 700, color: colors.accent,
    },
    statLabel: {
      fontSize: '.75rem', color: colors.muted, marginTop: '.15rem',
    },
    footer: {
      marginTop: 'auto', paddingTop: '2rem', textAlign: 'center',
      fontSize: '.78rem', color: colors.dimmed,
    },
  };

  if (loading) return <div style={{color:colors.muted, padding:'3rem 0', textAlign:'center'}}>Loading...</div>;

  return (
    <div style={s.wrapper}>
      <div style={s.header}>
        <div style={s.title}>
          <span style={s.titleAccent}>Sage Cloud</span>
        </div>
        <div style={s.subtitle}>Optimization runtime for LLM agents</div>
        <div style={s.statusRow}>
          <span style={s.statusDot}></span>
          <span style={s.statusText}>{connected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </div>

      <div style={s.grid}>
        <div
          style={s.card('jobs')}
          onMouseEnter={() => setHoveredCard('jobs')}
          onMouseLeave={() => setHoveredCard(null)}
          onClick={() => navigate('/apps/sage-jobs')}
        >
          <span style={{...s.cardIcon, color: colors.accent}}>&#9881;</span>
          <div style={s.cardTitle}>Solver Jobs</div>
          <div style={s.cardDesc}>View and manage optimization jobs</div>
        </div>

        <div
          style={s.card('artifacts')}
          onMouseEnter={() => setHoveredCard('artifacts')}
          onMouseLeave={() => setHoveredCard(null)}
          onClick={() => navigate('/apps/sage-artifacts')}
        >
          <span style={{...s.cardIcon, color: '#a78bfa'}}>&#9731;</span>
          <div style={s.cardTitle}>Artifacts</div>
          <div style={s.cardDesc}>Browse blobs, pages, schemas</div>
        </div>

        <div style={{...s.card('health'), cursor: 'default'}}>
          <span style={{...s.cardIcon, color: connected ? colors.green : colors.dimmed}}>&#9829;</span>
          <div style={s.cardTitle}>System Health</div>
          {stats ? (
            <div style={s.statsGrid}>
              <div style={s.statItem}>
                <div style={s.statNum}>{fmtUptime(stats.uptime_seconds)}</div>
                <div style={s.statLabel}>Uptime</div>
              </div>
              <div style={s.statItem}>
                <div style={s.statNum}>{stats.blob_count != null ? stats.blob_count : '--'}</div>
                <div style={s.statLabel}>Blobs</div>
              </div>
              <div style={s.statItem}>
                <div style={s.statNum}>{stats.artifact_count != null ? stats.artifact_count : '--'}</div>
                <div style={s.statLabel}>Pages</div>
              </div>
            </div>
          ) : (
            <div style={s.cardDesc}>Unable to fetch system stats</div>
          )}
        </div>
      </div>

      <div style={s.footer}>
        sage-solver-cloud &middot; ready for sage-solver-mcp integration
      </div>
    </div>
  );
}
"""

# ---------------------------------------------------------------------------
# Artifact browser JSX — tabs for Pages / Blobs / Schemas / Events
# ---------------------------------------------------------------------------

_ARTIFACTS_JSX = """\
function Page() {
  const [tab, setTab] = React.useState('pages');
  const [apiKey, setApiKey] = React.useState('');
  const [blobs, setBlobs] = React.useState([]);
  const [schemas, setSchemas] = React.useState([]);
  const [events, setEvents] = React.useState([]);
  const [pages, setPages] = React.useState([]);
  const [selected, setSelected] = React.useState(null);
  const [blobContent, setBlobContent] = React.useState({});
  const [schemaDefs, setSchemaDefs] = React.useState({});
  const [loading, setLoading] = React.useState(true);
  const [compact, setCompact] = React.useState(false);
  const [sourceModal, setSourceModal] = React.useState(null);
  const [query, setQuery] = React.useState('');

  const fmtRelative = iso => {
    if (!iso) return '\u2014';
    const diff = Date.now() - new Date(iso).getTime();
    const sec = Math.floor(diff / 1000);
    if (sec < 60) return sec + 's ago';
    const min = Math.floor(sec / 60);
    if (min < 60) return min + 'm ago';
    const hr = Math.floor(min / 60);
    if (hr < 24) return hr + 'h ago';
    return Math.floor(hr / 24) + 'd ago';
  };

  const loadAll = key => {
    const headers = { 'X-Sage-Key': key };
    Promise.all([
      fetch('/api/system/artifacts', { headers }).then(r => r.ok ? r.json() : null),
      fetch('/api/pages').then(r => r.ok ? r.json() : []),
    ])
      .then(([artifacts, pageList]) => {
        if (artifacts) {
          setBlobs(artifacts.blobs || []);
          setSchemas(artifacts.schemas || []);
          setEvents(artifacts.recent_events || []);
        }
        setPages(pageList || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  const switchTab = t => {
    setTab(t);
    setSelected(null);
    setQuery('');
    window.history.replaceState(null, '', '/artifacts?tab=' + t);
  };

  React.useEffect(() => {
    const m = new URLSearchParams(window.location.search).get('tab');
    if (m) setTab(m);
    fetch('/api/config')
      .then(r => r.json())
      .then(cfg => { setApiKey(cfg.api_key); loadAll(cfg.api_key); })
      .catch(() => setLoading(false));
  }, []);

  const openSource = name => {
    setSourceModal({ name, src: null, loading: true });
    fetch('/api/pages/' + encodeURIComponent(name) + '/source')
      .then(r => r.text())
      .then(src => setSourceModal({ name, src, loading: false }))
      .catch(() => setSourceModal({ name, src: '(failed to load source)', loading: false }));
  };

  const inspectBlob = key => {
    if (selected === key) { setSelected(null); return; }
    setSelected(key);
    if (blobContent[key] !== undefined) return;
    fetch('/api/tools/read_blob', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Sage-Key': apiKey },
      body: JSON.stringify({ key }),
    })
      .then(r => r.ok ? r.json() : null)
      .then(res => setBlobContent(bc => ({ ...bc, [key]: res ? (res.data || '(empty)') : '(failed to load)' })))
      .catch(() => setBlobContent(bc => ({ ...bc, [key]: '(error)' })));
  };

  const inspectSchema = name => {
    if (selected === name) { setSelected(null); return; }
    setSelected(name);
    if (schemaDefs[name] !== undefined) return;
    fetch('/api/tools/get_schema', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Sage-Key': apiKey },
      body: JSON.stringify({ name }),
    })
      .then(r => r.ok ? r.json() : null)
      .then(res => setSchemaDefs(sd => ({ ...sd, [name]: res ? res.definition : {} })))
      .catch(() => setSchemaDefs(sd => ({ ...sd, [name]: {} })));
  };

  const s = {
    tabs:     { display:'flex', gap:'.25rem', marginBottom:'1rem', borderBottom:'1px solid #30363d', paddingBottom:'.5rem' },
    tab:      { padding:'.35rem .9rem', borderRadius:6, border:'1px solid #30363d', background:'#161b22', color:'#8b949e', cursor:'pointer', fontSize:'.9rem' },
    tabA:     { padding:'.35rem .9rem', borderRadius:6, border:'1px solid #4ade80', background:'#0d2318', color:'#4ade80', cursor:'pointer', fontSize:'.9rem', fontWeight:600 },
    card:     { background:'#161b22', border:'1px solid #30363d', borderRadius:8, padding:'1.25rem', marginBottom:'.6rem' },
    row:      { display:'flex', justifyContent:'space-between', alignItems:'center', padding:'.35rem 0', borderBottom:'1px solid #21262d', fontSize:'.875rem' },
    key:      { color:'#e2e8f0', fontFamily:'monospace' },
    meta:     { color:'#8b949e', fontSize:'.8rem' },
    pre:      { background:'#0d1117', border:'1px solid #30363d', borderRadius:6, padding:'1rem', fontSize:'.8rem', color:'#4ade80', whiteSpace:'pre-wrap', wordBreak:'break-all', marginTop:'.75rem', maxHeight:300, overflow:'auto' },
    levelColor: l => l === 'error' ? '#ff6b6b' : l === 'warn' ? '#f0a854' : '#8b949e',
    h1:       { fontSize:'1.5rem', fontWeight:600, color:'#e2e8f0', marginBottom:'1rem' },
    empty:    { color:'#8b949e', fontSize:'.9rem', padding:'1rem 0' },
    link:     { color:'#6366f1', textDecoration:'none', fontSize:'.9rem' },
    btn:      { padding:'.25rem .6rem', fontSize:'.8rem', cursor:'pointer', background:'#21262d', border:'1px solid #30363d', borderRadius:4, color:'#8b949e' },
    overlay:  { position:'fixed', inset:0, background:'rgba(0,0,0,.6)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:100 },
    srcModal: { background:'#161b22', border:'1px solid #30363d', borderRadius:8, padding:'1.5rem', width:'min(90vw, 780px)', maxHeight:'80vh', display:'flex', flexDirection:'column', gap:'1rem' },
    srcPre:   { background:'#0d1117', border:'1px solid #30363d', borderRadius:6, padding:'1rem', fontSize:'.78rem', color:'#4ade80', whiteSpace:'pre-wrap', wordBreak:'break-all', overflow:'auto', flex:1 },
    searchBox:{ width:'100%', padding:'.4rem .7rem', background:'#0d1117', border:'1px solid #30363d', borderRadius:6, color:'#e2e8f0', fontSize:'.85rem', marginBottom:'.75rem', boxSizing:'border-box' },
  };

  const q = query.toLowerCase();
  const filteredPages   = pages.filter(p => !q || p.name.toLowerCase().includes(q) || (p.description||'').toLowerCase().includes(q));
  const filteredBlobs   = blobs.filter(b => !q || b.key.toLowerCase().includes(q) || b.content_type.toLowerCase().includes(q));
  const filteredSchemas = schemas.filter(sc => !q || sc.name.toLowerCase().includes(q));
  const filteredEvents  = events.filter(e => !q || e.message.toLowerCase().includes(q) || e.level.toLowerCase().includes(q));

  if (loading) return <div style={{color:'#8b949e', padding:'3rem 0', textAlign:'center'}}>Loading artifacts\u2026</div>;

  return (
    <div>
      <h1 style={s.h1}>Artifact Browser</h1>

      {sourceModal && (
        <div style={s.overlay} onClick={e => { if (e.target === e.currentTarget) setSourceModal(null); }}>
          <div style={s.srcModal}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', flexShrink:0}}>
              <span style={{color:'#e2e8f0', fontWeight:600, fontSize:'.9rem'}}>{sourceModal.name}</span>
              <button style={s.btn} onClick={() => setSourceModal(null)}>Close</button>
            </div>
            {sourceModal.loading
              ? <div style={{color:'#8b949e', padding:'2rem 0', textAlign:'center'}}>Loading source\u2026</div>
              : <pre style={s.srcPre}>{sourceModal.src}</pre>
            }
          </div>
        </div>
      )}

      <div style={s.tabs}>
        <button style={tab === 'pages'   ? s.tabA : s.tab} onClick={() => switchTab('pages')}>Pages ({pages.length})</button>
        <button style={tab === 'blobs'   ? s.tabA : s.tab} onClick={() => switchTab('blobs')}>Blobs ({blobs.length})</button>
        <button style={tab === 'schemas' ? s.tabA : s.tab} onClick={() => switchTab('schemas')}>Schemas ({schemas.length})</button>
        <button style={tab === 'events'  ? s.tabA : s.tab} onClick={() => switchTab('events')}>Events ({events.length})</button>
      </div>

      <input
        style={s.searchBox}
        placeholder={'Search ' + tab + '\u2026'}
        value={query}
        onChange={e => { setQuery(e.target.value); setSelected(null); }}
      />

      {tab === 'pages' && (
        <div>
          <div style={{display:'flex', justifyContent:'flex-end', marginBottom:'.5rem'}}>
            <button style={{...s.btn, fontSize:'.75rem', padding:'.2rem .55rem'}} onClick={() => setCompact(c => !c)}>
              {compact ? 'Card view' : 'Compact view'}
            </button>
          </div>
          {filteredPages.length === 0
            ? <div style={s.empty}>{query ? 'No matching pages.' : 'No pages registered.'}</div>
            : compact
              ? (
                <div style={{background:'#161b22', border:'1px solid #30363d', borderRadius:8, overflow:'hidden'}}>
                  {filteredPages.map((p, i) => (
                    <div key={p.name} style={{display:'flex', alignItems:'center', gap:'.75rem', padding:'.5rem 1rem', borderBottom: i < filteredPages.length - 1 ? '1px solid #21262d' : 'none', fontSize:'.85rem'}}>
                      <a href={'/apps/' + p.name} target="_blank" rel="noopener" style={s.link}>{p.name}</a>
                      <span style={{color:'#8b949e', flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', fontSize:'.78rem'}} title={p.description || ''}>{p.description || <em style={{color:'#4a5568'}}>No description</em>}</span>
                      <span title={p.updated_at ? new Date(p.updated_at).toLocaleString() : ''} style={{color:'#4a5568', fontSize:'.75rem', whiteSpace:'nowrap'}}>{fmtRelative(p.updated_at)}</span>
                      <button style={{...s.btn, padding:'.15rem .5rem', fontSize:'.75rem', color:'#8b949e'}} onClick={() => openSource(p.name)}>Source</button>
                    </div>
                  ))}
                </div>
              )
              : filteredPages.map(p => (
                  <div key={p.name} style={s.card}>
                    <div style={s.row}>
                      <div style={{display:'flex', flexDirection:'column', gap:'.2rem', flex:1, minWidth:0}}>
                        <a href={'/apps/' + p.name} target="_blank" rel="noopener" style={s.link}>{p.name}</a>
                        <span
                          title={p.description || ''}
                          style={{color: p.description ? '#8b949e' : '#4a5568', fontStyle: p.description ? 'normal' : 'italic', fontSize:'.78rem', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}}
                        >
                          {p.description || 'No description'}
                        </span>
                      </div>
                      <span title={p.updated_at ? new Date(p.updated_at).toLocaleString() : ''} style={{color:'#8b949e', fontSize:'.75rem', whiteSpace:'nowrap', marginLeft:'1rem'}}>{fmtRelative(p.updated_at)}</span>
                    </div>
                    <div style={{display:'flex', gap:'.5rem', marginTop:'.5rem'}}>
                      <button style={{...s.btn, color:'#6366f1', borderColor:'#6366f1'}} onClick={() => { window.open('/apps/' + p.name, '_blank'); }}>Open</button>
                      <button style={s.btn} onClick={() => openSource(p.name)}>Source</button>
                    </div>
                  </div>
                ))
          }
        </div>
      )}

      {tab === 'blobs' && (
        <div>
          {filteredBlobs.length === 0
            ? <div style={s.empty}>{query ? 'No matching blobs.' : 'No blobs stored.'}</div>
            : filteredBlobs.map(b => (
                <div key={b.key} style={s.card}>
                  <div style={s.row}>
                    <span style={s.key}>{b.key}</span>
                    <span style={s.meta}>{b.content_type} \u00b7 {b.size_bytes}B \u00b7 <span title={b.created_at ? new Date(b.created_at).toLocaleString() : ''}>{fmtRelative(b.created_at)}</span></span>
                  </div>
                  {selected === b.key
                    ? <div>
                        <pre style={s.pre}>{blobContent[b.key] !== undefined ? blobContent[b.key] : 'Loading\u2026'}</pre>
                        <button onClick={() => setSelected(null)} style={{...s.btn, color:'#e2e8f0', marginTop:'.5rem'}}>Close</button>
                      </div>
                    : <button onClick={() => inspectBlob(b.key)} style={{...s.btn, marginTop:'.5rem'}}>Inspect</button>
                  }
                </div>
              ))
          }
        </div>
      )}

      {tab === 'schemas' && (
        <div>
          {filteredSchemas.length === 0
            ? <div style={s.empty}>{query ? 'No matching schemas.' : 'No schemas defined.'}</div>
            : filteredSchemas.map(sc => (
                <div key={sc.name} style={s.card}>
                  <div style={s.row}>
                    <span style={s.key}>{sc.name}</span>
                    <span style={s.meta}><span title={sc.created_at ? new Date(sc.created_at).toLocaleString() : ''}>{fmtRelative(sc.created_at)}</span></span>
                  </div>
                  {selected === sc.name
                    ? <div>
                        <pre style={s.pre}>{schemaDefs[sc.name] !== undefined ? JSON.stringify(schemaDefs[sc.name], null, 2) : 'Loading\u2026'}</pre>
                        <button onClick={() => setSelected(null)} style={{...s.btn, color:'#e2e8f0', marginTop:'.5rem'}}>Close</button>
                      </div>
                    : <button onClick={() => inspectSchema(sc.name)} style={{...s.btn, marginTop:'.5rem'}}>View Schema</button>
                  }
                </div>
              ))
          }
        </div>
      )}

      {tab === 'events' && (
        <div>
          {filteredEvents.length === 0
            ? <div style={s.empty}>{query ? 'No matching events.' : 'No events logged.'}</div>
            : filteredEvents.map(e => (
                <div key={e.id} style={{...s.row, alignItems:'flex-start'}}>
                  <span style={{color: s.levelColor(e.level), marginRight:'.5rem', fontWeight:600, minWidth:50}}>[{e.level}]</span>
                  <span style={{color:'#e2e8f0', flex:1}}>{e.message}</span>
                  <span title={e.timestamp ? new Date(e.timestamp).toLocaleString() : ''} style={{color:'#8b949e', fontSize:'.75rem', marginLeft:'1rem', whiteSpace:'nowrap'}}>{fmtRelative(e.timestamp)}</span>
                </div>
              ))
          }
        </div>
      )}
    </div>
  );
}
"""

# ---------------------------------------------------------------------------
# Solver job dashboard JSX — reads jobs from blob store, shows status cards
# ---------------------------------------------------------------------------

_SAGE_JOBS_JSX = """\
function Page() {
  /* ------------------------------------------------------------------ */
  /* State                                                               */
  /* ------------------------------------------------------------------ */
  const [jobs, setJobs] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [statusFilter, setStatusFilter] = React.useState('all');
  const [typeFilter, setTypeFilter] = React.useState('all');
  const [expanded, setExpanded] = React.useState(null);
  const [jobDetails, setJobDetails] = React.useState({});
  const [toasts, setToasts] = React.useState([]);
  const [showDeleted, setShowDeleted] = React.useState(false);
  const [chartReady, setChartReady] = React.useState(false);
  const [confirmDelete, setConfirmDelete] = React.useState(null);
  const [webhookForm, setWebhookForm] = React.useState({});
  const chartRef = React.useRef(null);
  const chartInstance = React.useRef(null);
  const listPollRef = React.useRef(null);
  const progressPollRef = React.useRef(null);

  /* ------------------------------------------------------------------ */
  /* Helpers                                                             */
  /* ------------------------------------------------------------------ */
  const getKey = () => sessionStorage.getItem('sage_key') || '';

  const fmtElapsed = (s) => {
    if (!s && s !== 0) return '--';
    s = Math.floor(s);
    if (s < 60)   return s + 's';
    if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's';
    return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
  };

  const addToast = (msg) => {
    const id = Date.now();
    setToasts(t => [...t, { id, msg }]);
    setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 3000);
  };

  const copyText = (text, label) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => addToast('Copied ' + (label || 'to clipboard')));
    }
  };

  const typeIcon = (pt) => {
    const t = (pt || '').toUpperCase();
    if (t === 'LP') return '\\u{1F4C8}';
    if (t === 'MIP') return '\\u{1F333}';
    if (t === 'PORTFOLIO') return '\\u{1F967}';
    if (t === 'SCHEDULING') return '\\u{1F4C5}';
    return '\\u{1F4CA}';
  };

  /* ------------------------------------------------------------------ */
  /* Chart.js dynamic load                                               */
  /* ------------------------------------------------------------------ */
  React.useEffect(() => {
    if (window.Chart) { setChartReady(true); return; }
    const s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js';
    s.onload = () => setChartReady(true);
    document.head.appendChild(s);
  }, []);

  /* ------------------------------------------------------------------ */
  /* API calls                                                           */
  /* ------------------------------------------------------------------ */
  const hdrs = () => ({ 'X-Sage-Key': getKey() });
  const hdrsJson = () => ({ 'X-Sage-Key': getKey(), 'Content-Type': 'application/json' });

  const fetchJobs = () => {
    fetch('/api/jobs', { headers: hdrs() })
      .then(r => {
        if (!r.ok) throw new Error('Failed: ' + r.status);
        return r.json();
      })
      .then(data => { setJobs(data || []); setLoading(false); setError(null); })
      .catch(e => { setError(e.message); setLoading(false); });
  };

  const fetchJobDetail = (taskId) => {
    fetch('/api/jobs/' + encodeURIComponent(taskId), { headers: hdrs() })
      .then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(data => setJobDetails(d => ({ ...d, [taskId]: data })))
      .catch(e => setJobDetails(d => ({ ...d, [taskId]: { _error: e.message } })));
  };

  const fetchProgress = (taskId) => {
    fetch('/api/jobs/' + encodeURIComponent(taskId) + '/progress', { headers: hdrs() })
      .then(r => r.ok ? r.json() : null)
      .then(prog => {
        if (prog) {
          setJobDetails(d => {
            const prev = d[taskId] || {};
            return { ...d, [taskId]: { ...prev, ...prog } };
          });
        }
      })
      .catch(() => {});
  };

  const doPause = (taskId) => {
    fetch('/api/jobs/' + encodeURIComponent(taskId) + '/pause', { method: 'POST', headers: hdrs() })
      .then(r => {
        if (r.ok) { addToast('Pause requested for ' + taskId); fetchJobs(); fetchJobDetail(taskId); }
        else addToast('Pause failed: ' + r.status);
      })
      .catch(() => addToast('Pause request error'));
  };

  const doResume = (taskId) => {
    fetch('/api/jobs/' + encodeURIComponent(taskId) + '/resume', { method: 'POST', headers: hdrs() })
      .then(r => {
        if (r.ok) { addToast('Resumed ' + taskId); fetchJobs(); fetchJobDetail(taskId); }
        else addToast('Resume failed: ' + r.status);
      })
      .catch(() => addToast('Resume request error'));
  };

  const doDelete = (taskId) => {
    fetch('/api/jobs/' + encodeURIComponent(taskId), { method: 'DELETE', headers: hdrsJson() })
      .then(r => {
        if (r.ok) { addToast('Deleted ' + taskId); setConfirmDelete(null); setExpanded(null); fetchJobs(); }
        else addToast('Delete failed: ' + r.status);
      })
      .catch(() => addToast('Delete request error'));
  };

  /* ------------------------------------------------------------------ */
  /* Init + polling                                                      */
  /* ------------------------------------------------------------------ */
  React.useEffect(() => {
    fetch('/api/config').then(r => r.ok ? r.json() : null).then(cfg => {
      if (cfg && cfg.api_key) sessionStorage.setItem('sage_key', cfg.api_key);
      fetchJobs();
    }).catch(() => fetchJobs());
    /* Always poll every 4s — catches new jobs, status changes, completions */
    const timer = setInterval(() => { fetchJobs(); }, 4000);
    return () => clearInterval(timer);
  }, []);

  /* Progress polling for expanded job */
  React.useEffect(() => {
    if (progressPollRef.current) clearInterval(progressPollRef.current);
    if (!expanded) return;
    const job = jobs.find(j => j.task_id === expanded);
    if (!job) return;
    let interval = null;
    if (job.status === 'running') interval = 3000;
    else if (job.status === 'paused') interval = 30000;
    if (interval) {
      progressPollRef.current = setInterval(() => fetchProgress(expanded), interval);
    }
    return () => { if (progressPollRef.current) clearInterval(progressPollRef.current); };
  }, [expanded, jobs]);

  /* ------------------------------------------------------------------ */
  /* Colors & styles                                                     */
  /* ------------------------------------------------------------------ */
  const colors = {
    bg:      '#0d1117',
    surface: '#161b22',
    border:  '#1e2a3a',
    accent:  '#3b82f6',
    text:    '#e2e8f0',
    muted:   '#8b949e',
    dimmed:  '#4a5568',
    green:   '#34d399',
    yellow:  '#fbbf24',
    red:     '#f87171',
    orange:  '#fb923c',
  };

  const statusColors = {
    queued:   { bg: '#1e2a3a',  text: '#8b949e', label: 'Queued' },
    running:  { bg: '#172554',  text: '#60a5fa', label: 'Running' },
    paused:   { bg: '#2d2204',  text: '#fbbf24', label: 'Paused' },
    complete:   { bg: '#0d2a1f',  text: '#34d399', label: 'Complete' },
    infeasible: { bg: '#2d2204',  text: '#fbbf24', label: 'Infeasible' },
    failed:     { bg: '#2a1015',  text: '#f87171', label: 'Failed' },
    stalled:  { bg: '#2a1a05',  text: '#fb923c', label: 'Stalled' },
    deleted:  { bg: '#1a1a1a',  text: '#4a5568', label: 'Deleted' },
  };

  const sc = (status) => statusColors[status] || statusColors.queued;

  /* ------------------------------------------------------------------ */
  /* Filtering                                                           */
  /* ------------------------------------------------------------------ */
  const statusTabs = ['all', 'running', 'paused', 'complete', 'infeasible', 'failed'];
  const typeTabs   = ['all', 'LP', 'MIP', 'Portfolio', 'Scheduling'];

  const visibleJobs = jobs.filter(j => {
    if (j.status === 'deleted' && !showDeleted) return false;
    return true;
  });

  const filtered = visibleJobs.filter(j => {
    const sm = statusFilter === 'all' || j.status === statusFilter;
    const tm = typeFilter === 'all' || (j.problem_type || '').toUpperCase() === typeFilter.toUpperCase();
    return sm && tm;
  });

  /* ------------------------------------------------------------------ */
  /* Expand / collapse                                                   */
  /* ------------------------------------------------------------------ */
  const toggleExpand = (taskId) => {
    if (expanded === taskId) {
      setExpanded(null);
    } else {
      setExpanded(taskId);
      fetchJobDetail(taskId);
    }
  };

  /* ------------------------------------------------------------------ */
  /* Sparkline (raw canvas — no Chart.js)                                */
  /* ------------------------------------------------------------------ */
  const Sparkline = ({ history, width, height }) => {
    const canvasRef = React.useRef(null);
    React.useEffect(() => {
      const cv = canvasRef.current;
      if (!cv || !history || history.length < 2) return;
      const ctx = cv.getContext('2d');
      ctx.clearRect(0, 0, width, height);
      const vals = history.filter(h => Array.isArray(h) && h.length >= 2).map(h => h[1]);
      if (vals.length < 2) return;
      const mn = Math.min(...vals);
      const mx = Math.max(...vals);
      const range = mx - mn || 1;
      ctx.strokeStyle = '#3b82f6';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      vals.forEach((v, i) => {
        const x = (i / (vals.length - 1)) * width;
        const y = height - ((v - mn) / range) * (height - 4) - 2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
    }, [history, width, height]);
    return React.createElement('canvas', { ref: canvasRef, width: width, height: height, style: { display: 'block' } });
  };

  /* ------------------------------------------------------------------ */
  /* Convergence chart (Chart.js)                                        */
  /* ------------------------------------------------------------------ */
  React.useEffect(() => {
    if (!chartReady || !expanded) return;
    const detail = jobDetails[expanded];
    if (!detail || !detail.bound_history || detail.bound_history.length < 4) return;
    const cv = chartRef.current;
    if (!cv) return;
    if (chartInstance.current) { chartInstance.current.destroy(); chartInstance.current = null; }
    const entries = detail.bound_history.filter(h => Array.isArray(h) && h.length >= 3);
    if (entries.length < 3) return;
    const labels = entries.map(e => e[0].toFixed ? e[0].toFixed(1) + 's' : String(e[0]));
    chartInstance.current = new window.Chart(cv, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [
          { label: 'Dual Bound', data: entries.map(e => e[1]), borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,.1)', fill: false, tension: 0.2, pointRadius: 0 },
          { label: 'Incumbent', data: entries.map(e => e[2]), borderColor: '#34d399', backgroundColor: 'rgba(52,211,153,.1)', fill: false, tension: 0.2, pointRadius: 0 },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#8b949e', font: { size: 11 } } } },
        scales: {
          x: { ticks: { color: '#4a5568', font: { size: 10 }, maxTicksLimit: 8 }, grid: { color: '#1e2a3a' } },
          y: { ticks: { color: '#4a5568', font: { size: 10 } }, grid: { color: '#1e2a3a' } },
        },
      },
    });
    return () => { if (chartInstance.current) { chartInstance.current.destroy(); chartInstance.current = null; } };
  }, [chartReady, expanded, jobDetails]);

  /* ------------------------------------------------------------------ */
  /* Styles                                                              */
  /* ------------------------------------------------------------------ */
  const s = {
    wrapper: { padding: '1.5rem 0', position: 'relative', minHeight: '80vh', paddingBottom: '3.5rem' },
    header: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '.5rem' },
    title: { fontSize: '1.5rem', fontWeight: 600, color: colors.text },
    count: { fontSize: '.75rem', color: colors.dimmed, fontWeight: 400, marginLeft: '.5rem' },
    filterRow: { display: 'flex', gap: '.25rem', flexWrap: 'wrap', marginBottom: '.6rem' },
    filterLabel: { fontSize: '.72rem', fontWeight: 600, color: colors.muted, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '.25rem' },
    pill: (active, color) => ({
      padding: '.3rem .75rem', borderRadius: 20, fontSize: '.8rem', cursor: 'pointer',
      border: 'none', background: active ? (color || colors.accent) : colors.border,
      color: active ? '#fff' : colors.muted, fontWeight: active ? 600 : 400,
      transition: 'background .15s',
    }),
    card: {
      background: colors.surface, border: '1px solid ' + colors.border,
      borderRadius: 8, padding: '1rem 1.25rem', marginBottom: '.6rem',
      cursor: 'pointer', transition: 'border-color .15s',
    },
    cardTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' },
    badge: (status) => ({
      display: 'inline-block', padding: '.15rem .55rem', borderRadius: 4,
      fontSize: '.72rem', fontWeight: 600, letterSpacing: '.03em',
      background: sc(status).bg, color: sc(status).text,
    }),
    meta: { display: 'flex', gap: '1.25rem', flexWrap: 'wrap', marginTop: '.5rem', fontSize: '.8rem', color: colors.muted },
    metaItem: { display: 'flex', alignItems: 'center', gap: '.25rem' },
    gapBar: { height: 4, borderRadius: 2, background: colors.border, marginTop: '.5rem', overflow: 'hidden' },
    gapFill: (pct) => ({ height: '100%', width: Math.min(100, Math.max(0, 100 - (pct || 100))) + '%', background: colors.accent, borderRadius: 2, transition: 'width .3s' }),
    detailPanel: { marginTop: '.75rem', padding: '1rem', background: '#0d1117', border: '1px solid ' + colors.border, borderRadius: 6 },
    detailSection: { marginBottom: '1rem' },
    detailLabel: { fontSize: '.72rem', fontWeight: 600, color: colors.muted, textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '.35rem' },
    detailPre: { background: colors.surface, border: '1px solid ' + colors.border, borderRadius: 4, padding: '.6rem', fontSize: '.78rem', color: colors.text, whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 200, overflow: 'auto' },
    btn: (color) => ({ padding: '.3rem .75rem', fontSize: '.78rem', borderRadius: 4, border: '1px solid ' + color, background: 'transparent', color: color, cursor: 'pointer', marginRight: '.5rem' }),
    btnDisabled: { padding: '.3rem .75rem', fontSize: '.78rem', borderRadius: 4, border: '1px solid ' + colors.dimmed, background: 'transparent', color: colors.dimmed, cursor: 'not-allowed', marginRight: '.5rem' },
    empty: { textAlign: 'center', padding: '4rem 1rem', color: colors.muted },
    toast: { position: 'fixed', bottom: 56, right: 24, zIndex: 300, display: 'flex', flexDirection: 'column', gap: '.4rem', alignItems: 'flex-end' },
    toastItem: { background: colors.surface, border: '1px solid ' + colors.accent, borderRadius: 8, padding: '.6rem 1rem', color: '#60a5fa', fontSize: '.82rem', boxShadow: '0 4px 16px rgba(0,0,0,.5)' },
    hintBar: { position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 200, background: colors.surface, borderTop: '1px solid ' + colors.border, padding: '.5rem 1.5rem', fontSize: '.78rem', color: colors.dimmed, textAlign: 'center' },
    overlay: { position: 'fixed', inset: 0, background: 'rgba(0,0,0,.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 400 },
    confirmBox: { background: colors.surface, border: '1px solid ' + colors.border, borderRadius: 8, padding: '1.5rem', maxWidth: 400, textAlign: 'center' },
    varTable: { width: '100%', borderCollapse: 'collapse', fontSize: '.8rem', marginTop: '.5rem' },
    varTh: { textAlign: 'left', padding: '.3rem .5rem', borderBottom: '1px solid ' + colors.border, color: colors.muted, fontWeight: 600, fontSize: '.72rem', textTransform: 'uppercase' },
    varTd: { padding: '.25rem .5rem', borderBottom: '1px solid ' + colors.border, color: colors.text, fontFamily: 'monospace', fontSize: '.78rem' },
  };

  /* ------------------------------------------------------------------ */
  /* Render: loading                                                     */
  /* ------------------------------------------------------------------ */
  if (loading) return React.createElement('div', { style: { color: colors.muted, padding: '3rem 0', textAlign: 'center' } }, 'Loading jobs...');

  /* ------------------------------------------------------------------ */
  /* Render: main                                                        */
  /* ------------------------------------------------------------------ */
  return (
    <div style={s.wrapper}>

      {/* Toasts */}
      {toasts.length > 0 && (
        <div style={s.toast}>
          {toasts.map(t => <div key={t.id} style={s.toastItem}>{t.msg}</div>)}
        </div>
      )}

      {/* Delete confirm dialog */}
      {confirmDelete && (
        <div style={s.overlay} onClick={e => { if (e.target === e.currentTarget) setConfirmDelete(null); }}>
          <div style={s.confirmBox}>
            <div style={{ fontSize: '1rem', fontWeight: 600, color: colors.text, marginBottom: '1rem' }}>Delete job?</div>
            <div style={{ fontSize: '.85rem', color: colors.muted, marginBottom: '1.25rem' }}>
              This will soft-delete <span style={{ fontFamily: 'monospace', color: colors.text }}>{confirmDelete}</span>. The job data is preserved.
            </div>
            <div>
              <button style={s.btn(colors.red)} onClick={() => doDelete(confirmDelete)}>Delete</button>
              <button style={s.btn(colors.muted)} onClick={() => setConfirmDelete(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div style={s.header}>
        <div style={s.title}>
          Solver Jobs
          <span style={s.count}>{jobs.length} total</span>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div style={{ background: '#2a1015', border: '1px solid #f87171', borderRadius: 8, padding: '.75rem 1rem', color: '#f87171', fontSize: '.85rem', marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {/* Filter row 1: Status */}
      <div style={{ marginBottom: '.75rem' }}>
        <div style={s.filterLabel}>Status</div>
        <div style={s.filterRow}>
          {statusTabs.map(t => {
            const color = t === 'all' ? colors.accent : (sc(t).text || colors.accent);
            return <button key={t} style={s.pill(statusFilter === t, color)} onClick={() => setStatusFilter(t)}>{t === 'all' ? 'All' : sc(t).label}</button>;
          })}
        </div>
      </div>

      {/* Filter row 2: Type */}
      <div style={{ marginBottom: '1.25rem' }}>
        <div style={s.filterLabel}>Type</div>
        <div style={s.filterRow}>
          {typeTabs.map(t => (
            <button key={t} style={s.pill(typeFilter === t, colors.accent)} onClick={() => setTypeFilter(t)}>
              {t === 'all' ? 'All' : typeIcon(t) + ' ' + t}
            </button>
          ))}
        </div>
      </div>

      {/* Job list */}
      {filtered.length === 0 ? (
        <div style={s.empty}>
          <div style={{ fontSize: '2.5rem', marginBottom: '.75rem' }}>{String.fromCodePoint(0x1F4CA)}</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 600, color: colors.text, marginBottom: '.5rem' }}>No optimization jobs yet</div>
          <div style={{ fontSize: '.9rem' }}>
            {jobs.length === 0
              ? 'Start a conversation with Claude and say "solve this LP..." to submit your first job.'
              : 'No jobs match the current filters.'}
          </div>
        </div>
      ) : (
        filtered.map(job => {
          const isExpanded = expanded === job.task_id;
          const detail = jobDetails[job.task_id];
          const hasGap = (job.status === 'running' || job.status === 'paused') && detail && detail.gap_pct != null;
          const boundHistory = detail && detail.bound_history ? detail.bound_history.filter(h => Array.isArray(h) && h.length >= 2) : [];

          return (
            <div key={job.task_id}
              style={{ ...s.card, borderColor: isExpanded ? colors.accent : colors.border }}
              onClick={() => toggleExpand(job.task_id)}
            >
              <div style={s.cardTop}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '.5rem', flexWrap: 'wrap' }}>
                    <span style={{ fontSize: '1.1rem' }}>{typeIcon(job.problem_type)}</span>
                    <span style={{ fontSize: '.95rem', fontWeight: 600, color: colors.text }}>{(job.problem_name && !['SchedulingModel','LPModel','MIPModel','PortfolioModel'].includes(job.problem_name)) ? job.problem_name : job.task_id}</span>
                    <span style={s.badge(job.status)}>{sc(job.status).label}</span>
                  </div>
                  <div style={s.meta}>
                    <span style={s.metaItem}>
                      <span style={{ fontFamily: 'monospace', fontSize: '.75rem', cursor: 'pointer', textDecoration: 'underline dotted' }}
                        onClick={e => { e.stopPropagation(); copyText(job.task_id, 'task ID'); }}>
                        {job.task_id}
                      </span>
                    </span>
                    {job.problem_type && <span style={s.metaItem}>{job.problem_type}</span>}
                    {job.complexity_tier && <span style={s.metaItem}>{job.complexity_tier}</span>}
                    {job.status === 'complete' && job.best_incumbent != null && <span style={{ ...s.metaItem, color: colors.green }}>Obj: {typeof job.best_incumbent === 'number' ? job.best_incumbent.toLocaleString(undefined, {maximumFractionDigits:4}) : job.best_incumbent}{job.elapsed_seconds != null ? ' · ' + fmtElapsed(job.elapsed_seconds) : ''}</span>}
                    {job.status === 'running' && job.gap_pct != null && <span style={{ ...s.metaItem, color: colors.accent }}>Gap: {typeof job.gap_pct === 'number' ? job.gap_pct.toFixed(1) + '%' : job.gap_pct}</span>}
                    {(job.status === 'failed') && <span style={{ ...s.metaItem, color: '#f87171' }}>Error</span>}
                    {job.status === 'infeasible' && <span style={{ ...s.metaItem, color: '#fbbf24' }}>Infeasible</span>}
                  </div>
                  {/* Sparkline for bound history */}
                  {boundHistory.length >= 3 && (
                    <div style={{ marginTop: '.4rem' }}>
                      <Sparkline history={boundHistory} width={120} height={20} />
                    </div>
                  )}
                  {/* Gap bar */}
                  {hasGap && (
                    <div style={s.gapBar}>
                      <div style={s.gapFill(detail.gap_pct)}></div>
                    </div>
                  )}
                </div>
                <span style={{ fontSize: '.75rem', color: colors.dimmed, flexShrink: 0 }}>
                  {isExpanded ? '\\u25B2' : '\\u25BC'}
                </span>
              </div>

              {/* Expanded panel */}
              {isExpanded && (
                <div style={s.detailPanel} onClick={e => e.stopPropagation()}>
                  {!detail ? (
                    <div style={{ color: colors.muted, fontSize: '.85rem' }}>Loading details...</div>
                  ) : detail._error ? (
                    <div style={{ color: '#f87171', fontSize: '.85rem' }}>
                      Could not load details: {detail._error}
                    </div>
                  ) : (
                    <>
                      {/* Section A: Summary / Progress — always shown when detail loaded */}
                      <div style={s.detailSection}>
                        <div style={s.detailLabel}>{['running','paused'].includes(detail.status || job.status) ? 'Progress' : 'Summary'}</div>
                        <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap', fontSize: '.85rem', color: colors.text, marginBottom: '.5rem' }}>
                          {detail.gap_pct != null && <span>Gap: {detail.gap_pct.toFixed ? detail.gap_pct.toFixed(2) + '%' : detail.gap_pct}</span>}
                          {detail.best_bound != null && <span>Best bound: {detail.best_bound}</span>}
                          {detail.best_incumbent != null && <span>Objective: {detail.best_incumbent.toFixed ? detail.best_incumbent.toFixed(4) : detail.best_incumbent}</span>}
                          {detail.node_count != null && <span>Nodes: {detail.node_count}</span>}
                          {detail.elapsed_seconds != null && <span>Solved in: {fmtElapsed(detail.elapsed_seconds)}</span>}
                          {detail.n_vars != null && <span>Variables: {detail.n_vars}</span>}
                          {detail.n_constraints != null && <span>Constraints: {detail.n_constraints}</span>}
                          {detail.created_at && <span>Created: {new Date(detail.created_at).toLocaleString()}</span>}
                        </div>
                        <div>
                          {(detail.status === 'running' || job.status === 'running') && (
                            <button style={s.btn(colors.yellow)} onClick={() => doPause(job.task_id)}>Pause</button>
                          )}
                          {(detail.status === 'paused' || job.status === 'paused') && (
                            <button style={s.btn(colors.accent)} onClick={() => doResume(job.task_id)}>Resume</button>
                          )}
                        </div>
                      </div>

                      {/* Section B: Convergence chart */}
                      {chartReady && boundHistory.length > 3 && (
                        <div style={s.detailSection}>
                          <div style={s.detailLabel}>Convergence</div>
                          <div style={{ height: 200, position: 'relative' }}>
                            <canvas ref={chartRef} />
                          </div>
                        </div>
                      )}

                      {/* Section C: Result */}
                      {(detail.status === 'complete' || detail.status === 'infeasible' || detail.status === 'failed' || detail.solution || detail.incumbent_solution) && (
                        <div style={s.detailSection}>
                          <div style={s.detailLabel}>Result</div>
                          {detail.best_incumbent != null && (
                            <div style={{ fontSize: '.95rem', fontWeight: 600, color: colors.green, marginBottom: '.5rem' }}>
                              Objective: {detail.best_incumbent.toFixed ? detail.best_incumbent.toFixed(4) : detail.best_incumbent}
                            </div>
                          )}
                          {detail.explanation && (
                            <div style={{ fontSize: '.85rem', color: colors.text, lineHeight: 1.5, marginBottom: '.5rem' }}>
                              {detail.explanation}
                            </div>
                          )}
                          {/* Top 20 variables — detail.solution is flat {name: value} */}
                          {detail.solution && typeof detail.solution === 'object' && Object.keys(detail.solution).length > 0 && (
                            <div style={{ maxHeight: 300, overflow: 'auto' }}>
                              <table style={s.varTable}>
                                <thead>
                                  <tr>
                                    <th style={s.varTh}>Variable</th>
                                    <th style={{ ...s.varTh, textAlign: 'right' }}>Value</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {Object.entries(detail.solution)
                                    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
                                    .slice(0, 20)
                                    .map(([k, v]) => (
                                      <tr key={k}>
                                        <td style={s.varTd}>{k}</td>
                                        <td style={{ ...s.varTd, textAlign: 'right' }}>{typeof v === 'number' ? v.toFixed(6) : v}</td>
                                      </tr>
                                    ))
                                  }
                                </tbody>
                              </table>
                            </div>
                          )}
                          {detail.status === 'infeasible' && (
                            <div style={{ color: '#fbbf24', fontSize: '.85rem', marginTop: '.5rem' }}>
                              This problem has no feasible solution. The constraints cannot all be satisfied simultaneously.
                            </div>
                          )}
                          {detail.status === 'failed' && (
                            <div style={{ color: '#f87171', fontSize: '.85rem', marginTop: '.5rem' }}>
                              The solver encountered an error processing this job.{detail.explanation ? '' : ' No additional details available.'}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Section D: Actions */}
                      <div style={s.detailSection}>
                        <div style={s.detailLabel}>Actions</div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '.4rem', alignItems: 'center' }}>
                          <button style={s.btn(colors.accent)}
                            onClick={() => copyText(window.location.origin + '/api/jobs/' + encodeURIComponent(job.task_id), 'output URL')}>
                            Copy Output URL
                          </button>
                          <button style={s.btn(colors.red)} onClick={() => setConfirmDelete(job.task_id)}>Delete</button>
                          <button style={s.btnDisabled} disabled title="Available after Stage 14">Send to ClickUp</button>
                        </div>
                      </div>

                      {/* Webhook config */}
                      <div style={s.detailSection}>
                        <div style={s.detailLabel}>Webhooks</div>
                        {detail.output_webhooks && detail.output_webhooks.length > 0 && (
                          <div style={{ marginBottom: '.5rem' }}>
                            {detail.output_webhooks.map((url, i) => (
                              <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '.5rem', marginBottom: '.25rem' }}>
                                <span style={{ fontFamily: 'monospace', fontSize: '.78rem', color: colors.text, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{url}</span>
                                <button style={{ ...s.btn(colors.red), padding: '.15rem .5rem', fontSize: '.7rem' }} onClick={() => addToast('Webhook removal not yet wired')}>x</button>
                              </div>
                            ))}
                          </div>
                        )}
                        <div style={{ display: 'flex', gap: '.35rem', alignItems: 'center' }}>
                          <input
                            style={{ flex: 1, padding: '.3rem .5rem', background: colors.surface, border: '1px solid ' + colors.border, borderRadius: 4, color: colors.text, fontSize: '.8rem' }}
                            placeholder="https://..."
                            value={webhookForm[job.task_id] || ''}
                            onChange={e => setWebhookForm(f => ({ ...f, [job.task_id]: e.target.value }))}
                            onClick={e => e.stopPropagation()}
                          />
                          <button style={s.btn(colors.accent)} onClick={() => addToast('Webhook add not yet wired')}>Add</button>
                        </div>
                      </div>

                      {/* Fallback for queued/stalled jobs with no data */}
                      {!detail.solution && !detail.incumbent_solution && !detail.explanation && detail.best_incumbent == null && !['running','paused','complete','failed'].includes(detail.status) && (
                        <div style={{ color: colors.muted, fontSize: '.85rem' }}>No detailed output available yet.</div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })
      )}

      {/* Hint bar */}
      <div style={s.hintBar}>
        In a new chat session, say <span style={{ fontFamily: 'monospace', color: colors.accent }}>{'check task <task_id>'}</span> and Claude will retrieve this job.
        <span style={{ marginLeft: '1.5rem' }}>
          <label style={{ cursor: 'pointer', fontSize: '.75rem', color: colors.dimmed }}>
            <input type="checkbox" checked={showDeleted} onChange={e => setShowDeleted(e.target.checked)} style={{ marginRight: '.3rem' }} />
            Show deleted
          </label>
        </span>
      </div>
    </div>
  );
}
"""


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

async def register_builtin_pages(store: ArtifactStore) -> None:
    """Upsert built-in pages into the artifact store at startup."""
    pages = [
        ("sage-dashboard", _DASHBOARD_JSX, "Sage Cloud landing page"),
        ("sage-artifacts", _ARTIFACTS_JSX, "Artifact browser"),
        ("sage-jobs", _SAGE_JOBS_JSX, "Solver job dashboard"),
    ]
    for name, jsx, description in pages:
        try:
            await store.create_page(name, jsx, description)
            logger.info("Registered built-in page: %s", name)
        except ValueError:
            await store.update_page(name, jsx)
            logger.info("Updated built-in page: %s", name)
