from pathlib import Path

from email_templates import render_transactional_email


def test_email_template_escapes_dynamic_html_fields():
    payload = render_transactional_email(
        subject="Injected <subject>",
        body="<script>alert(1)</script>\n\nLine <b>two</b>",
        event_type="job.assigned",
        metadata={
            "workspace": "<img src=x onerror=alert(1)>",
            "headline": "<svg/onload=alert(2)>",
            "preheader": "Pre <tag>",
            "job_url": "https://example.com/jobs/123?name=<bad>",
        },
    )

    html = payload["html"]
    assert "<script>alert(1)</script>" not in html
    assert "<svg/onload=alert(2)>" not in html
    assert "<img src=x onerror=alert(1)>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;svg/onload=alert(2)&gt;" in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "https://example.com/jobs/123?name=&lt;bad&gt;" in html


def test_email_template_rejects_non_http_cta_urls():
    payload = render_transactional_email(
        subject="Reset",
        body="Use this link",
        event_type="auth.password_reset",
        metadata={"reset_url": "javascript:alert(1)"},
        app_base_url="data:text/html,blocked",
    )

    assert payload["cta_url"] == ""
    assert "javascript:alert(1)" not in payload["html"]
    assert "data:text/html" not in payload["html"]


def test_email_dispatch_reads_use_explicit_platform_scope_reason():
    source = Path("email_dispatch_worker.py").read_text(encoding="utf-8")
    start = source.index("def dispatch_pending")
    end = source.index("def main", start)
    body = source[start:end]

    assert "include_all_workspaces=True" in body
    assert 'platform_scope_reason="email_dispatch_worker_queue"' in body


if __name__ == "__main__":
    test_email_template_escapes_dynamic_html_fields()
    test_email_template_rejects_non_http_cta_urls()
    test_email_dispatch_reads_use_explicit_platform_scope_reason()
    print("Email template security tests passed.")
