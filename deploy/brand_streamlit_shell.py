"""Brand Streamlit's static HTML shell for unfurlers and no-JS crawlers.

Streamlit updates the document title after its frontend boots, but link preview
crawlers such as WhatsApp usually read the first static HTML response and never
execute the app JavaScript. Patching the installed shell in the Docker image
keeps previews and no-JS metadata branded as CogniSweep.
"""

from __future__ import annotations

import re
from pathlib import Path

import streamlit


SHARE_TITLE = "CogniSweep | Localization SaaS Workspace"
SHARE_DESCRIPTION = (
    "CogniSweep is a SaaS workspace for translation, transcription, subtitling, "
    "localization QA, glossary, DNT, and translation memory workflows."
)
SHARE_URL = "https://www.cognisweep.com/solutions/software-localization-tool"
SHARE_IMAGE_URL = "https://www.cognisweep.com/cognisweep-logo.png"
FAVICON_ICO_URL = "/favicon.ico"
FAVICON_48_URL = "/favicon-48x48.png"
FAVICON_96_URL = "/favicon-96x96.png"
FAVICON_PNG_URL = "/favicon.png"
APPLE_TOUCH_ICON_URL = "/apple-touch-icon.png"
MARKER_START = "<!-- CogniSweep share metadata -->"
MARKER_END = "<!-- /CogniSweep share metadata -->"
ICON_LINK_PATTERN = re.compile(
    r"\s*<link\b(?=[^>]*\brel=[\"'](?:shortcut icon|icon|apple-touch-icon)[\"'])[^>]*>",
    flags=re.IGNORECASE,
)


def normalize_static_asset_paths(html: str) -> str:
    return html.replace("./static/", "/static/")


def share_metadata_block() -> str:
    return f"""    {MARKER_START}
    <title>{SHARE_TITLE}</title>
    <meta name="description" content="{SHARE_DESCRIPTION}" />
    <meta name="application-name" content="CogniSweep" />
    <link rel="shortcut icon" href="{FAVICON_ICO_URL}" />
    <link rel="icon" type="image/png" sizes="48x48" href="{FAVICON_48_URL}" />
    <link rel="icon" type="image/png" sizes="96x96" href="{FAVICON_96_URL}" />
    <link rel="icon" type="image/png" sizes="512x512" href="{FAVICON_PNG_URL}" />
    <link rel="apple-touch-icon" href="{APPLE_TOUCH_ICON_URL}" />
    <link rel="canonical" href="{SHARE_URL}" />
    <meta property="og:type" content="website" />
    <meta property="og:site_name" content="CogniSweep" />
    <meta property="og:title" content="{SHARE_TITLE}" />
    <meta property="og:description" content="{SHARE_DESCRIPTION}" />
    <meta property="og:url" content="{SHARE_URL}" />
    <meta property="og:image" content="{SHARE_IMAGE_URL}" />
    <meta property="og:image:alt" content="CogniSweep" />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:title" content="{SHARE_TITLE}" />
    <meta name="twitter:description" content="{SHARE_DESCRIPTION}" />
    <meta name="twitter:image" content="{SHARE_IMAGE_URL}" />
    {MARKER_END}"""


def branded_index_html(html: str) -> str:
    html = normalize_static_asset_paths(html)
    html = ICON_LINK_PATTERN.sub("", html)
    block = share_metadata_block()
    marked_pattern = re.compile(
        rf"\s*{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}",
        flags=re.DOTALL,
    )
    if MARKER_START in html and MARKER_END in html:
        return marked_pattern.sub("\n" + block, html, count=1)

    title_pattern = re.compile(r"\s*<title>.*?</title>", flags=re.DOTALL | re.IGNORECASE)
    if title_pattern.search(html):
        return title_pattern.sub("\n" + block, html, count=1)

    if "</head>" not in html:
        raise RuntimeError("Streamlit index.html has no </head> tag to brand")
    return html.replace("</head>", f"{block}\n  </head>", 1)


def streamlit_index_path() -> Path:
    return Path(streamlit.__file__).resolve().parent / "static" / "index.html"


def main() -> None:
    path = streamlit_index_path()
    html = path.read_text(encoding="utf-8")
    branded = branded_index_html(html)
    if branded != html:
        path.write_text(branded, encoding="utf-8")
    print(f"Branded Streamlit shell metadata in {path}")


if __name__ == "__main__":
    main()
