import React, { useCallback, useEffect, useRef, useState } from 'react';

interface LogEntry {
  id: string;
  timestamp: string;
  method: string;
  path: string;
  status_code: number;
  ip_address: string | null;
  user_agent: string | null;
  user: string | null;
  duration_ms: number | null;
  event_type: string | null;
  detail: string | null;
}

interface Filters {
  eventType: string;
  user: string;
  search: string;
}

const PAGE_SIZE = 50;

const LogsPage: React.FC = () => {
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [filters, setFilters] = useState<Filters>({ eventType: '', user: '', search: '' });
  const intervalRef = useRef<number | null>(null);
  const credsRef = useRef('');

  const fetchLogs = useCallback(
    async (skip: number, currentFilters: Filters) => {
      const params = new URLSearchParams({
        skip: String(skip),
        limit: String(PAGE_SIZE),
      });
      if (currentFilters.eventType) params.append('event_type', currentFilters.eventType);
      if (currentFilters.user) params.append('user', currentFilters.user);
      if (currentFilters.search) params.append('search', currentFilters.search);

      const res = await fetch(`/api/logs?${params}`, {
        headers: { Authorization: `Basic ${credsRef.current}` },
      });
      if (!res.ok) throw new Error('Unauthorized');
      return res.json();
    },
    []
  );

  const fetchCount = useCallback(async (currentFilters: Filters) => {
    const params = new URLSearchParams();
    if (currentFilters.eventType) params.append('event_type', currentFilters.eventType);
    if (currentFilters.user) params.append('user', currentFilters.user);
    if (currentFilters.search) params.append('search', currentFilters.search);

    const res = await fetch(`/api/logs/count?${params}`, {
      headers: { Authorization: `Basic ${credsRef.current}` },
    });
    if (!res.ok) throw new Error('Unauthorized');
    const data = await res.json();
    return data.count;
  }, []);

  const loadData = useCallback(
    async (currentPage: number, currentFilters: Filters) => {
      setLoading(true);
      try {
        const [entries, count] = await Promise.all([
          fetchLogs(currentPage * PAGE_SIZE, currentFilters),
          fetchCount(currentFilters),
        ]);
        setLogs(entries);
        setTotalCount(count);
      } catch {
        setAuthenticated(false);
        setError('Session expired');
      } finally {
        setLoading(false);
      }
    },
    [fetchLogs, fetchCount]
  );

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const creds = btoa(`${username}:${password}`);
    try {
      const res = await fetch(`/api/logs?skip=0&limit=1`, {
        headers: { Authorization: `Basic ${creds}` },
      });
      if (!res.ok) {
        setError('Invalid credentials');
        return;
      }
      credsRef.current = creds;
      setAuthenticated(true);
      loadData(0, filters);
    } catch {
      setError('Connection error');
    }
  };

  useEffect(() => {
    if (!authenticated || !autoRefresh) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }
    intervalRef.current = window.setInterval(() => {
      loadData(page, filters);
    }, 10000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [authenticated, autoRefresh, page, filters, loadData]);

  const handleFilterChange = (key: keyof Filters, value: string) => {
    const newFilters = { ...filters, [key]: value };
    setFilters(newFilters);
    setPage(0);
    loadData(0, newFilters);
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
    loadData(newPage, filters);
  };

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  if (!authenticated) {
    return (
      <div className="flex items-center justify-center flex-grow bg-gray-50 px-4">
        <div className="w-full max-w-md">
          <img src="/abacus.svg" alt="Abacus Logo" className="h-20 w-auto mx-auto mb-6" />
          <p className="text-center text-gray-500 mb-8">Server Logs</p>
          <div className="bg-white p-8 rounded-xl shadow-md border border-gray-200">
            <h2 className="text-2xl font-semibold text-center mb-6">Authentication</h2>
            <form onSubmit={handleLogin} className="space-y-6">
              <input
                type="text"
                placeholder="Username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
              />
              <input
                type="password"
                placeholder="Password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gray-800 transition"
              />
              {error && <p className="text-red-500 text-sm text-center">{error}</p>}
              <button
                type="submit"
                className="w-full bg-gray-800 text-white py-3 rounded-lg font-semibold hover:bg-gray-900 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-800 transition"
              >
                Login
              </button>
            </form>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-grow bg-gray-50 text-gray-800">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-screen-2xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Abacus - Server Logs</h1>
            <p className="text-sm text-gray-500">{totalCount} entries</p>
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="rounded"
              />
              Auto-refresh (10s)
            </label>
            <button
              onClick={() => loadData(page, filters)}
              className="px-4 py-2 bg-gray-800 text-white rounded-lg text-sm hover:bg-gray-900 transition"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-screen-2xl mx-auto px-6 py-4">
        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-4">
          <select
            value={filters.eventType}
            onChange={(e) => handleFilterChange('eventType', e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
          >
            <option value="">All events</option>
            <option value="request">Request</option>
            <option value="login">Login</option>
            <option value="login_failed">Login Failed</option>
            <option value="logout">Logout</option>
            <option value="signup">Signup</option>
            <option value="signup_failed">Signup Failed</option>
            <option value="mcp_request">MCP Request</option>
            <option value="mcp_auth_failed">MCP Auth Failed</option>
          </select>
          <input
            type="text"
            placeholder="Filter by user..."
            value={filters.user}
            onChange={(e) => handleFilterChange('user', e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
          <input
            type="text"
            placeholder="Search path..."
            value={filters.search}
            onChange={(e) => handleFilterChange('search', e.target.value)}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm"
          />
        </div>

        {/* Table */}
        <div className="bg-white rounded-xl shadow-md border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Timestamp</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Event</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Method</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Path</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">User</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">IP</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Status</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Duration</th>
                  <th className="px-4 py-3 text-left font-semibold text-gray-600">Detail</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading && logs.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-8 text-center text-gray-400">
                      Loading...
                    </td>
                  </tr>
                ) : logs.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-8 text-center text-gray-400">
                      No logs found
                    </td>
                  </tr>
                ) : (
                  logs.map((log) => (
                    <tr key={log.id} className="hover:bg-gray-50 transition">
                      <td className="px-4 py-2 whitespace-nowrap text-gray-500 font-mono text-xs">
                        {formatTimestamp(log.timestamp)}
                      </td>
                      <td className="px-4 py-2">
                        <EventBadge type={log.event_type} />
                      </td>
                      <td className="px-4 py-2">
                        <MethodBadge method={log.method} />
                      </td>
                      <td className="px-4 py-2 font-mono text-xs max-w-xs truncate">
                        {log.path}
                      </td>
                      <td className="px-4 py-2">{log.user || '-'}</td>
                      <td className="px-4 py-2 font-mono text-xs">{log.ip_address || '-'}</td>
                      <td className="px-4 py-2">
                        <StatusBadge code={log.status_code} />
                      </td>
                      <td className="px-4 py-2 text-xs text-gray-500">
                        {log.duration_ms != null ? `${log.duration_ms.toFixed(0)}ms` : '-'}
                      </td>
                      <td className="px-4 py-2 text-xs text-gray-500 max-w-xs truncate">
                        {log.detail || '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-gray-500">
              Page {page + 1} / {totalPages}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 0}
                className="px-3 py-1 border border-gray-300 rounded-lg text-sm disabled:opacity-40 hover:bg-gray-100 transition"
              >
                Previous
              </button>
              <button
                onClick={() => handlePageChange(page + 1)}
                disabled={page >= totalPages - 1}
                className="px-3 py-1 border border-gray-300 rounded-lg text-sm disabled:opacity-40 hover:bg-gray-100 transition"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

function formatTimestamp(ts: string): string {
  const d = new Date(ts);
  return d.toLocaleString('fr-FR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

const EventBadge: React.FC<{ type: string | null }> = ({ type }) => {
  const colors: Record<string, string> = {
    login: 'bg-green-100 text-green-800',
    logout: 'bg-orange-100 text-orange-800',
    login_failed: 'bg-red-100 text-red-800',
    signup: 'bg-blue-100 text-blue-800',
    signup_failed: 'bg-red-100 text-red-800',
    mcp_request: 'bg-purple-100 text-purple-800',
    mcp_auth_failed: 'bg-red-100 text-red-800',
    request: 'bg-gray-100 text-gray-600',
  };
  const color = colors[type || ''] || colors.request;
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {type || 'request'}
    </span>
  );
};

const MethodBadge: React.FC<{ method: string }> = ({ method }) => {
  const colors: Record<string, string> = {
    GET: 'text-blue-600',
    POST: 'text-green-600',
    PUT: 'text-yellow-600',
    DELETE: 'text-red-600',
  };
  return (
    <span className={`font-mono text-xs font-bold ${colors[method] || 'text-gray-600'}`}>
      {method}
    </span>
  );
};

const StatusBadge: React.FC<{ code: number }> = ({ code }) => {
  let color = 'bg-gray-100 text-gray-600';
  if (code >= 200 && code < 300) color = 'bg-green-100 text-green-800';
  else if (code >= 400 && code < 500) color = 'bg-yellow-100 text-yellow-800';
  else if (code >= 500) color = 'bg-red-100 text-red-800';
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>{code}</span>
  );
};

export default LogsPage;
