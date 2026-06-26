from pathlib import Path

from deploy.brand_streamlit_shell import branded_index_html


ROOT = Path(__file__).resolve().parent


def test_streamlit_shell_branding_replaces_default_title():
    html = "<html><head>\n    <title>Streamlit</title>\n</head><body></body></html>"
    branded = branded_index_html(html)

    assert "<title>CogniSweep | Localization SaaS Workspace</title>" in branded
    assert 'property="og:title"' in branded
    assert "Streamlit</title>" not in branded


def test_static_share_preview_is_cognisweep_branded():
    html = (ROOT / "deploy" / "public" / "share-preview.html").read_text(encoding="utf-8")

    assert "CogniSweep | Localization SaaS Workspace" in html
    assert 'property="og:title"' in html
    assert "cognisweep-logo.png" in html
    assert "Streamlit" not in html


def test_caddy_serves_social_preview_before_streamlit_proxy():
    caddyfile = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")

    assert "@socialPreview" in caddyfile
    assert "WhatsApp" in caddyfile
    assert "/share-preview.html" in caddyfile
    assert "reverse_proxy errorsweep-app:8501" in caddyfile
