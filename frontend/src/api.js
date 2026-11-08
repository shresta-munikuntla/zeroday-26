import axios from 'axios';

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api' });
api.interceptors.request.use((config) => {
  const token = sessionStorage.getItem('sentinel_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export async function login(username, password) {
  const { data } = await api.post('/auth/login', { username, password });
  sessionStorage.setItem('sentinel_token', data.access_token);
  sessionStorage.setItem('sentinel_user', JSON.stringify(data.user));
  return data.user;
}
export async function getIncidents() { return (await api.get('/incidents')).data; }
export async function getIncident(id) { return (await api.get(`/incidents/${id}`)).data; }
export async function runDemo() { return (await api.post('/incidents/run-demo', {})).data; }
export async function approve(id) { return (await api.post(`/incidents/${id}/approve`, { comment: '' })).data; }
export async function reject(id) { return (await api.post(`/incidents/${id}/reject`, { comment: '' })).data; }
export async function send(id, recipient_ids) { return (await api.post(`/incidents/${id}/send`, { recipient_ids })).data; }
export default api;
