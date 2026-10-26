# Diagnostic interpretation and lab exercises

## How to interpret the three layers

| DNS | TCP | HTTP | Likely area to investigate |
|---|---|---|---|
| Fail | Fail | Fail | Resolver, hostname, or upstream reachability. A DNS failure does not prove the service is down. |
| Pass | Fail | Fail | Server/listener, port, local/remote firewall, routing. |
| Pass | Pass | Fail | Application-layer behavior, HTTP status, TLS, or server response. |
| Pass | Pass | Pass | Basic connectivity and the requested HTTP path are working *at that moment*. |

A TCP check performs its own name resolution when passed a hostname, so results can differ over time. HTTP may also resolve the hostname independently. Results are separate observations, not a packet-level traceroute.

## Safe lab: local-only server

1. Run the CLI on `127.0.0.1:18765` before starting a server. Expect DNS PASS, TCP FAIL, HTTP FAIL and exit code 1.
2. Start `python -m http.server 18765 --bind 127.0.0.1` in a separate PowerShell window. Re-run CLI; expect all three to pass and exit code 0.
3. Pass `--url http://127.0.0.1:18765/missing-page`. Expect DNS/TCP PASS, HTTP FAIL with 404, exit code 1.
4. Open `reports/diagnostics.jsonl` and compare timestamps, latency, and the error/HTTP status evidence.
5. Stop the test server with Ctrl+C.

## Independent engineering challenge

Implement a tested `--quiet` flag that suppresses per-check terminal messages but **still writes the JSONL report and preserves exit codes**. Update README and add at least two tests. Don't modify historical reports or publish them to Git.

## Future batches

- Evidence-based diagnostic summaries based on combinations of observations (implemented in Batch 2).
- Extra simulated failure modes, latency statistics, and richer machine-readable reports.
- Cross-platform GitHub Actions tests and publication polish.
