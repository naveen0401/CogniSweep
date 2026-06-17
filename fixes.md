# CogniSweep Platform Issues and Fixes

Based on a review of the CogniSweep build (v46), these are the currently tracked issues and their resolution status.

## Summary of All Tracked Issues

**Resolved in Latest Pass:**
1. XML Vulnerability (Billion Laughs) in DOCX Parsing
2. Server RAM Exhaustion from Media Uploads (OOM Risk)
3. Insufficient Media Preview Cleanup Trigger
4. SSRF (Server-Side Request Forgery) Vulnerability via BYO Base URL
5. Dead Code in Media Editor (`app.py`)
6. Dead Code in Navigation (`app.py`)
7. Duplicate Imports (`app.py`)
8. Unimplemented QA Rule (`qa_engine_global_v15.py`)
9. Missing UI Refresh in Admin Data Clear (`app.py`)
10. Performance Regression in QA Regex Compilation
11. Potential XML Vulnerability in Async Worker
12. Brittle JSON Parsing in AI Router
13. LibreTranslate Code Residuals
14. Thread Lock vs Process Lock Discrepancy
15. ZIP Bomb / RAM Exhaustion Risk in `app.py`
16. Excel Backlog Production Hardening
17. Transactional Email Template HTML Safety
18. Model Download Integrity Verification
19. Operational Backup PII Redaction
20. QA Engine Shim Public Surface

**Unresolved & New Issues:**
None currently tracked.

**Corrected Issues:**
1. Landing Page Legal Links
2. Landing Page Claim and Logo Neutrality
3. Legacy Editor Job Store Race Conditions
4. Floating Selected Cell Overlay While Scrolling
5. Local Timestamp Display
6. Scorecard Excel Source/Target Auto-Detection
7. Scorecard DOCX Table and Revision Extraction
8. Scorecard Reference Text and Pass Threshold
9. Media Preview Disk Cleanup
10. Code Duplication
11. MT Token and Emoji Preservation
12. Privacy Risk with the Public LanguageTool API
13. Massive Performance Bottleneck in QA Regex Compilation
14. Silent Failures
15. Unsupported LibreTranslate Route Removed
16. CUDA Out-Of-Memory Risk in MT Servers
17. Insecure Password Storage and Default Secrets
18. Race Conditions in Local JSON Storage
19. Unbounded Memory and Disk Growth
20. API Key Timing Attack Vulnerability
21. Silent Data Loss in QA Rule Parsing
22. Scorecard Preview and Manual Mapping Upgrade
23. Professional QA Report Export
24. QA Findings Column Order Polish
25. Rules Intelligence Wiring
26. Jobs Attachment Persistence Gap
27. Auth Verification and Reset Flow Gap
28. Local-Only Upload Storage
29. Heavy Workflow Request Blocking
30. Excel Backlog Production Hardening
31. Transactional Email Template HTML Safety
32. Model Download Integrity Verification
33. Operational Backup PII Redaction
34. QA Engine Shim Public Surface

## Resolved in Latest Pass

### 1. XML Vulnerability (Billion Laughs) in DOCX Parsing
*   **The Issue:** The `_docx_table_rows` function in `app.py` had been reverted to the standard library XML parser.
*   **The Fix:** `app.py` now imports `defusedxml.ElementTree`, rejects DTD/entity declarations before DOCX XML parsing, and `requirements.txt` includes `defusedxml>=0.7.1`. *(Verified fixed)*.

### 2. Server RAM Exhaustion from Media Uploads (OOM Risk)
*   **The Issue:** Media preview and transcription paths could load uploaded media into server RAM with `.getvalue()`.
*   **The Fix:** Media uploads now stream to disk in chunks through `stream_uploaded_file_to_path`; transcription uses file-path transcription and setup previews use the local preview file instead of loading the upload into memory. *(Verified fixed)*.

### 3. Insufficient Media Preview Cleanup Trigger
*   **The Issue:** Stale local media previews were cleaned only during new media saves.
*   **The Fix:** `maybe_cleanup_media_preview_files` now runs from `render_app` with a throttled request-based cleanup interval, while uploads still force cleanup before saving. *(Verified fixed)*.

### 4. SSRF (Server-Side Request Forgery) Vulnerability via BYO Base URL
*   **The Issue:** BYO AI base URLs could point to localhost, loopback, private networks, or cloud metadata addresses.
*   **The Fix:** `managed_ai_router.py` now validates custom OpenAI-compatible base URLs and blocks localhost, local/internal hostnames, private/link-local/reserved IPs, and metadata endpoints such as `169.254.169.254`. *(Verified fixed)*.

