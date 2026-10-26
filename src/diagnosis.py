"""Evidence-based guidance from separate DNS, TCP, and HTTP observations.

These classifications suggest a place to investigate, not a proven root cause.
"""

from models import CheckResult


def diagnose(results: list[CheckResult]) -> dict:
    """Return deterministic troubleshooting guidance for the selected checks."""
    if not results:
        raise ValueError("At least one diagnostic result is required")

    observed = {item.check: item for item in results}
    dns = observed.get("dns")
    tcp = observed.get("tcp")
    http = observed.get("http")

    evidence = [
        f"{item.check.upper()}: {'PASS' if item.success else 'FAIL'}"
        for item in results
    ]
    if http is not None and "status_code" in http.details:
        evidence.append(f"HTTP status: {http.details['status_code']}")
    if tcp is not None and tcp.error:
        evidence.append(f"TCP error: {tcp.error.split(':', 1)[0]}")

    def result(code: str, layer: str, summary: str, next_step: str) -> dict:
        return {
            "code": code,
            "layer": layer,
            "summary": summary,
            "next_step": next_step,
            "evidence": evidence,
        }

    # Separate checks can disagree as DNS and connections are retried independently.
    if (
        (dns is not None and not dns.success and
         ((tcp is not None and tcp.success) or (http is not None and http.success)))
        or (tcp is not None and not tcp.success and http is not None and http.success)
    ):
        return result(
            "mixed_results", "multiple",
            "Checks disagree; a single failed layer cannot be confirmed.",
            "Repeat the checks and compare timestamps, target address, and service state.",
        )

    if all(item.success for item in results):
        return result(
            "checks_passed", "none",
            "All selected checks succeeded at the time of testing.",
            "If users still report issues, inspect application logs and test the exact failing request.",
        )

    if dns is not None and not dns.success:
        return result(
            "dns_resolution_failed", "dns",
            "The resolver did not provide a usable address.",
            "Verify hostname spelling, DNS configuration, and the relevant DNS records.",
        )

    if tcp is not None and not tcp.success:
        error = (tcp.error or "").casefold()
        if "connectionrefusederror" in error or "winerror 10061" in error:
            return result(
                "tcp_connection_refused", "tcp",
                "The TCP connection was refused; no listening service may be available.",
                "Check whether the intended service is listening on the specified port and whether a firewall rejects connections.",
            )
        if "timeouterror" in error or "timed out" in error or "winerror 10060" in error:
            return result(
                "tcp_connection_timeout", "tcp",
                "The TCP connection timed out without completing.",
                "Check network reachability, packet filtering, routing, and service availability; a timeout alone does not identify the cause.",
            )
        return result(
            "tcp_connection_failed", "tcp",
            "The TCP connection could not be established.",
            "Review the TCP error, chosen host and port, routing, and service listener.",
        )

    if http is not None and not http.success:
        status = http.details.get("status_code")
        if status == 404:
            return result(
                "http_not_found", "http",
                "The HTTP server responded with 404 Not Found.",
                "Verify the requested path and application routes; basic HTTP reachability was demonstrated.",
            )
        if status == 401:
            return result(
                "http_authentication_required", "http",
                "The HTTP server responded with 401 Unauthorized.",
                "Check the application's expected authentication method; do not include credentials in diagnostic URLs.",
            )
        if status == 403:
            return result(
                "http_access_forbidden", "http",
                "The HTTP server responded with 403 Forbidden.",
                "Review application authorization rules or access controls.",
            )
        if isinstance(status, int) and 300 <= status < 400:
            return result(
                "http_redirect", "http",
                "The server returned a redirect; this tool intentionally did not follow it.",
                "Review the Location header using an authorized client and verify the expected URL.",
            )
        if isinstance(status, int) and 500 <= status < 600:
            return result(
                "http_server_error", "http",
                "The web service returned an HTTP 5xx error.",
                "Inspect application and reverse-proxy logs for the failing request.",
            )
        if isinstance(status, int) and 400 <= status < 500:
            return result(
                "http_client_error", "http",
                "The web service returned an HTTP 4xx error.",
                "Review the request, target path, and application permissions.",
            )
        return result(
            "http_transport_failed", "http",
            "The HTTP request failed without a successful response.",
            "Examine TLS, HTTP protocol, connection, and application service errors.",
        )

    return result(
        "unclassified_failure", "multiple",
        "At least one check failed, but the failure does not match a known rule.",
        "Inspect individual result details and repeat the targeted check.",
    )
