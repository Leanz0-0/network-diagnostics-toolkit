# Network Diagnostics Toolkit

A beginner-friendly, test-driven Python command-line troubleshooting tool for distinguishing **DNS resolution**, **TCP connectivity**, and **HTTP application responses**. Built as a practical IT infrastructure and networking portfolio project.

> **Status:** Batch 1 working prototype. Further diagnostic analysis, failure labs, and CI will follow. Not intended for production monitoring or network scanning.

## Features

- Resolve a hostname to unique IPv4/IPv6 addresses with the OS resolver.
- Attempt a connection to **one explicitly specified TCP port** with a timeout.
- Perform an HTTP(S) GET using the standard library and classify HTTP 2xx as success. Redirects are **not followed**.
- Measure the elapsed time of each check in milliseconds.
- Continue independent checks when another layer fails (useful for fault isolation).
- Record timestamps, results, status codes, errors, and latency to local **JSON Lines** (`.jsonl`) files.
- Validate host, port, timeout, and URL before making requests. Refuse URLs containing credentials or query strings.
- Test behavior with Python's `unittest` and a locally bound, temporary HTTP test server.

## Quick start (Windows PowerShell)

Requirements: Python 3.11+ (developed for Python 3.14). No third-party dependencies.

```powershell
cd "$HOME\Projects\network-diagnostics-toolkit"
py -V:3.14 -m venv .venv
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe .\src\main.py
```

By default, the tool targets **127.0.0.1:18765**. If no service is running there, DNS should succeed but TCP/HTTP checks should fail; this is an **expected diagnostic result**, not a program crash.

### Run against a local test web server

In **PowerShell window A**, from the project folder:

```powershell
.\.venv\Scripts\python.exe -m http.server 18765 --bind 127.0.0.1
```

Keep this window open. In **PowerShell window B**:

```powershell
cd "$HOME\Projects\network-diagnostics-toolkit"
.\.venv\Scripts\python.exe .\src\main.py
```

Stop the test server in window A with `Ctrl+C` when done.

### Other examples

```powershell
# DNS only (does not open a TCP connection)
.\.venv\Scripts\python.exe .\src\main.py --host localhost --only dns

# Test a specific path, using matching host and port
.\.venv\Scripts\python.exe .\src\main.py --host 127.0.0.1 --port 18765 --url http://127.0.0.1:18765/health

# Change report file location
.\.venv\Scripts\python.exe .\src\main.py --output reports\lab-1.jsonl
```

Note: An HTTP 404 from `/health` still proves that the HTTP server answered; the HTTP check correctly reports a non-2xx **application-level failure**.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All selected network checks succeeded, and the report was saved. |
| `1` | At least one diagnostic check failed; the report was saved. |
| `2` | Invalid command-line input (handled by argparse). |
| `3` | Report could not be saved. |

Unlike the Infrastructure Health Monitor, this troubleshooting CLI intentionally uses exit code **1** when a diagnostic check fails.

## Project structure

```text
network-diagnostics-toolkit/
├── src/
│   ├── main.py          # CLI entry point
│   ├── cli.py           # Validation, orchestration, output
│   ├── models.py        # Consistent check results
│   ├── dns_check.py     # OS resolver check
│   ├── tcp_check.py     # Single-port TCP connection
│   ├── http_check.py    # HTTP(S) response check
│   └── reporting.py     # Append-only JSONL records
├── tests/               # Unit tests + loopback integration tests
├── docs/
│   └── troubleshooting.md
└── .gitignore
```

## Limitations and responsible use

- Test only endpoints and ports you own or are authorized to troubleshoot.
- This tool does **not** scan multiple ports or collect remote inventory.
- OS-backed DNS lookup (`getaddrinfo`) does not guarantee it obeys the TCP/HTTP timeout; DNS may take longer.
- A successful TCP handshake does not prove an application is functioning; HTTP response checks add a separate layer.
- TLS failures are surfaced as connection errors; this prototype does not perform detailed certificate analysis.
- HTTPS verification uses the Python standard library's default certificate validation.
- Reports contain hostnames, paths, addresses, and error information: keep them private. URL credentials, query strings, and fragments are disallowed, but paths may still be sensitive.
- The CLI performs **one execution** per invocation; no scheduler, alerting service, or dashboard yet.

## Testing

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

All local integration tests use loopback (`127.0.0.1`) only. GitHub Actions will be added in a later batch.