### 5. Dead Code in Media Editor (`app.py`)
*   **The Issue:** In `render_external_media_editor`, an unconditional `return` after `render_reference_media_editor_shell` left the Streamlit fallback editor unreachable.
*   **The Fix:** The reference media editor is now gated behind an explicit session fallback flag, so the legacy Streamlit fallback can still be reached when needed instead of being hidden behind unconditional dead code. *(Verified fixed)*.

### 6. Dead Code in Navigation (`app.py`)
*   **The Issue:** In `render_navigation`, an unconditional `return` after rendering the HTML topnav prevented the legacy Streamlit column navigation from ever executing.
*   **The Fix:** The legacy navigation is now reachable through an explicit fallback flag while the HTML topnav remains the normal default. *(Verified fixed)*.

### 7. Duplicate Imports (`app.py`)
*   **The Issue:** `Workbook` was imported twice on the same line.
*   **The Fix:** The duplicate `Workbook` import was removed. *(Verified fixed)*.

### 8. Unimplemented QA Rule (`qa_engine_global_v15.py`)
*   **The Issue:** `rule_telugu_malformed_cluster_hint` was registered but only returned an empty list.
*   **The Fix:** The rule now flags high-confidence Telugu Unicode cluster issues including repeated virama, dangling virama, and orphan dependent vowel/sign marks, with regression coverage. *(Verified fixed)*.

### 9. Missing UI Refresh in Admin Data Clear (`app.py`)
*   **The Issue:** Clicking "Clear all demo workspace data" cleared session state but did not rerun the page immediately.
*   **The Fix:** The clear-all action now sets a success flag and calls `st.rerun()`, so the refreshed admin UI immediately reflects the cleared data. *(Verified fixed)*.

### 10. Performance Regression in QA Regex Compilation
*   **The Issue:** The `rule_offline_correction_dictionary` function in `qa_engine_global_v15.py` re-parses and re-compiles correction rules for every segment.
*   **The Fix:** Correction dictionaries are now cached by content for the duration of the run, with regression coverage in `test_qa_correction_cache.py`. *(Verified fixed)*.

### 11. Potential XML Vulnerability in Async Worker
*   **The Issue:** The `async_workflow_processor.py` uses the `python-docx` library to parse DOCX files, which is inconsistent with the main application's use of `defusedxml` for security hardening.
*   **The Fix:** Async DOCX parsing now rejects DTD/entity declarations and parses DOCX XML through `defusedxml`, with size limits and regression coverage in `test_async_docx_security.py`. *(Verified fixed)*.

### 12. Brittle JSON Parsing in AI Router
*   **The Issue:** The `_extract_json_object` function in `managed_ai_router.py` uses a simple string search for `{` and `}` to find JSON in LLM responses.
*   **The Fix:** AI response extraction now scans with `json.JSONDecoder().raw_decode` and prefers structured payloads with findings/items, with regression coverage in `test_ai_json_extraction.py`. *(Verified fixed)*.

