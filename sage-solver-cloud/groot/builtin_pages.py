"""Groot built-in pages — dashboard and artifact browser registered at startup."""

import logging

from groot.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dashboard JSX — fetches /api/system/state and /api/pages
# ---------------------------------------------------------------------------

_DASHBOARD_JSX = """\
function fmtUptime(s) {
  if (!s && s !== 0) return '--';
  s = Math.floor(s);
  if (s < 60)   return s + 's';
  if (s < 3600) return Math.floor(s / 60) + 'm ' + (s % 60) + 's';
  return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
}

function fmtRelative(iso) {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const s = Math.floor(diff / 1000);
  if (s < 60)    return s + 's ago';
  if (s < 3600)  return Math.floor(s / 60) + 'm ago';
  if (s < 86400) return Math.floor(s / 3600) + 'h ago';
  return Math.floor(s / 86400) + 'd ago';
}

function fmtDate(iso) {
  if (!iso) return '\u2014';
  const d = new Date(iso);
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return d.getDate() + '\u00a0' + months[d.getMonth()];
}

function Dropdown({ items }) {
  const [open, setOpen] = React.useState(false);
  const [hovered, setHovered] = React.useState(null);
  const ref = React.useRef(null);

  React.useEffect(() => {
    if (!open) return;
    const handler = e => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={ref} style={{position:'relative', display:'inline-block', flexShrink:0}}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{padding:'.25rem .65rem', fontSize:'.78rem', borderRadius:4, border:'1px solid #30363d', cursor:'pointer', background:'#21262d', color:'#8b949e'}}
      >
        Actions \u25be
      </button>
      {open && (
        <div style={{position:'absolute', top:'100%', left:0, zIndex:200, background:'#161b22', border:'1px solid #30363d', borderRadius:6, minWidth:160, marginTop:2, boxShadow:'0 4px 12px rgba(0,0,0,.5)'}}>
          {items.map((item, i) => (
            <button
              key={i}
              onMouseEnter={() => setHovered(i)}
              onMouseLeave={() => setHovered(null)}
              onClick={() => { setOpen(false); item.onClick(); }}
              style={{display:'block', width:'100%', textAlign:'left', padding:'.4rem .75rem', background: hovered === i ? '#30363d' : 'transparent', border:'none', cursor:'pointer', color: item.danger ? '#ff6b6b' : '#e2e8f0', fontSize:'.82rem'}}
            >
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Page() {
  const [state, setState]     = React.useState(null);
  const [webApps, setWebApps] = React.useState([]);
  const [events, setEvents]   = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError]     = React.useState(null);
  const [apiKey, setApiKey]   = React.useState(() => sessionStorage.getItem('groot_key') || '');
  const [keyStatus, setKeyStatus] = React.useState('idle');

  // Fetch API key then immediately load data — prevents 401 race on mount/remount
  React.useEffect(() => {
    fetch('/api/config').then(r => r.ok ? r.json() : null).then(cfg => {
      const key = cfg && cfg.api_key ? cfg.api_key : apiKey;
      if (cfg && cfg.api_key) {
        setApiKey(cfg.api_key);
        sessionStorage.setItem('groot_key', cfg.api_key);
      }
      reload(key);
    }).catch(() => reload());
  }, []);
  const [importFile, setImportFile] = React.useState(null);
  const [importing, setImporting]   = React.useState(false);
  const [importMsg, setImportMsg]   = React.useState(null);
  const [showKey, setShowKey]       = React.useState(false);
  const [deleteStatus, setDeleteStatus]   = React.useState({});
  const [confirmDelete, setConfirmDelete] = React.useState(null); // {name, kind}
  const [search, setSearch]         = React.useState('');
  const [toast, setToast]           = React.useState(null);
  const [sourceModal, setSourceModal] = React.useState(null);
  const [confirmDataExport, setConfirmDataExport] = React.useState(null); // {name, kind, url, filename}

  const showToast = (msg, ok) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 4000);
  };

  const triggerDownload = (url, filename) => {
    showToast('Preparing export\u2026', null);
    fetch(url, {headers: apiKey ? {'X-Groot-Key': apiKey} : {}})
      .then(r => {
        if (!r.ok) throw new Error('Export failed: ' + r.status);
        const cd = r.headers.get('Content-Disposition') || '';
        const m = cd.match(/filename[*]?=['"]?([^'";\x20\t]+)['"]?/);
        if (m) filename = m[1];
        return r.blob();
      })
      .then(blob => {
        const sizeKb = (blob.size / 1024).toFixed(1);
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = filename;
        a.click();
        URL.revokeObjectURL(a.href);
        showToast('\u2713 Downloaded ' + filename + ' (' + sizeKb + ' KB)', true);
      })
      .catch(err => showToast('Export failed: ' + err.message, false));
  };

  const saveKey = k => {
    setApiKey(k);
    sessionStorage.setItem('groot_key', k);
    setKeyStatus('idle');
  };

  React.useEffect(() => {
    if (!apiKey) { setKeyStatus('empty'); return; }
    setKeyStatus('validating');
    const t = setTimeout(() => {
      fetch('/api/system/state', {headers: {'X-Groot-Key': apiKey}})
        .then(r => setKeyStatus(r.ok ? 'ok' : 'fail'))
        .catch(() => setKeyStatus('fail'));
    }, 600);
    return () => clearTimeout(t);
  }, [apiKey]);

  const reload = (k) => {
    const key = k !== undefined ? k : apiKey;
    setLoading(true);
    Promise.all([
      fetch('/api/system/state', {headers: key ? {'X-Groot-Key': key} : {}}).then(r => r.ok ? r.json() : null),
      fetch('/api/web-apps').then(r => r.ok ? r.json() : []),
      fetch('/api/system/artifacts', {headers: key ? {'X-Groot-Key': key} : {}}).then(r => r.ok ? r.json() : null),
    ])
      .then(([sysState, webAppList, artifacts]) => {
        setState(sysState);
        setWebApps(webAppList || []);
        setEvents(artifacts ? (artifacts.recent_events || []).slice(0, 10) : []);
        setLoading(false);
      })
      .catch(e => { setError(e.message); setLoading(false); });
  };

  const openSource = name => {
    setSourceModal({ name, src: null, loading: true });
    fetch('/api/pages/' + encodeURIComponent(name) + '/source')
      .then(r => r.text())
      .then(src => setSourceModal({ name, src, loading: false }))
      .catch(() => setSourceModal({ name, src: '(failed to load source)', loading: false }));
  };

  const doDelete = (name, force) => {
    setDeleteStatus(s => ({...s, [name]: 'deleting\u2026'}));
    fetch('/api/apps/' + name + '?force=' + force, {
      method: 'DELETE',
      headers: {'X-Groot-Key': apiKey},
    })
      .then(r => r.json())
      .then(d => {
        if (d.detail) {
          setDeleteStatus(s => ({...s, [name]: '\u2717 ' + d.detail}));
          showToast('Delete failed: ' + (typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail)), false);
        } else {
          setDeleteStatus(s => ({...s, [name]: '\u2713 deleted'}));
          showToast('App "' + name + '" deleted', true);
          reload();
        }
      })
      .catch(e => {
        setDeleteStatus(s => ({...s, [name]: '\u2717 ' + e.message}));
        showToast('Delete failed: ' + e.message, false);
      });
    setConfirmDelete(null);
  };

  const doDeletePage = name => {
    setDeleteStatus(s => ({...s, [name]: 'deleting\u2026'}));
    fetch('/api/tools/delete_page', {
      method: 'POST',
      headers: {'X-Groot-Key': apiKey, 'Content-Type': 'application/json'},
      body: JSON.stringify({name}),
    })
      .then(r => r.json())
      .then(d => {
        if (d.error || d.detail) {
          const msg = d.detail || d.error;
          setDeleteStatus(s => ({...s, [name]: '\u2717 ' + msg}));
          showToast('Delete failed: ' + (typeof msg === 'string' ? msg : JSON.stringify(msg)), false);
        } else {
          setDeleteStatus(s => ({...s, [name]: '\u2713 deleted'}));
          showToast('Page "' + name + '" deleted', true);
          reload();
        }
      })
      .catch(e => {
        setDeleteStatus(s => ({...s, [name]: '\u2717 ' + e.message}));
        showToast('Delete failed: ' + e.message, false);
      });
    setConfirmDelete(null);
  };

  const doImport = () => {
    if (!importFile) return;
    const ext = importFile.name.split('.').pop().toLowerCase();
    setImporting(true);
    setImportMsg(null);
    if (ext === 'zip') {
      const fd = new FormData();
      fd.append('file', importFile);
      fetch('/api/apps/import', { method:'POST', headers:{'X-Groot-Key': apiKey}, body: fd })
        .then(r => r.json())
        .then(d => {
          setImporting(false);
          if (d.detail) {
            const msg = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail);
            setImportMsg({ ok: false, text: msg }); showToast(msg, false);
          } else {
            const msg = '\u2713 ' + d.name + ' loaded \u2014 tools:' + d.tools_registered + ' pages:' + d.pages_registered;
            setImportMsg({ ok: true, text: msg }); showToast(msg, true);
            setImportFile(null); reload();
          }
        })
        .catch(e => { setImporting(false); setImportMsg({ ok: false, text: e.message }); showToast(e.message, false); });
    } else if (ext === 'json') {
      const reader = new FileReader();
      reader.onload = ev => {
        try {
          JSON.parse(ev.target.result);
          fetch('/api/app-bundles', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-Groot-Key': apiKey},
            body: ev.target.result,
          })
            .then(r => r.json())
            .then(d => {
              setImporting(false);
              if (d.detail) {
                const msg = typeof d.detail === 'string' ? d.detail : JSON.stringify(d.detail);
                setImportMsg({ ok: false, text: msg }); showToast(msg, false);
              } else {
                const msg = '\u2713 ' + d.name + ' imported \u2014 ' + d.pages_imported + ' pages';
                setImportMsg({ ok: true, text: msg }); showToast(msg, true);
                setImportFile(null); reload();
              }
            })
            .catch(err => { setImporting(false); showToast(err.message, false); });
        } catch (err) {
          setImporting(false); showToast('Invalid JSON: ' + err.message, false);
        }
      };
      reader.readAsText(importFile);
    } else {
      setImporting(false);
      showToast('Use .zip for module apps or .json for multi-page bundles', false);
    }
  };

  const keyDot = () => {
    if (keyStatus === 'ok')         return <span style={{marginLeft:6, display:'inline-block', width:10, height:10, borderRadius:'50%', background:'#4ade80', verticalAlign:'middle'}} title="Key valid"></span>;
    if (keyStatus === 'fail')       return <span style={{marginLeft:6, display:'inline-block', width:10, height:10, borderRadius:'50%', background:'#ff6b6b', verticalAlign:'middle'}} title="Key invalid"></span>;
    if (keyStatus === 'empty')      return <span style={{marginLeft:6, display:'inline-block', width:10, height:10, borderRadius:'50%', background:'#4a5568', verticalAlign:'middle'}} title="No key set"></span>;
    if (keyStatus === 'validating') return <span style={{marginLeft:6, fontSize:'.75rem', color:'#8b949e'}}>...</span>;
    return null;
  };

  const s = {
    card:     { background:'#161b22', border:'1px solid #30363d', borderRadius:8, padding:'1.25rem', marginBottom:'1rem' },
    h1:       { fontSize:'1.5rem', fontWeight:600, color:'#e2e8f0', marginBottom:'1rem' },
    h2:       { fontSize:'.8rem', fontWeight:600, color:'#8b949e', marginBottom:'.75rem', textTransform:'uppercase', letterSpacing:'.08em' },
    row:      { display:'flex', justifyContent:'space-between', alignItems:'center', padding:'.4rem 0', borderBottom:'1px solid #21262d' },
    link:     { color:'#6366f1', textDecoration:'none', fontSize:'.9rem' },
    grid:     { display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(140px, 1fr))', gap:'1rem', marginBottom:'1rem' },
    statCard: { background:'#161b22', border:'1px solid #30363d', borderRadius:8, padding:'1rem', textAlign:'center' },
    bigNum:   { fontSize:'1.8rem', fontWeight:700, color:'#4ade80' },
    bigLabel: { color:'#8b949e', fontSize:'.8rem', marginTop:'.2rem' },
    two:      { display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1rem' },
    eventRow: { padding:'.35rem 0', borderBottom:'1px solid #21262d', fontSize:'.85rem' },
    btn:      { padding:'.25rem .65rem', fontSize:'.78rem', borderRadius:4, border:'1px solid #30363d', cursor:'pointer', background:'#21262d', color:'#8b949e', marginLeft:'.35rem' },
    btnRed:   { padding:'.25rem .65rem', fontSize:'.78rem', borderRadius:4, border:'1px solid #ff6b6b', cursor:'pointer', background:'#21262d', color:'#ff6b6b', marginLeft:'.35rem' },
    btnGreen: { padding:'.25rem .65rem', fontSize:'.78rem', borderRadius:4, border:'1px solid #4ade80', cursor:'pointer', background:'#21262d', color:'#4ade80', marginLeft:'.35rem' },
    badge:    ok => ({ display:'inline-block', padding:'.1rem .45rem', borderRadius:4, fontSize:'.7rem', fontWeight:600,
                       background: ok ? '#0d2318' : '#2d1515', color: ok ? '#4ade80' : '#ff6b6b', marginRight:'.5rem' }),
    input:    { background:'#0d1117', border:'1px solid #30363d', borderRadius:4, padding:'.3rem .6rem', color:'#e2e8f0', fontSize:'.85rem', boxSizing:'border-box' },
    overlay:  { position:'fixed', inset:0, background:'rgba(0,0,0,.6)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:100 },
    modal:    { background:'#161b22', border:'1px solid #30363d', borderRadius:8, padding:'1.5rem', minWidth:320, maxWidth:420 },
    tagSystem:  { display:'inline-block', padding:'.05rem .35rem', borderRadius:3, fontSize:'.65rem', fontWeight:600, background:'#21262d', color:'#6e7681', marginLeft:'.4rem', verticalAlign:'middle' },
    tagExample: { display:'inline-block', padding:'.05rem .35rem', borderRadius:3, fontSize:'.65rem', fontWeight:600, background:'#2d2208', color:'#d29922', marginLeft:'.4rem', verticalAlign:'middle' },
    spinner:  { display:'inline-block', width:12, height:12, border:'2px solid #4ade8040', borderTopColor:'#4ade80', borderRadius:'50%', animation:'spin 0.7s linear infinite', marginRight:6 },
    srcModal: { background:'#161b22', border:'1px solid #30363d', borderRadius:8, padding:'1.5rem', width:'min(90vw, 780px)', maxHeight:'80vh', display:'flex', flexDirection:'column', gap:'1rem' },
    srcPre:   { background:'#0d1117', border:'1px solid #30363d', borderRadius:6, padding:'1rem', fontSize:'.78rem', color:'#4ade80', whiteSpace:'pre-wrap', wordBreak:'break-all', overflow:'auto', flex:1 },
  };

  const isSystemPage = name => name.startsWith('groot-');

  const filteredApps = webApps.filter(wa => {
    if (!search) return true;
    const q = search.toLowerCase();
    return wa.name.toLowerCase().includes(q) || (wa.description || '').toLowerCase().includes(q);
  });

  const kindBadge = kind => {
    if (kind === 'app_bundle')        return <span style={{display:'inline-block', padding:'.05rem .35rem', borderRadius:3, fontSize:'.65rem', fontWeight:600, background:'#1a1040', color:'#818cf8', marginRight:'.4rem'}}>module</span>;
    if (kind === 'multi_page_bundle') return <span style={{display:'inline-block', padding:'.05rem .35rem', borderRadius:3, fontSize:'.65rem', fontWeight:600, background:'#0d2440', color:'#38bdf8', marginRight:'.4rem'}}>multi-page</span>;
    return <span style={{display:'inline-block', padding:'.05rem .35rem', borderRadius:3, fontSize:'.65rem', fontWeight:600, background:'#21262d', color:'#6e7681', marginRight:'.4rem'}}>page</span>;
  };

  const scrollToWebApps = () => { const el = document.getElementById('web-apps-section'); if (el) el.scrollIntoView({behavior:'smooth', block:'start'}); };

  const navArtifacts = tab => {
    window.history.pushState({}, '', '/artifacts?tab=' + tab);
    window.dispatchEvent(new PopStateEvent('popstate'));
  };

  if (loading) return <div style={{color:'#8b949e', padding:'3rem 0', textAlign:'center'}}>Loading dashboard\u2026</div>;
  if (error)   return <div style={{color:'#ff6b6b', padding:'1rem'}}>Error: {error}</div>;

  const levelColor = l => l === 'error' ? '#ff6b6b' : l === 'warn' ? '#f0a854' : '#8b949e';

  return (
    <div>
      <style>{'@keyframes spin { to { transform: rotate(360deg) } }'}</style>

      {toast && (
        <div style={{position:'fixed', bottom:24, right:24, zIndex:300, background:'#161b22', border:'1px solid ' + (toast.ok === null ? '#6366f1' : toast.ok ? '#4ade80' : '#ff6b6b'), borderRadius:8, padding:'.75rem 1rem', color: toast.ok === null ? '#818cf8' : toast.ok ? '#4ade80' : '#ff6b6b', fontSize:'.85rem', maxWidth:360, boxShadow:'0 4px 16px rgba(0,0,0,.5)'}}>
          {toast.msg}
        </div>
      )}

      {sourceModal && (
        <div style={s.overlay} onClick={e => { if (e.target === e.currentTarget) setSourceModal(null); }}>
          <div style={s.srcModal}>
            <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', flexShrink:0}}>
              <span style={{color:'#e2e8f0', fontWeight:600, fontSize:'.9rem'}}>{sourceModal.name}</span>
              <button style={{...s.btn, marginLeft:0}} onClick={() => setSourceModal(null)}>Close</button>
            </div>
            {sourceModal.loading
              ? <div style={{color:'#8b949e', padding:'2rem 0', textAlign:'center'}}>Loading source\u2026</div>
              : <pre style={s.srcPre}>{sourceModal.src}</pre>
            }
          </div>
        </div>
      )}

      {confirmDelete && (
        <div style={s.overlay}>
          <div style={s.modal}>
            <div style={{color:'#e2e8f0', marginBottom:'1rem', fontWeight:600}}>
              Delete {confirmDelete.kind === 'app_bundle' ? 'app' : 'page'} "{confirmDelete.name}"?
            </div>
            <div style={{color:'#8b949e', fontSize:'.85rem', marginBottom:'1.25rem'}}>
              {confirmDelete.kind === 'app_bundle'
                ? 'Unregisters all tools, removes its pages, and deletes the app directory.'
                : 'This removes the page and its JSX from the store. The route will stop working immediately.'}
            </div>
            <div style={{display:'flex', gap:'.5rem', justifyContent:'flex-end'}}>
              <button style={s.btn} onClick={() => setConfirmDelete(null)}>Cancel</button>
              {confirmDelete.kind === 'app_bundle' ? (
                <button style={s.btnRed} onClick={() => doDelete(confirmDelete.name, true)}>Delete</button>
              ) : (
                <button style={s.btnRed} onClick={() => doDeletePage(confirmDelete.name)}>Delete</button>
              )}
            </div>
          </div>
        </div>
      )}

      {confirmDataExport && (
        <div style={s.overlay}>
          <div style={s.modal}>
            <div style={{color:'#e2e8f0', marginBottom:'1rem', fontWeight:600}}>
              Export "{confirmDataExport.name}" with data?
            </div>
            <div style={{color:'#8b949e', fontSize:'.85rem', marginBottom:'1.25rem'}}>
              \u26a0 This export includes saved data (blobs). The archive may contain sensitive information. Only share with trusted recipients.
            </div>
            <div style={{display:'flex', gap:'.5rem', justifyContent:'flex-end'}}>
              <button style={s.btn} onClick={() => setConfirmDataExport(null)}>Cancel</button>
              <button style={s.btnGreen} onClick={() => { triggerDownload(confirmDataExport.url, confirmDataExport.filename); setConfirmDataExport(null); }}>Export + Data</button>
            </div>
          </div>
        </div>
      )}

      <h1 style={s.h1}><span style={{color:'#4ade80'}}>Groot</span> Dashboard <span style={{fontSize:'0.75rem', color:'#8b949e', fontWeight:'normal', marginLeft:'0.5rem'}}>v0.3.0</span></h1>

      {state && (
        <div style={s.grid}>
          <div style={{...s.statCard, cursor:'pointer'}} onClick={scrollToWebApps} title="View web apps">
            <div style={s.bigNum}>{webApps.length}</div><div style={s.bigLabel}>Web Apps</div>
          </div>
          <div style={{...s.statCard, cursor:'pointer'}} onClick={() => navArtifacts('blobs')} title="View blobs">
            <div style={s.bigNum}>{state.blob_count}</div><div style={s.bigLabel}>Blobs</div>
          </div>
          <div style={{...s.statCard, cursor:'pointer'}} onClick={() => navArtifacts('schemas')} title="View schemas">
            <div style={s.bigNum}>{state.schema_count}</div><div style={s.bigLabel}>Schemas</div>
          </div>
          <div style={{...s.statCard, cursor:'pointer'}} onClick={() => navArtifacts('pages')} title="View artifacts">
            <div style={s.bigNum}>{state.artifact_count}</div><div style={s.bigLabel}>Artifacts</div>
          </div>
          <div style={s.statCard}>
            <div style={{...s.bigNum, fontSize:'1.3rem'}}>{fmtUptime(state.uptime_seconds)}</div>
            <div style={s.bigLabel}>Uptime</div>
          </div>
        </div>
      )}

      <div style={s.card}>
        <div style={{display:'flex', alignItems:'center', gap:'.75rem', flexWrap:'wrap'}}>
          <span style={{...s.h2, marginBottom:0}}>API Key</span>
          {keyDot()}
          <input style={{...s.input, flex:1, minWidth:140, maxWidth:280}} type={showKey ? 'text' : 'password'}
            placeholder="Enter Groot API key" value={apiKey} onChange={e => saveKey(e.target.value)}
            title="Required for import/export. Find in your Groot config or terminal output." />
          <button style={{...s.btn, marginLeft:0, padding:'.25rem .45rem'}} onClick={() => setShowKey(v => !v)}>
            {showKey ? 'Hide' : 'Show'}
          </button>
        </div>
      </div>

      <div id="web-apps-section" style={s.card}>
        <div style={{display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'.75rem', flexWrap:'wrap', gap:'.5rem'}}>
          <div style={{...s.h2, marginBottom:0}}>Available Web Apps</div>
          <div style={{display:'flex', gap:'.5rem', alignItems:'center', flexWrap:'wrap'}}>
            <input style={{...s.input, width:150, fontSize:'.78rem', padding:'.2rem .5rem'}}
              placeholder="Search\u2026" value={search} onChange={e => setSearch(e.target.value)} />
            <label style={{...s.btnGreen, cursor:'pointer', display:'inline-flex', alignItems:'center', marginLeft:0}}>
              + Import
              <input type="file" accept=".zip,.json" style={{display:'none'}}
                onChange={e => { setImportFile(e.target.files[0] || null); setImportMsg(null); e.target.value = ''; }} />
            </label>
            {importFile && (
              <>
                <span style={{color:'#8b949e', fontSize:'.78rem', maxWidth:130, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap'}} title={importFile.name}>{importFile.name}</span>
                <button style={{...s.btnGreen, display:'flex', alignItems:'center', marginLeft:0}} onClick={doImport} disabled={importing}>
                  {importing && <span style={s.spinner}></span>}
                  {importing ? 'Uploading\u2026' : 'Upload'}
                </button>
                <button style={{...s.btn, marginLeft:0}} onClick={() => setImportFile(null)}>\u00d7</button>
              </>
            )}
          </div>
        </div>
        {importMsg && (
          <div style={{fontSize:'.82rem', color: importMsg.ok ? '#4ade80' : '#ff6b6b', marginBottom:'.5rem'}}>
            {importMsg.text}
          </div>
        )}

        {filteredApps.length === 0 ? (
          <div style={{color:'#8b949e', fontSize:'.9rem'}}>
            {search ? "No apps match '" + search + "'" : 'No web apps found. Import a .zip (module app) or .json (multi-page bundle).'}
          </div>
        ) : (
          <>
            <div style={{display:'flex', alignItems:'center', gap:'.75rem', paddingBottom:'.3rem', borderBottom:'1px solid #30363d', marginBottom:'.15rem'}}>
              <div style={{width:74, flexShrink:0}}></div>
              <div style={{flex:1, color:'#4a5568', fontSize:'.68rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'.06em'}}>Name</div>
              <div style={{display:'flex', gap:'1.25rem', flexShrink:0}}>
                <span style={{color:'#4a5568', fontSize:'.68rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'.06em', minWidth:40, textAlign:'right', cursor:'default'}} title="When this app was first registered">Created</span>
                <span style={{color:'#4a5568', fontSize:'.68rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'.06em', minWidth:50, textAlign:'right', cursor:'default'}} title="When the app source was last changed">Modified</span>
                <span style={{color:'#4a5568', fontSize:'.68rem', fontWeight:600, textTransform:'uppercase', letterSpacing:'.06em', minWidth:50, textAlign:'right', cursor:'default'}} title="Last time this app was opened in the browser">Opened</span>
              </div>
            </div>
            {filteredApps.map(wa => {
              const isSystem = wa.kind === 'page' && isSystemPage(wa.name);
              const dropItems = [
                { label: 'Open', onClick: () => window.open(wa.url, '_blank') },
              ];
              if (wa.kind === 'page') {
                dropItems.push({ label: 'View Source', onClick: () => openSource(wa.name) });
                if (!isSystem) {
                  dropItems.push({ label: 'Export App', onClick: () => triggerDownload('/api/pages/' + encodeURIComponent(wa.name) + '/export', wa.name + '.zip') });
                  dropItems.push({ label: 'Export App + Data', onClick: () => setConfirmDataExport({name: wa.name, kind: 'page', url: '/api/pages/' + encodeURIComponent(wa.name) + '/export?include_data=true', filename: wa.name + '-data.zip'}) });
                  dropItems.push({ label: 'Delete\u2026', onClick: () => setConfirmDelete({name: wa.name, kind: 'page'}), danger: true });
                }
              } else if (wa.kind === 'app_bundle') {
                dropItems.push({ label: 'Export App',        onClick: () => triggerDownload('/api/apps/' + wa.name + '/export', wa.name + '.zip') });
                dropItems.push({ label: 'Export App + Data', onClick: () => setConfirmDataExport({name: wa.name, kind: 'app_bundle', url: '/api/apps/' + wa.name + '/export?include_data=true', filename: wa.name + '-data.zip'}) });
                dropItems.push({ label: 'Delete\u2026',      onClick: () => setConfirmDelete({name: wa.name, kind: 'app_bundle'}), danger: true });
              } else if (wa.kind === 'multi_page_bundle') {
                dropItems.push({ label: 'Export Bundle', onClick: () => triggerDownload('/api/app-bundles/' + encodeURIComponent(wa.name), wa.name + '-bundle.json') });
              }
              return (
                <div key={wa.kind + ':' + wa.name} style={{...s.row, gap:'.75rem', flexWrap:'nowrap', alignItems:'center', paddingTop:'.5rem', paddingBottom:'.5rem'}}>
                  <Dropdown items={dropItems} />
                  <div style={{flex:1, minWidth:0}}>
                    <div style={{display:'flex', alignItems:'center', flexWrap:'wrap', gap:'.25rem'}}>
                      {kindBadge(wa.kind)}
                      <a href={wa.url} target="_blank" rel="noopener" style={{...s.link, wordBreak:'break-all', fontWeight:600}}>{wa.name}</a>
                      {wa.kind === 'app_bundle' && wa.status && <span style={s.badge(wa.status === 'loaded')}>{wa.status}</span>}
                      {isSystem && <span style={s.tagSystem}>system</span>}
                    </div>
                    <div style={{color: wa.description ? '#8b949e' : '#4a5568', fontStyle: wa.description ? 'normal' : 'italic', fontSize:'.75rem', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', marginTop:'.1rem'}}>
                      {wa.description || (wa.kind === 'app_bundle' ? wa.tools_count + 't \u00b7 ' + wa.page_count + 'p'
                        : wa.kind === 'multi_page_bundle' ? wa.page_count + ' page' + (wa.page_count !== 1 ? 's' : '')
                        : 'No description')}
                    </div>
                    {deleteStatus[wa.name] && <div style={{color:'#8b949e', fontSize:'.75rem', marginTop:'.15rem'}}>{deleteStatus[wa.name]}</div>}
                  </div>
                  <div style={{display:'flex', gap:'1.25rem', alignItems:'center', flexShrink:0}}>
                    <span style={{color:'#6e7681', fontSize:'.72rem', textAlign:'right', minWidth:40, whiteSpace:'nowrap'}}
                          title={wa.created_at ? new Date(wa.created_at).toLocaleString() : 'Unknown'}>
                      {wa.created_at ? fmtDate(wa.created_at) : '\u2014'}
                    </span>
                    <span style={{color:'#6e7681', fontSize:'.72rem', textAlign:'right', minWidth:50, whiteSpace:'nowrap'}}
                          title={wa.updated_at ? new Date(wa.updated_at).toLocaleString() : 'Unknown'}>
                      {wa.updated_at ? fmtRelative(wa.updated_at) : '\u2014'}
                    </span>
                    <span style={{color: wa.last_opened_at ? '#818cf8' : '#4a5568', fontSize:'.72rem', textAlign:'right', minWidth:50, whiteSpace:'nowrap'}}
                          title={wa.last_opened_at ? new Date(wa.last_opened_at).toLocaleString() : 'Never opened'}>
                      {wa.last_opened_at ? fmtRelative(wa.last_opened_at) : '\u2014'}
                    </span>
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>

      {events.length > 0 && (
        <div style={s.card}>
          <div style={s.h2}>Recent Events</div>
          {events.map(e => (
            <div key={e.id} style={s.eventRow}>
              <span style={{color: levelColor(e.level), marginRight:'.5rem', fontWeight:600}}>[{e.level}]</span>
              <span style={{color:'#e2e8f0'}}>{e.message}</span>
              <span title={e.timestamp} style={{color:'#8b949e', fontSize:'.75rem', marginLeft:'.75rem'}}>{fmtRelative(e.timestamp)}</span>
            </div>
          ))}
        </div>
      )}
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
    const headers = { 'X-Groot-Key': key };
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
      headers: { 'Content-Type': 'application/json', 'X-Groot-Key': apiKey },
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
      headers: { 'Content-Type': 'application/json', 'X-Groot-Key': apiKey },
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
# Registration
# ---------------------------------------------------------------------------

async def register_builtin_pages(store: ArtifactStore) -> None:
    """Upsert built-in pages into the artifact store at startup."""
    pages = [
        ("groot-dashboard", _DASHBOARD_JSX, "Groot system dashboard"),
        ("groot-artifacts", _ARTIFACTS_JSX, "Browse stored artifacts"),
    ]
    for name, jsx, description in pages:
        try:
            await store.create_page(name, jsx, description)
            logger.info("Registered built-in page: %s", name)
        except ValueError:
            await store.update_page(name, jsx)
            logger.info("Updated built-in page: %s", name)
