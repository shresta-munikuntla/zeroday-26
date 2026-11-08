import React, { useState } from 'react';
import { login } from './api';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('reviewer');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError('');
    try { onLogin(await login(username, password)); }
    catch { setError('Sign in failed. Check your username and password.'); }
    finally { setBusy(false); }
  }
  return <main className="login-page"><div className="login-mark"><span className="brand-icon">S</span><span>SENTINEL<span className="muted-brand">AI</span></span></div><section className="login-card"><div className="eyebrow">SECURITY OPERATIONS</div><h1>Incident desk</h1><p className="muted">Review evidence-led alerts and approve owner notifications.</p><form onSubmit={submit}><label>Username<input autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required /></label><label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>{error && <div className="error-text">{error}</div>}<button className="button primary full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'} <span>↗</span></button></form><div className="login-foot"><span className="status-dot"/> Protected reviewer workspace <span>·</span> Session expires in 30 min</div></section><div className="login-caption">A human decision is required before any notification is delivered.</div></main>;
}
