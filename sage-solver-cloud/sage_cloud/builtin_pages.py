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
function fmtElapsed(s) {
  if (!s && s !== 0) return '--';
  s = Math.floor(s);
  if (s < 60)   return s + 's';
  if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's';
  return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
}

function Page() {
  const [jobs, setJobs] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [filter, setFilter] = React.useState('all');
  const [expanded, setExpanded] = React.useState(null);
  const [jobDetails, setJobDetails] = React.useState({});
  const [actionMsg, setActionMsg] = React.useState(null);

  const getKey = () => sessionStorage.getItem('sage_key') || '';

  const fetchJobs = () => {
    const apiKey = getKey();
    fetch('/api/tools/read_blob', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Sage-Key': apiKey },
      body: JSON.stringify({ key: 'jobs/index' }),
    })
      .then(r => {
        if (r.status === 404) return { data: null };
        if (!r.ok) throw new Error('Failed to fetch jobs: ' + r.status);
        return r.json();
      })
      .then(res => {
        if (res && res.data) {
          try {
            const parsed = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
            setJobs(parsed.jobs || []);
          } catch (e) {
            setJobs([]);
          }
        } else {
          setJobs([]);
        }
        setLoading(false);
        setError(null);
      })
      .catch(e => { setError(e.message); setLoading(false); });
  };

  React.useEffect(() => {
    fetch('/api/config').then(r => r.ok ? r.json() : null).then(cfg => {
      if (cfg && cfg.api_key) sessionStorage.setItem('sage_key', cfg.api_key);
      fetchJobs();
    }).catch(() => fetchJobs());
  }, []);

  React.useEffect(() => {
    const interval = setInterval(fetchJobs, 3000);
    return () => clearInterval(interval);
  }, []);

  const fetchJobDetail = (taskId) => {
    if (jobDetails[taskId]) return;
    const apiKey = getKey();
    fetch('/api/tools/read_blob', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Sage-Key': apiKey },
      body: JSON.stringify({ key: 'jobs/' + taskId }),
    })
      .then(r => r.ok ? r.json() : null)
      .then(res => {
        if (res && res.data) {
          try {
            const parsed = typeof res.data === 'string' ? JSON.parse(res.data) : res.data;
            setJobDetails(d => ({ ...d, [taskId]: parsed }));
          } catch (e) {
            setJobDetails(d => ({ ...d, [taskId]: { error: 'Invalid JSON' } }));
          }
        }
      })
      .catch(() => {});
  };

  const toggleExpand = (taskId) => {
    if (expanded === taskId) {
      setExpanded(null);
    } else {
      setExpanded(taskId);
      fetchJobDetail(taskId);
    }
  };

  const sendControl = (taskId, control) => {
    const apiKey = getKey();
    const detail = jobDetails[taskId];
    if (!detail) return;
    const updated = { ...detail, control: control, updated_at: new Date().toISOString() };
    fetch('/api/tools/write_blob', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Sage-Key': apiKey },
      body: JSON.stringify({ key: 'jobs/' + taskId, data: JSON.stringify(updated), content_type: 'application/json' }),
    })
      .then(r => {
        if (r.ok) {
          setJobDetails(d => ({ ...d, [taskId]: updated }));
          setActionMsg({ taskId, msg: control === 'pause' ? 'Pause requested' : 'Resume requested', ok: true });
          setTimeout(() => setActionMsg(null), 2500);
        }
      })
      .catch(() => {});
  };

  const colors = {
    bg:      '#0d1117',
    surface: '#161b22',
    border:  '#1e2a3a',
    accent:  '#3b82f6',
    text:    '#e2e8f0',
    muted:   '#8b949e',
    dimmed:  '#4a5568',
  };

  const statusColors = {
    queued:   { bg: '#1e2a3a', text: '#8b949e', label: 'Queued' },
    running:  { bg: '#172554', text: '#60a5fa', label: 'Running' },
    paused:   { bg: '#2d2204', text: '#fbbf24', label: 'Paused' },
    complete: { bg: '#0d2a1f', text: '#34d399', label: 'Complete' },
    failed:   { bg: '#2a1015', text: '#f87171', label: 'Failed' },
  };

  const sc = (status) => statusColors[status] || statusColors.queued;

  const tabs = ['all', 'running', 'paused', 'complete', 'failed'];

  const filtered = filter === 'all' ? jobs : jobs.filter(j => j.status === filter);

  const s = {
    wrapper: { padding: '1.5rem 0' },
    header: {
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      marginBottom: '1.25rem', flexWrap: 'wrap', gap: '.5rem',
    },
    title: { fontSize: '1.5rem', fontWeight: 600, color: colors.text },
    tabs: {
      display: 'flex', gap: '.25rem', marginBottom: '1.25rem',
      borderBottom: '1px solid ' + colors.border, paddingBottom: '.5rem',
    },
    tab: (active) => ({
      padding: '.35rem .9rem', borderRadius: 6, fontSize: '.85rem', cursor: 'pointer',
      border: '1px solid ' + (active ? colors.accent : colors.border),
      background: active ? '#172554' : colors.surface,
      color: active ? '#60a5fa' : colors.muted,
      fontWeight: active ? 600 : 400,
    }),
    card: {
      background: colors.surface, border: '1px solid ' + colors.border,
      borderRadius: 8, padding: '1rem 1.25rem', marginBottom: '.6rem',
      cursor: 'pointer', transition: 'border-color .15s',
    },
    cardTop: {
      display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
      gap: '1rem',
    },
    badge: (status) => ({
      display: 'inline-block', padding: '.15rem .55rem', borderRadius: 4,
      fontSize: '.72rem', fontWeight: 600, letterSpacing: '.03em',
      background: sc(status).bg, color: sc(status).text,
    }),
    meta: {
      display: 'flex', gap: '1.25rem', flexWrap: 'wrap', marginTop: '.5rem',
      fontSize: '.8rem', color: colors.muted,
    },
    metaItem: { display: 'flex', alignItems: 'center', gap: '.25rem' },
    detailPanel: {
      marginTop: '.75rem', padding: '1rem',
      background: '#0d1117', border: '1px solid ' + colors.border,
      borderRadius: 6,
    },
    detailSection: { marginBottom: '.75rem' },
    detailLabel: {
      fontSize: '.72rem', fontWeight: 600, color: colors.muted,
      textTransform: 'uppercase', letterSpacing: '.06em', marginBottom: '.35rem',
    },
    detailPre: {
      background: colors.surface, border: '1px solid ' + colors.border,
      borderRadius: 4, padding: '.6rem', fontSize: '.78rem', color: colors.text,
      whiteSpace: 'pre-wrap', wordBreak: 'break-all', maxHeight: 200, overflow: 'auto',
    },
    btn: (color) => ({
      padding: '.3rem .75rem', fontSize: '.78rem', borderRadius: 4,
      border: '1px solid ' + color, background: 'transparent',
      color: color, cursor: 'pointer', marginRight: '.5rem',
    }),
    empty: {
      textAlign: 'center', padding: '3rem 1rem', color: colors.muted,
      fontSize: '.95rem',
    },
    toast: {
      position: 'fixed', bottom: 24, right: 24, zIndex: 300,
      background: colors.surface, border: '1px solid ' + colors.accent,
      borderRadius: 8, padding: '.6rem 1rem', color: '#60a5fa',
      fontSize: '.82rem', boxShadow: '0 4px 16px rgba(0,0,0,.5)',
    },
    count: {
      fontSize: '.75rem', color: colors.dimmed, fontWeight: 400,
      marginLeft: '.5rem',
    },
  };

  if (loading) return <div style={{color: colors.muted, padding: '3rem 0', textAlign: 'center'}}>Loading jobs...</div>;

  return (
    <div style={s.wrapper}>
      {actionMsg && <div style={s.toast}>{actionMsg.msg}</div>}

      <div style={s.header}>
        <div style={s.title}>
          Solver Jobs
          <span style={s.count}>{jobs.length} total</span>
        </div>
      </div>

      {error && (
        <div style={{background: '#2a1015', border: '1px solid #f87171', borderRadius: 8, padding: '.75rem 1rem', color: '#f87171', fontSize: '.85rem', marginBottom: '1rem'}}>
          {error}
        </div>
      )}

      <div style={s.tabs}>
        {tabs.map(t => (
          <button key={t} style={s.tab(filter === t)} onClick={() => setFilter(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
            {t !== 'all' && <span style={{marginLeft: '.3rem', opacity: .6}}>({jobs.filter(j => t === 'all' || j.status === t).length})</span>}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div style={s.empty}>
          {jobs.length === 0
            ? 'No jobs yet. Submit a problem through sage-solver-mcp to get started.'
            : 'No ' + filter + ' jobs.'}
        </div>
      ) : (
        filtered.map(job => {
          const isExpanded = expanded === job.task_id;
          const detail = jobDetails[job.task_id];
          return (
            <div key={job.task_id}
              style={{...s.card, borderColor: isExpanded ? colors.accent : colors.border}}
              onClick={() => toggleExpand(job.task_id)}
            >
              <div style={s.cardTop}>
                <div style={{flex: 1, minWidth: 0}}>
                  <div style={{display: 'flex', alignItems: 'center', gap: '.5rem', flexWrap: 'wrap'}}>
                    <span style={s.badge(job.status)}>{sc(job.status).label}</span>
                    <span style={{fontSize: '.95rem', fontWeight: 600, color: colors.text}}>{job.problem_name || job.task_id}</span>
                  </div>
                  <div style={s.meta}>
                    <span style={s.metaItem}>ID: <span style={{fontFamily: 'monospace', fontSize: '.75rem'}}>{job.task_id.length > 12 ? job.task_id.slice(0, 12) + '...' : job.task_id}</span></span>
                    {job.problem_type && <span style={s.metaItem}>Type: {job.problem_type}</span>}
                    {job.variable_count != null && <span style={s.metaItem}>Vars: {job.variable_count}</span>}
                    {job.elapsed_seconds != null && <span style={s.metaItem}>Time: {fmtElapsed(job.elapsed_seconds)}</span>}
                  </div>
                </div>
                <span style={{fontSize: '.75rem', color: colors.dimmed, flexShrink: 0}}>
                  {isExpanded ? '\u25b2' : '\u25bc'}
                </span>
              </div>

              {isExpanded && (
                <div style={s.detailPanel} onClick={e => e.stopPropagation()}>
                  {!detail ? (
                    <div style={{color: colors.muted, fontSize: '.85rem'}}>Loading details...</div>
                  ) : detail.error ? (
                    <div style={{color: '#f87171', fontSize: '.85rem'}}>{detail.error}</div>
                  ) : (
                    <>
                      {(job.status === 'running' || job.status === 'paused') && (
                        <div style={{marginBottom: '.75rem'}}>
                          {job.status === 'running' && (
                            <button style={s.btn('#fbbf24')} onClick={() => sendControl(job.task_id, 'pause')}>
                              Pause
                            </button>
                          )}
                          {job.status === 'paused' && (
                            <button style={s.btn('#60a5fa')} onClick={() => sendControl(job.task_id, 'run')}>
                              Resume
                            </button>
                          )}
                        </div>
                      )}

                      {detail.solution_summary && (
                        <div style={s.detailSection}>
                          <div style={s.detailLabel}>Solution Summary</div>
                          <div style={{fontSize: '.85rem', color: colors.text, lineHeight: 1.5}}>
                            {detail.solution_summary}
                          </div>
                        </div>
                      )}

                      {detail.cost_breakdown && Object.keys(detail.cost_breakdown).length > 0 && (
                        <div style={s.detailSection}>
                          <div style={s.detailLabel}>Cost Breakdown</div>
                          <pre style={s.detailPre}>{JSON.stringify(detail.cost_breakdown, null, 2)}</pre>
                        </div>
                      )}

                      {detail.solver_log && detail.solver_log.length > 0 && (
                        <div style={s.detailSection}>
                          <div style={s.detailLabel}>Solver Log ({detail.solver_log.length} lines)</div>
                          <pre style={s.detailPre}>{detail.solver_log.slice(-20).join('\\n')}</pre>
                        </div>
                      )}

                      {!detail.solution_summary && (!detail.solver_log || detail.solver_log.length === 0) && !detail.cost_breakdown && (
                        <div style={{color: colors.muted, fontSize: '.85rem'}}>No detailed output available yet.</div>
                      )}
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })
      )}
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
