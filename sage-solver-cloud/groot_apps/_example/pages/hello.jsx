function Page() {
  const s = {
    wrap:  { maxWidth: 600 },
    h1:    { fontSize: '1.5rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '1rem' },
    card:  { background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: '1.25rem', marginBottom: '1rem' },
    label: { color: '#8b949e', fontSize: '.85rem', marginBottom: '.25rem' },
    val:   { color: '#4ade80', fontWeight: 600 },
    link:  { color: '#6366f1', textDecoration: 'none' },
  };

  return (
    <div style={s.wrap}>
      <h1 style={s.h1}>Hello from <span style={{color:'#4ade80'}}>Example App</span></h1>
      <div style={s.card}>
        <div style={s.label}>App</div>
        <div style={s.val}>groot_apps/example</div>
      </div>
      <div style={s.card}>
        <div style={s.label}>Status</div>
        <div style={s.val}>Loaded ✓</div>
      </div>
      <div style={s.card}>
        <div style={s.label}>What this shows</div>
        <div style={{color:'#e2e8f0', fontSize:'.9rem', lineHeight:1.6}}>
          This is a static JSX page shipped with the example app module.
          It was registered via <code style={{color:'#4ade80'}}>page_server.register_static()</code> at startup
          and is delivered by the Groot page server.
        </div>
      </div>
      <p style={{color:'#8b949e', fontSize:'.85rem'}}>
        <a href="#/" style={s.link}>← Back to Dashboard</a>
      </p>
    </div>
  );
}
