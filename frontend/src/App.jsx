import React, { useCallback, useEffect, useState } from 'react';
import Login from './Login.jsx';
import IncidentList from './IncidentList.jsx';
import IncidentDetail from './IncidentDetail.jsx';
import { approve, getIncident, getIncidents, reject, runDemo, send } from './api.js';

export default function App() {
  const [user, setUser] = useState(() => JSON.parse(sessionStorage.getItem('sentinel_user') || 'null'));
  const [incidents, setIncidents] = useState([]);
  const [selected, setSelected] = useState('');
  const [incident, setIncident] = useState(null);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState('');
  const notify = useCallback(message => { setToast(message); window.setTimeout(() => setToast(''), 3400); }, []);
  const refresh = useCallback(async (id = selected) => {
    try {
      const list = await getIncidents();
      setIncidents(list);
      const targetId = list.some(item => item.incident_id === id) ? id : list[0]?.incident_id;
      if (!targetId) { setIncident(null); setSelected(''); return; }
      const detail = await getIncident(targetId);
      setIncident(detail); setSelected(targetId);
    } catch (error) {
      if (error.response?.status === 401) { sessionStorage.clear(); setUser(null); }
      else if (error.response?.status !== 404) notify('Could not load the incident. Check the backend connection.');
    }
  }, [selected, notify]);
  useEffect(() => { if (user) refresh(); }, [user, refresh]);
  async function action(fn, success) {
    setBusy(true);
    try { await fn(selected); notify(success); await refresh(selected); }
    catch (error) { notify(error.response?.data?.detail || 'Action could not be completed.'); }
    finally { setBusy(false); }
  }
  async function doRunDemo() {
    setBusy(true);
    try { const result = await runDemo(); setSelected(result.incident_id); await refresh(result.incident_id); notify('Demo incident is ready for review.'); }
    catch (error) { notify(error.response?.data?.detail || 'Could not run the demo scenario.'); }
    finally { setBusy(false); }
  }
  function logout() { sessionStorage.clear(); setUser(null); setIncident(null); }
  if (!user) return <Login onLogin={setUser} />;
  return <div className="app-shell"><IncidentList incidents={incidents} selected={selected} onSelect={id => refresh(id)} onRunDemo={doRunDemo} busy={busy} /><main className="main-area"><div className="topbar"><div className="topbar-context"><span className="live-dot"/> SentinelAI <span className="top-divider">/</span> Incident Desk <span className="environment">DEMO ENVIRONMENT</span></div><div className="topbar-user"><span className="help-link" onClick={() => notify('SentinelAI incident desk')}>? <span>Help</span></span><span className="avatar">{user.username.slice(0, 1).toUpperCase()}</span><span className="user-copy"><strong>{user.username}</strong><small>{user.role === 'reviewer' ? 'Security reviewer' : 'Read-only viewer'}</small></span><button className="logout" onClick={logout} title="Sign out">↪</button></div></div><IncidentDetail incident={incident} user={user} onApprove={() => action(approve, 'Incident approved. The decision is in the audit history.')} onReject={() => action(reject, 'Incident rejected.')} onSend={recipientIds => action(id => send(id, recipientIds), 'Notification delivery processed. Check each recipient status.')} busy={busy} notify={notify} /></main>{toast && <div className="toast"><span>✓</span>{toast}</div>}</div>;
}
