from pathlib import Path

from deploy.brand_streamlit_shell import branded_index_html


ROOT = Path(__file__).resolve().parent


def test_streamlit_shell_branding_replaces_default_title_and_favicon():
    html = (
        "<html><head>\n"
        '    <link rel="shortcut icon" href="./favicon.png" />\n'
        '    <script type="module" crossorigin src="./static/js/index.js"></script>\n'
        '    <link rel="stylesheet" crossorigin href="./static/css/index.css">\n'
        "    <title>Streamlit</title>\n"
        "</head><body></body></html>"
    )
    branded = branded_index_html(html)

    assert "<title>CogniSweep | Localization SaaS Workspace</title>" in branded
    assert 'rel="shortcut icon" href="/favicon.ico"' in branded
    assert 'rel="icon" type="image/png" href="/favicon.png"' in branded
    assert 'rel="apple-touch-icon" href="/apple-touch-icon.png"' in branded
    assert "./favicon.png" not in branded
    assert "./static/" not in branded
    assert 'src="/static/js/index.js"' in branded
    assert 'href="/static/css/index.css"' in branded
    assert 'rel="canonical" href="https://www.cognisweep.com/solutions/software-localization-tool"' in branded
    assert 'property="og:title"' in branded
    assert 'property="og:url" content="https://www.cognisweep.com/solutions/software-localization-tool"' in branded
    assert "Streamlit</title>" not in branded


def test_static_share_preview_is_cognisweep_branded():
    html = (ROOT / "deploy" / "public" / "share-preview.html").read_text(encoding="utf-8")

    assert "CogniSweep | Localization SaaS Workspace" in html
    assert 'property="og:title"' in html
    assert 'rel="canonical" href="https://www.cognisweep.com/solutions/software-localization-tool"' in html
    assert 'rel="shortcut icon" href="/favicon.ico"' in html
    assert 'rel="icon" type="image/png" href="/favicon.png"' in html
    assert 'rel="apple-touch-icon" href="/apple-touch-icon.png"' in html
    assert 'property="og:url" content="https://www.cognisweep.com/solutions/software-localization-tool"' in html
    assert "cognisweep-logo.png" in html
    assert "./favicon.png" not in html
    assert "Streamlit" not in html


def test_caddy_serves_social_preview_before_streamlit_proxy():
    caddyfile = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")

    assert "@socialPreview" in caddyfile
    assert "WhatsApp" in caddyfile
    assert "/share-preview.html" in caddyfile
    assert "@faviconFiles" in caddyfile
    assert "path /favicon.ico /favicon.png /apple-touch-icon.png" in caddyfile
    assert "@seoFiles" in caddyfile
    assert "path /robots.txt /sitemap.xml" in caddyfile
    assert caddyfile.index("@faviconFiles") < caddyfile.index("@seoFiles")
    assert caddyfile.index("@seoFiles") < caddyfile.index("@socialPreview")
    assert "reverse_proxy errorsweep-app:8501" in caddyfile


def test_static_seo_files_point_to_canonical_landing():
    robots = (ROOT / "deploy" / "public" / "robots.txt").read_text(encoding="utf-8")
    sitemap = (ROOT / "deploy" / "public" / "sitemap.xml").read_text(encoding="utf-8")

    canonical = "https://www.cognisweep.com/solutions/software-localization-tool"
    assert "User-agent: *" in robots
    assert "Allow: /" in robots
    assert "Sitemap: https://www.cognisweep.com/sitemap.xml" in robots
    assert f"<loc>{canonical}</loc>" in sitemap
    assert "<urlset" in sitemap


def test_static_favicon_files_exist_for_crawlers():
    public = ROOT / "deploy" / "public"

    assert (public / "favicon.ico").exists()
    assert (public / "favicon.png").exists()
    assert (public / "apple-touch-icon.png").exists()