### 13. LibreTranslate Code Residuals
*   **The Issue:** Despite being marked as resolved (Corrected Issue #15), `local_translation_engine.py` still contains and defaults to `translate_with_libretranslate`.
*   **The Fix:** Unsupported LibreTranslate code paths were removed; the local translation router now defaults to supported self-hosted/generic routes and refuses unsupported providers without network calls. *(Verified fixed)*.

### 14. Thread Lock vs Process Lock Discrepancy
*   **The Issue:** `production_persistence.py` and `editor_job_store.py` use `threading.Lock()`, which is a thread lock, not the "process lock" claimed in Corrected Issue #18. This leaves a race condition vulnerability if deployed with multiple worker processes.
*   **The Fix:** Local JSON fallback storage now uses a stdlib OS file lock (`msvcrt.locking` on Windows, `fcntl.flock` on Unix) plus re-entrant thread locks. Editor job updates, SaaS collection upserts/deletes, and usage-log appends lock the whole read-modify-write operation. *(Verified fixed)*.

### 15. ZIP Bomb / RAM Exhaustion Risk in `app.py`
*   **The Issue:** While media files stream to disk, `parse_rules_zip` and DOCX parsing still use `.getvalue()` and `zf.read()`, reading fully into memory and posing an OOM risk for overly large ZIP payloads.
*   **The Fix:** Rules ZIPs and Office ZIP containers now use hard upload, file-count, expanded-size, per-member, and XML member read limits. Rules parsing no longer uses `.getvalue()` or direct `zf.read()`, and DOCX/PPTX extraction no longer uses direct `archive.read()`. *(Verified fixed)*.

### 16. Excel Backlog Production Hardening
*   **The Issue:** Remaining audit backlog items called out public worker/billing/Redis ports, optional async receiver tokens, email header injection risk, default public object URLs, and missing release-gate coverage for those contracts.
*   **The Fix:** Production compose now binds worker, billing receiver, and Redis ports to localhost; the async receiver fails closed without a production token and uses constant-time token comparison; outbound email headers and addresses reject newline injection; public object URLs are disabled unless explicitly enabled; and release checks/CI now enforce these contracts. *(Verified fixed)*.

### 17. Transactional Email Template HTML Safety
*   **The Issue:** Transactional email templates escaped body/headline/fact HTML, but metadata-supplied CTA URLs were not explicitly restricted to safe web schemes.
*   **The Fix:** Email CTA links now accept only `http` and `https` URLs with a host, while script/data-style URLs are dropped. Regression coverage verifies HTML escaping and unsafe CTA rejection. *(Verified fixed)*.

### 18. Model Download Integrity Verification
*   **The Issue:** The local model download helper fetched Hugging Face model artifacts without verifying trusted checksums.
*   **The Fix:** `download_models.ps1` now requires a SHA-256 checksum manifest by default, verifies every downloaded non-cache file with `Get-FileHash`, and exposes `-SkipChecksumVerification` only for explicit local experiments. A manifest example and release-gate regression coverage were added. *(Verified fixed)*.

### 19. Operational Backup PII Redaction
*   **The Issue:** Operational backups redacted secrets and tokens, but common PII fields such as email, names, recipients, actors, and phone numbers were not explicitly covered by the redaction map.
*   **The Fix:** The backup worker now redacts common PII keys in nested records, still excludes `auth_tokens`, and release-gate coverage verifies PII redaction behavior. *(Verified fixed)*.

### 20. QA Engine Shim Public Surface
*   **The Issue:** Legacy `qa_engine_global_v13.py` and `qa_engine_global_v14.py` shims used wildcard re-exports without an explicit public symbol list.
*   **The Fix:** Both compatibility shims now expose `__all__` from the canonical v15 public surface, with regression coverage. *(Verified fixed)*.

## Unresolved & New Issues

None currently tracked.

---

## Corrected Issues

### 1. Landing Page Legal Links
*   **The Issue:** The landing page and consent flows needed readable Terms, Privacy, and Security links.
*   **The Fix:** Public Terms, Privacy, and Security pages are available, footer links are clickable, and login/signup compliance text links to Terms and Privacy. *(Verified fixed)*.

### 2. Landing Page Claim and Logo Neutrality
*   **The Issue:** Landing copy should avoid unsupported third-party award labels, real customer claims, and percentage-style performance claims.
*   **The Fix:** The landing page uses fictitious/logo-neutral names and capability badges, with percentage-style quality metrics replaced by neutral product-status labels. *(Verified fixed)*.

### 3. Legacy Editor Job Store Race Conditions
*   **The Issue:** The legacy fallback editor job store risked JSON corruption if multiple saves happened at the same time.
*   **The Fix:** `editor_job_store.py` now uses a write lock, atomic temp-file writes with `os.replace`, and logging for read/cleanup failures. *(Verified fixed)*.

### 4. Floating Selected Cell Overlay While Scrolling
*   **The Issue:** Streamlit dataframe/data editor active-cell overlays could remain visible outside the table while scrolling.
*   **The Fix:** Added global and CAT-editor-specific dataframe clipping CSS plus a scroll/wheel listener that blurs stale grid overlay inputs during page scroll. *(Verified fixed)*.

### 5. Local Timestamp Display
*   **The Issue:** Owner Console and related tables displayed raw UTC ISO strings.
*   **The Fix:** Browser/local timezone-aware timestamp formatting is applied to persisted jobs, usage logs, audit logs, payments, workspaces, users, projects, and job tables. *(Verified fixed)*.

### 6. Scorecard Excel Source/Target Auto-Detection
*   **The Issue:** Scorecard uploads with metadata rows before the real table header could be parsed from the wrong row.
*   **The Fix:** Smart header-row detection, purpose-aware target selection, and manual mapping preview are implemented. *(Verified fixed)*.

### 7. Scorecard DOCX Table and Revision Extraction
*   **The Issue:** DOCX scorecard uploads needed deeper table extraction than the basic visible table reader.
*   **The Fix:** Lower-level DOCX XML table extraction is present, with support for detected table choices and combined DOCX tables. *(Verified fixed)*.

### 8. Scorecard Reference Text and Pass Threshold
*   **The Issue:** Reference-only `Description:` / `Definition:` text could be treated as source, and pass criteria needed a strict 95% threshold.
*   **The Fix:** Reference context is stripped from source scoring, empty source rows are skipped, and scorecard `PASS` now requires 95% or above. *(Verified fixed)*.

### 9. Media Preview Disk Cleanup
*   **The Issue:** Local media preview files could accumulate in the temp directory.
*   **The Fix:** Added TTL-based media preview cleanup using `ERRORSWEEP_MEDIA_PREVIEW_TTL_SECONDS`, defaulting to 48 hours, and run cleanup before saving new media previews. *(Fixed in v46 media cleanup pass)*.

### 10. Code Duplication
*   **The Issue:** `qa_engine_global_v13.py`, `v14.py`, and `v15.py` previously risked drift if duplicated.
*   **The Fix:** `qa_engine_global_v13.py` and `qa_engine_global_v14.py` are compatibility shims that re-export the canonical `qa_engine_global_v15.py` implementation. *(Verified fixed)*.

### 11. MT Token and Emoji Preservation
*   **The Issue:** Reviewed exports could contain altered protection tokens such as `PH000Token`, missing `{{...}}` placeholders, missing leading emoji/icons, and mojibake leading bullets like `Â`.
*   **The Fix:** Hardened self-hosted MT placeholder restoration and visual-prefix preservation. *(Verified fixed)*.

### 12. Privacy Risk with the Public LanguageTool API
*   **The Issue:** The fallback grammar engine could send segment text to public endpoints when configured for public mode.
*   **The Fix:** Defaulted to local mode and strictly warned users before enabling public checks. *(Verified fixed)*.

### 13. Massive Performance Bottleneck in QA Regex Compilation
*   **The Issue:** `_apply_correction_to_text` could recompile regular expressions for every dictionary entry against every segment.
*   **The Fix:** Pre-compiled regex patterns once when dictionary entries are parsed. *(Verified fixed)*.

### 14. Silent Failures
*   **The Issue:** Several paths used blanket exception handling that hid useful debugging information.
*   **The Fix:** Added proper `logging.warning/error` across the application. *(Verified fixed)*.

### 15. Unsupported LibreTranslate Route Removed
*   **The Issue:** LibreTranslate was considered as a fallback route, but it was intentionally removed from CogniSweep after licensing/commercial-use review.
*   **The Fix:** CogniSweep now stays on commercial-safe self-hosted/BYO translation routes and preserves batch processing through the supported MT router. *(Verified fixed)*.

### 16. CUDA Out-Of-Memory Risk in MT Servers
*   **The Issue:** Transformer model caches could retain too many models at once.
*   **The Fix:** Reduced model cache sizes and added CUDA cache clearing. *(Verified fixed)*.

### 17. Insecure Password Storage and Default Secrets
*   **The Issue:** Plain-text fallback secrets and default session secrets could be unsafe in production if not configured.
*   **The Fix:** Implemented PBKDF2 password hashing and enforced custom production secrets. *(Verified fixed)*.

### 18. Race Conditions in Local JSON Storage
*   **The Issue:** Local fallback persistence could corrupt JSON under concurrent writes.
*   **The Fix:** Implemented atomic writes with a process lock in `production_persistence.py`. *(Verified fixed)*.

### 19. Unbounded Memory and Disk Growth
*   **The Issue:** Session lists and local usage logs could grow indefinitely.
*   **The Fix:** Added session collection trimming and local JSONL usage-log rotation. *(Verified fixed)*.

### 20. API Key Timing Attack Vulnerability
*   **The Issue:** MT server API keys were previously compared with normal string equality.
*   **The Fix:** Updated authentication checks to use `hmac.compare_digest`. *(Verified fixed)*.

### 21. Silent Data Loss in QA Rule Parsing
*   **The Issue:** QA rule parsing could silently truncate large rule arrays.
*   **The Fix:** Removed arbitrary slicing and added zip expansion validations. *(Verified fixed)*.

### 22. Scorecard Preview and Manual Mapping Upgrade
*   **The Upgrade:** Scorecard generation needed a pre-export review step so unusual client formats could be corrected before producing the final LQA workbook.
*   **The Fix:** Added a mapping preview panel for Scorecards that detects candidate Excel sheets, DOCX tables, CSV headers, source columns, and target columns. Users can override table/source/target choices, reviewer targets default to an auto cascade when `Suggested Translation` is blank, and DOCX uploads can use all detected tables together. *(Added in v46 Scorecard Intelligence v2 pass)*.

### 23. Professional QA Report Export
*   **The Issue:** The QA section exported a raw CSV with technical row fields and a long `issues` string, which was not suitable as a client-facing QA deliverable.
*   **The Fix:** Added a polished Excel QA workbook with Summary, QA Findings, Segment Overview, and Review Notes sheets. The QA page now shows score/result metrics, one finding per row, severity styling, and keeps CSV downloads as secondary exports. *(Fixed in v46 QA reporting pass)*.

### 24. QA Findings Column Order Polish
*   **The Issue:** The professional QA Findings sheet listed severity/category before the actual source and target text, which made review flow feel unnatural.
*   **The Fix:** Reordered QA Findings columns to `Finding ID`, `Segment ID`, `Source Text`, `Target Text`, `Suggested Target`, `Error Category`, `Severity`, `Issue`, `Explanation`, `Check`, `Confidence`, and `Rule ID`. The in-app findings preview now uses the same order. *(Fixed in v46 QA reporting polish pass)*.

### 25. Rules Intelligence Wiring
*   **The Issue:** Uploaded rules ZIP files and saved Memory & Rules were parsed for QA, but translation and optional AI QA did not consistently receive the same client rule context.
*   **The Fix:** Added a merged workspace rule pack that extracts glossary, DNT, and instruction hints from uploaded ZIP files, combines them with saved glossary/DNT/TM memory, applies protected terms during built-in MT, and includes the same rule summary in BYO-key translation and AI QA prompts. *(Fixed in v46 Rules Intelligence v1 pass)*.

### 26. Jobs Attachment Persistence Gap
*   **The Issue:** Manual Jobs uploads were restored in the UI, but production persistence did not yet allow the job/project attachment fields through to Supabase.
*   **The Fix:** Added project/job attachment fields to the SaaS persistence allow-list and Supabase release schema so `project_id`, `project`, `attachment_count`, and `attachments_json` can survive production storage. *(Fixed in latest tracker reconciliation pass)*.

### 27. Auth Verification and Reset Flow Gap
*   **The Issue:** The auth-token schema existed, but the app did not yet expose public email verification and password reset routes.
*   **The Fix:** Added hashed one-time verification/reset tokens, public verify/reset pages, production sign-in enforcement for unverified persisted users, duplicate-signup blocking, and notification outbox links. *(Fixed in latest auth onboarding pass)*.

### 28. Local-Only Upload Storage
*   **The Issue:** Manual job attachments and media previews still depended on local disk paths, which is unsafe for public multi-instance deployment.
*   **The Fix:** Added a cloud object storage adapter with local fallback plus Supabase Storage, S3, and GCS support. Job attachments and media previews now store through the adapter and persist provider, bucket, storage key, local cache, public URL, SHA-256, size, and MIME metadata. *(Fixed in cloud object storage pass)*.

### 29. Heavy Workflow Request Blocking
*   **The Issue:** QA and Pro workflows still ran inside the Streamlit request even though lifecycle records existed, which is risky for public SaaS traffic and larger files.
*   **The Fix:** Added an external async worker bridge for HTTP workers or Redis/Celery-style queues. QA and Pro now hand off uploaded input/rules manifests to the worker when configured, while local development keeps the existing inline behavior. *(Fixed in async worker bridge pass)*.

### 30. Excel Backlog Production Hardening
*   **The Issue:** Lower-priority Excel audit findings remained around production service exposure, async worker token posture, object-storage URL defaults, and notification email header safety.
*   **The Fix:** Added fail-closed async token enforcement, constant-time bearer-token comparison, email header sanitization, localhost-only internal compose ports, opt-in public object URLs, and a dedicated regression test plus release-gate wiring. *(Verified fixed)*.

### 31. Transactional Email Template HTML Safety
*   **The Issue:** User-controlled notification metadata could provide unsafe CTA URL schemes even though email text fields were escaped.
*   **The Fix:** CTA URLs are filtered through a strict web-link allowlist and release-gate coverage now includes `test_email_template_security.py`. *(Verified fixed)*.

### 32. Model Download Integrity Verification
*   **The Issue:** Downloaded self-hosted MT model files were not checked against expected hashes before local use.
*   **The Fix:** Added default SHA-256 manifest enforcement to the model downloader, an example manifest format, and `test_model_download_integrity.py` in the release gate. *(Verified fixed)*.

### 33. Operational Backup PII Redaction
*   **The Issue:** Backup snapshots could preserve obvious PII even after secret/token redaction.
*   **The Fix:** Added common PII fields to backup redaction and `test_backup_redaction.py` to keep the behavior covered. *(Verified fixed)*.

### 34. QA Engine Shim Public Surface
*   **The Issue:** Compatibility shims obscured their public export surface.
*   **The Fix:** Added explicit `__all__` delegation to the canonical v15 QA engine and extended shim tests. *(Verified fixed)*.
