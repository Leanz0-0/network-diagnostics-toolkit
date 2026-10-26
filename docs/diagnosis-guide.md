# Evidence-based diagnostic guide

Each run writes a `diagnosis` object to the JSONL report and prints a short diagnosis with the next recommended troubleshooting step.

These are **observations and investigation suggestions**, not verified root causes. DNS, TCP, and HTTP checks each start a separate operation; they can disagree for transient reasons or because an environment changes between checks.

| Code | Observation | Investigation to consider |
|---|---|---|
| `checks_passed` | Every selected check succeeded | Verify user-specific requests or application logs if problems persist |
| `dns_resolution_failed` | DNS lookup failed or found no address | Hostname and resolver settings |
| `tcp_connection_refused` | A TCP connection was refused | Service listener, port, rejection rules |
| `tcp_connection_timeout` | A TCP connection timed out | Routing, filtering, service reachability |
| `tcp_connection_failed` | Another TCP error occurred | Review the recorded TCP error |
| `http_not_found` | HTTP 404 response | URL path and application routes |
| `http_authentication_required` | HTTP 401 response | Application login requirements |
| `http_access_forbidden` | HTTP 403 response | Access control and permission rules |
| `http_redirect` | HTTP 3xx response | Expected URL and redirect behavior |
| `http_client_error` | Other HTTP 4xx response | Request correctness and app permissions |
| `http_server_error` | HTTP 5xx response | App and reverse-proxy logs |
| `http_transport_failed` | HTTP did not return a usable status | TLS and HTTP protocol diagnostics |
| `mixed_results` | Independent checks disagree | Repeat tests and compare exact targets and timing |

## Safe local demonstration

In one PowerShell terminal:

```powershell
cd "$HOME\Projects\network-diagnostics-toolkit"
.\.venv\Scripts\python.exe -m http.server 18765 --bind 127.0.0.1
```

In a second terminal:

```powershell
cd "$HOME\Projects\network-diagnostics-toolkit"
.\.venv\Scripts\python.exe .\src\main.py
.\.venv\Scripts\python.exe .\src\main.py --url http://127.0.0.1:18765/missing
Get-Content .\reports\diagnostics.jsonl -Tail 2
```

When the server is stopped, a connection refusal should classify as `tcp_connection_refused`. With the server running, `/missing` should classify as `http_not_found`.

Do not put real credentials or sensitive paths into reports, and only test endpoints you are authorized to troubleshoot.
