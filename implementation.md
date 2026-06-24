# CogniSweep Graphical Implementation Guide

## Implemented Editor Productivity Foundations (CAT & Media)
To further bridge the gap between the Streamlit-based UI and native desktop localization tools (like Phrase, memoQ, or Ooona), the following editor productivity foundations are now implemented:

*   **Completed:** Predictive typing foundations in CAT editors using TM, glossary, DNT, and protected-token suggestions, with one-click insertion into the selected segment.
*   **Completed:** Streamlit-native media timeline upgrade with an interactive HTML timeline band alongside waveform previews and precise numeric timing controls. A fully bidirectional React drag component remains a future custom-component option, but the product now has a richer timeline foundation.
*   **Completed:** Media timing quick-adjust tools added to the focused subtitle/transcription workspace, with duration, CPS, neighbor-gap metrics, move/trim/snap/set-duration actions, and regression-tested timing math.
*   **Completed:** Separate full-screen media editor shell now has matching timing quick actions, active duration/gap metrics, autosaved timecode updates, and reference-asset regression coverage.
*   **Completed:** Collaboration/presence foundation with visible selected-row lock ownership, lock takeover/release controls, and persisted row lock metadata.
*   **Completed:** Inline comments and `@mention` support at segment level, with author, timestamp, mention extraction, and persisted comment metadata.
*   **Completed:** Advanced global find and replace for editor rows, including source/target/all scope, regex mode, case sensitivity, bulk replacement counts, and target repair after replacement.
*   **Completed:** Keyboard workflow foundation with a browser shortcut listener and in-editor shortcut panel for professional CAT commands such as approve, top suggestion, copy source, and find/replace.
*   **Completed:** Contextual copilot panel in the right editor rail, giving deterministic row-level guidance from glossary, DNT, protected tokens, target length, and reviewer questions without leaving the editor.
*   **Completed:** Segment completion confirmation checkboxes added across CAT Human Review, separate CAT jobs, and subtitle/transcription media editors, placed after the target cell, with confirmed/pending counts, pending filters, and download gating until every segment is ticked complete.
*   **Completed:** Editable grid scroll protection and single-click edit helper added so escaped active-cell overlays are hidden while scrolling, source cells remain protected from deletion, and reviewers can enter edit mode with one click.
*   **Completed:** Separate CAT editor chrome upgraded into a single-page editor workspace with sticky top navigation, functional Context/Quality/TM/Glossary tabs, a compact CAT-style center grip for collapsed/compact/large context sizing, real focused-segment toolbar actions, internally sized editor/detail panels, and a frozen bottom task-status bar with segment, confirmation, pending, language, and word-count details.
*   **Completed:** Separate CAT editor single-page polish added with in-place Streamlit resource tabs instead of browser-opening links, restored compact context visibility, a shorter scrollable right-side details rail, and top-positioned Save/Approve/Submit/Download actions.
*   **Completed:** Separate CAT editor rearranged into a Smartling-style single-pager: all controls now sit in fixed compact bands, find/replace opens as an inline popover, the grid and right rail use internal scrolling, and browser-page scrolling is disabled for the editor workspace.
*   **Completed:** Separate CAT editor grid simplified by removing the focused-segment dropdown and hiding nonessential Status, Notes, and Location columns from the main editing grid while retaining those fields internally for QA, downloads, and audit.
*   **Completed:** Separate CAT editor action band spacing corrected to prevent overlap with the tab/context row, with the download control shortened to `Export` and forced single-line button labels.
*   **Completed:** Separate CAT editor command controls compressed into one single-line toolbar so resource tabs, panel sizing, Save/Approve/Submit/Export/Refresh/Back actions, and segment counters stay on the same row.
*   **Completed:** Separate CAT editor band spacing hardened so the title bar, command toolbar, context preview, search/filter controls, and format buttons reserve their own vertical space and do not overlap.
*   **Completed:** Separate CAT editor frontend rewritten into isolated Streamlit layout bands: sticky job header, bordered resource navigation, separate workflow action row, bordered context/resource panel, search/filter row, focused segment toolbar, 75/25 editor workspace, and dark card-based right rail.
*   **Completed:** Separate CAT editor context/resources panel now follows the focused segment through an explicit segment focus selector and automatically updates focus from edited/confirmed grid rows when Streamlit reports row edits.
*   **Completed:** Separate CAT editor grid now estimates row height from visible source/target segment length and passes adaptive `row_height` into `st.data_editor`, giving longer English/Telugu segments more vertical space instead of forcing every segment into one-line rows.
*   **Completed:** Separate CAT editor single-click editing improved by removing non-focused input suppression from the grid and focusing the Streamlit data-editor overlay immediately after the one-click edit helper opens a cell.

## Proposed Public SaaS Launch Requirements
Before opening CogniSweep to public sign-ups and paying customers, the following infrastructural and commercial upgrades are required to transition from a Streamlit MVP to a scalable SaaS:

*   **Billing & Subscription Gateway:** Foundation is implemented with plan catalog, subscriptions, checkout-intent records, usage allowance display, payment records, draft invoice/receipt records, and Platform Settings diagnostics. External launch gate: live Stripe/Razorpay checkout credentials, tax-advisor approved invoice templates, provider invoices, and reconciliation.
*   **Asynchronous Task Queues:** Foundation is implemented with durable task lifecycle records, progress, retry requests, Jobs/Platform visibility, an external handoff adapter, a standalone HTTP task receiver, and a worker-side QA/Pro processor for queued handoffs. External launch gate: deploy receiver/processor as managed services and test high-volume jobs with production buckets and secrets.
*   **Cloud Object Storage:** Foundation is implemented with workspace-scoped file manifests, size/MIME/SHA metadata, assignment upload tracking, media preview storage, and a provider adapter for local fallback, Supabase Storage, S3, and GCS. External launch gate: configure production bucket and credentials.
*   **Authentication & Onboarding Flows:** Password hashing, compliance-gated signup/login, persisted users, email verification links, password-reset links, and auth-token schema are present. External launch gate: real OAuth/SAML provider wiring and live email deliverability testing.
*   **Legal & Compliance Finalization:** Draft Terms, Privacy, Security, Cookie Notice links, DPA route, consent choices, legal version controls, and acceptance tracking are present. External launch gate: lawyer-reviewed Terms, Privacy Policy, DPA, cookie notice, and customer data-processing language.
*   **Production CDN & Security (WAF):** App-level security controls and configurable abuse throttles are implemented. External launch gate: HTTPS deployment behind Cloudflare, AWS CloudFront, or equivalent WAF/CDN with edge rate-limiting.
*   **Automated Email Notifications:** Foundation is implemented with a workspace outbox, branded transactional templates, Resend/SendGrid/SMTP dispatch paths, and a standalone dispatch worker. External launch gate: provider secrets, verified sender domain, deployed worker scheduling, and deliverability testing.
*   **Production Persistence:** Foundation is implemented with a local JSON fallback for development, manual operational backup/restore snapshots, a scheduled backup worker path, and a standalone production smoke-test runner. External launch gate: run the Supabase release schema, configure `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`, and schedule verified provider backups.

## Shared Launch Pending Upgrade Tracker
This table tracks the launch checklist shared in the latest SaaS launch prompt. Items marked `Repo guard complete` have code, docs, or automated checks implemented locally; items marked `External pending` require real production credentials, hosted services, legal review, or infrastructure outside this repository before public launch.

| Priority | Upgrade | Status | Next implementation step |
| --- | --- | --- | --- |
| P0 | Confirm launch branch/files | Repo guard complete | `deploy/release_check.py` enforces root `app.py`, root `requirements.txt`, Docker `streamlit run app.py`, and current README launch instructions. |
| P0 | Run production dependencies install | Repo guard complete | Release check verifies required packages in `requirements.txt`; staging still needs `pip install -r requirements.txt` or Docker build. |
| P0 | CI release gate | Repo guard complete | `.github/workflows/release-gate.yml` installs production dependencies, runs launch-safe regression tests, runs `deploy/release_check.py --strict`, and exercises the launch rehearsal runner without external probes. |
| P0 | Set up Supabase production DB | Repo schema/setup guard complete; external pending | Create production Supabase project, write keys with `python deploy/supabase_schema_check.py --env-file deploy/.env.production --write-supabase-env ...`, apply `supabase_v42_release_schema.sql`, then pass `python deploy/supabase_schema_check.py --env-file deploy/.env.production --probe-rest --strict` and `production_smoke_test.py`. |
| P0 | Add Streamlit production secrets | Repo guard complete; external values pending | `.streamlit/secrets.toml.example` now lists required Streamlit secrets; real keys must be added in the deployment secret store. |
| P0 | Stop relying on local fallback storage | Repo storage guard complete; external pending | Configure Supabase persistence and cloud object storage; run `python deploy/object_storage_check.py --env-file deploy/.env.production --probe-write --strict` and smoke/env checks to block local fallback for launch. |
| P0 | Configure object storage | Repo storage guard/setup helper complete; external pending | Choose Supabase Storage, S3, or GCS. For Supabase Storage, write project keys and bucket with `deploy/supabase_schema_check.py --write-supabase-env`, then pass `deploy/object_storage_check.py` config and probe checks. |
| P0 | Deploy async worker for heavy QA/Pro jobs | Repo async guard complete; external deploy pending | Deploy `async_task_worker.py` and `async_workflow_processor.py`, set worker URL/token, then pass `python deploy/async_worker_check.py --env-file deploy/.env.production --run-smoke --probe-health --strict`. |
| P0 | Managed MT posture | Repo guard complete | Keep `COGNISWEEP_MT_PROVIDER=disabled` for launch; add Amazon Translate later behind `translator_router.translate_batch(...)` with language-pair tests. |
| P0 | Test MT route health | Not applicable for launch | Bundled MT workers have been removed; run `python deploy/mt_endpoint_check.py --strict` to verify retired engine artifacts stay absent. |
| P0 | Configure production AI fallback | Repo AI guard complete; external values pending | Set `OPENAI_API_KEY` or a live managed OpenAI-compatible/vLLM endpoint, then pass `python deploy/ai_fallback_check.py --env-file deploy/.env.production --probe-models --strict` and production smoke checks. |
| P0 | Set production session/auth secrets | Repo auth guard complete; external values pending | Set production session secret, public URL, owner/workspace PBKDF2 credential hashes, then pass `python deploy/auth_session_check.py --env-file deploy/.env.production --probe-public-url --strict` plus launch env and smoke checks. |
| P0 | Prevent accidental public signup before launch | Repo guard complete | Production signup is locked while launch preflight blockers remain when `ERRORSWEEP_ENFORCE_PUBLIC_LAUNCH_PREFLIGHT=true`; Platform Settings shows lock status and a downloadable preflight report. |
| P0 | Schedule verified operational backups | Repo backup guard complete; external schedule pending | Configure backup provider/schedule, run `python deploy/backup_check.py --env-file deploy/.env.production --run-smoke --strict`, then create and verify a production backup/restore evidence snapshot. |
| P0 | Live email delivery | Repo email guard complete; external deliverability pending | Configure Resend, SendGrid, or SMTP credentials, verify sender domain, pass `python deploy/email_check.py --env-file deploy/.env.production --run-smoke --strict`, deploy the dispatch worker, and run deliverability test. |
| P0 | Billing checkout and recurring payments | Repo billing guard/setup helper complete; external pending | Write live Stripe/Razorpay keys, plan IDs, mandate links, and webhook secret with `python deploy/launch_env_check.py --write-billing-env ...`, then pass `python deploy/billing_check.py --env-file deploy/.env.production --run-smoke --strict` and provider checkout/reconciliation tests. |
| P0 | Deploy webhook/API receiver | Repo billing guard complete; external deploy pending | `billing_webhook_receiver.py` is implemented and compose-wired; deploy behind HTTPS, set `ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL`, then pass `python deploy/billing_check.py --env-file deploy/.env.production --probe-health --strict`. |
| P0 | Manual plan upgrade fallback | Repo implementation complete | Billing page includes owner action to activate a selected subscription locally while provider automation is being verified. |
| P0 | Legal review | Repo legal guard complete; external legal approval pending | Replace draft legal docs with lawyer-reviewed Terms, Privacy, DPA, Cookie Notice, and customer processing language, then pass `python deploy/legal_check.py --env-file deploy/.env.production --probe-public --strict`. |
| P0 | Production CDN/WAF/rate limiting | External pending | Put public routes behind Cloudflare, CloudFront, or equivalent HTTPS WAF/CDN and set `ERRORSWEEP_WAF_PROVIDER`. |
| P1 | Enterprise SSO decision | Optional external pending | SSO foundation and signed handoff bridge are implemented; choose whether to enable and configure provider metadata. |
| P1 | Amazon Translate adapter | Future work | Implement a managed AWS MT adapter, IAM permissions, terminology support, cost controls, and launch checks before enabling `COGNISWEEP_MT_PROVIDER=amazon_translate`. |
| P1 | Verify launch-readiness table in app UI | Repo implementation complete | Platform Settings includes Public Launch Readiness and production preflight sections. |
| P1 | End-to-end launch rehearsal | Repo rehearsal runner complete; external run pending | Run `python deploy/launch_rehearsal.py --env-file deploy/.env.production --include-os-env --probe-public --probe-workers --strict` after production services and secrets are configured. |
| P2 | Keep compatibility shims or clean later | Verified; not launch blocking | v13/v14 QA shims re-export v15 and are covered by `test_qa_engine_shims.py`. |

---

## Implemented Global SaaS UI/UX Redesign (All Pages)
To elevate the entire CogniSweep platform to a world-class, premium SaaS standard, the following visual and UX enhancements were implemented across application workflows:

### Global Layout & Navigation
*   **Completed:** Horizontal glassmorphic top navigation with workspace/owner sections, route tabs, job/notification indicators, and an account dropdown.
*   **Completed:** Omnibar-style global search support that deep-links to pages and finds projects, jobs, and TM entries where the command surface is enabled.

### Projects & Jobs Workspaces
*   **Completed:** Kanban board view for Job pipelines (Draft -> Translating -> Human Review -> QA -> Delivered). Drag-and-drop is represented visually; status changes still use Streamlit controls.
*   **Completed:** Job context flyout-style panel with metadata and notes, plus an optional raw table for auditability.
*   **Completed:** Projects and Jobs workflow redesigned into a project-owned model: Projects creates and opens project workspaces, job creation happens inside a selected project, and Jobs now uses a narrow framed left project selector with a wide right-side selected-project jobs list.

### CogniSweep QA & Pro (Workflow Setup)
*   **Completed:** Branded dropzone panels above QA and Pro upload controls with file-type guidance and glowing dashed styling.
*   **Completed:** Wizard/stepper visual guidance for QA and Pro setup flows.

### Memory, Rules & Scorecards
*   **Completed:** Visual rule builder with tag clouds for glossary/DNT, ZIP analyzer imports, and bulk import for glossary pairs and DNT terms.
*   **Completed:** Interactive LQA dashboard filters for severity/category alongside radar, heatmap, and drill-down diff review.

### Team, Roles, Billing & Admin
*   **Completed:** Team avatar grid with monogram avatars and role badges, while retaining the detailed permissions table.
*   **Completed:** Owner Console usage visualization with animated area chart for AI/MT usage velocity.
*   **Completed:** System topology map in Owner Console and Platform Settings showing Streamlit, Supabase persistence, and production service health with status dots.

---

## Implemented Dashboard Redesign (Post-Login Visual Experience)
To elevate the post-login Home page to a world-class SaaS standard, the following visual and UX implementations are required:

*   **Completed:** Personalized Hero Banner with contextual greeting, animated mesh-gradient background, current review/priority/rules summary, and workspace route status.
*   **Completed:** Advanced Glassmorphic Bento Grid with translucent panels, stronger borders, high-depth shadows, and polished hover states.
*   **Completed:** Smart Action Center ("Needs Attention") replacing the plain recent-jobs-first view with a prioritized queue and red/amber pulsing severity indicators.
*   **Completed:** Rich, Animated Data Visualizations with gradient-filled animated area charts and an animated radial TQI progress ring.
*   **Completed:** Floating Quick Actions (FAB) for New Project, Run Pro Translation, Upload Rules, and Run QA with hover lift and shadow expansion.
*   **Completed:** Empty State Illustrations for new/quiet workspaces using a muted 3D-style icon block and onboarding guidance.

---

The CogniSweep platform is built on top of Streamlit, but it heavily overrides the default Streamlit UI using custom CSS injection, HTML rendering, and full-screen external routing to create a professional, SaaS-like experience. Furthermore, the graphical interface incorporates compliance, accessibility, and legal safeguards (such as data privacy indicators and NDA warnings) directly into the user experience.

## Planned Upgrades & Security Fixes
Before transitioning to a full production release, the following critical upgrades and architectural fixes were tracked and implemented where practical in the Streamlit codebase:
### Implementation Progress
*   **Verified:** Code audit confirms the security/workflow fixes are implemented in Python, not only documented. The app now reports `v46 Security + QA Workflow Hardening`; stale v44 comments were removed from the main app/router to avoid false audit signals.
*   **Completed:** Password hashes now use PBKDF2 verification, legacy plain-text passwords are blocked in production, session tokens require a custom production secret, and API-key comparisons use `hmac.compare_digest`.
*   **Completed:** Production auth hardening now scopes sessions to workspace IDs, blocks inactive persisted users in production, prevents duplicate signups, supports temporary-password workspace invites, and enforces tenant checks on external editor job loading.
*   **Completed:** LanguageTool defaults to local-only mode unless explicitly enabled for public routing.
*   **Completed:** QA correction patterns are compiled once when client/built-in correction entries are parsed instead of compiling inside every match attempt.
*   **Completed:** Local editor-job persistence uses temp-file writes with `os.replace`, and usage-event JSONL storage rotates by size/retained line count.
*   **Completed:** Session history collections now have explicit max sizes, and uploaded rule ZIPs surface visible warnings for oversized or highly expanded packs instead of silently truncating rules.
*   **Completed:** Silent translation-adapter failures now emit Python logging warnings.
*   **Completed:** Translation routing remains limited to BYO/platform AI routes and manual Human Review for launch; unsupported third-party fallback engines were intentionally removed.
*   **Completed:** Self-hosted MT workers use reduced model caches and clear CUDA cache after generation batches when running on GPU.
*   **Verified:** The versioned `qa_engine_global_v13.py` and `qa_engine_global_v14.py` shims remain for backward compatibility, re-export the canonical `qa_engine_global_v15.py` implementation, and are now covered by `test_qa_engine_shims.py`.

### UI & Workflow Progress
*   **Completed:** Login flows now require explicit Terms of Service, Privacy Policy, and NDA/confidentiality acknowledgement before owner, workspace, or demo access.
*   **Completed:** CogniSweep Pro shows a persistent routing privacy indicator so users can distinguish manual/BYO AI routes.
*   **Completed:** Account AI access supports any user-supplied OpenAI-compatible API key, model, and base URL, with presets for OpenAI, OpenRouter, Groq, Together, Fireworks, Gemini OpenAI-compatible, local vLLM, and LM Studio.
*   **Completed:** Uploaded Pro rows and CAT review rows now surface sensitive-data indicators for emails, phone-like numbers, and credential-like text before reviewers approve or route content externally.
*   **Completed:** Subtitle/transcription setup now requires explicit media-rights/client-authorization acknowledgement before creating a media workspace.
*   **Completed:** Scorecard exports now support anonymized translator/reviewer identifiers by default for safer external sharing.
*   **Completed:** QA and Pro workflows now call the canonical global QA rule engine, including client rule ZIP chunks, and expose detailed rule findings for download/review.
*   **Completed:** QA, Pro, and Human Review exports now use a delivery quality gate for placeholders, emojis/icons, DNT, numbers, tags, source/target mismatch, and Zero Width Non-Joiner integrity before delivery.
*   **Completed:** Safe Autofix Assistant applies only rule-engine findings explicitly marked autofixable, with audit downloads and Human Review approval required before delivery.
*   **Completed:** CAT review rows now show rule-engine QA details in the assist panel and mark rows with QA findings in the grid.
*   **Completed:** Subtitle/transcription timing grids now validate invalid durations and overlapping segments before saving.
*   **Completed:** External editor persistence load/save paths now log failures instead of silently swallowing them.
*   **Completed:** File storage foundation added with workspace-scoped file manifests for generated downloads, including purpose, MIME type, size, SHA-256 checksum, storage key, expiry metadata, and Platform Settings visibility.
*   **Completed:** Cloud object storage adapter added for local fallback, Supabase Storage, S3, and GCS. Manual job attachments and media previews now store through the adapter, persist provider/bucket/key/public URL metadata, and surface object storage health in Platform Settings.
*   **Completed:** Automated email notification foundation added with a workspace-scoped outbox for signup, workspace invite, QA completion, and Pro completion events. Records persist locally/Supabase with recipient, subject, event type, provider status, body, metadata, and Platform Settings visibility.
*   **Completed:** Async task queue foundation added with workspace-scoped task lifecycle records for QA and Pro workflows, including task type, label, status, progress, unit counts, result reference, error field, timestamps, Supabase schema, Jobs-page visibility, and Platform Settings diagnostics.
*   **Completed:** Async task queue visibility upgraded with QA/Pro progress updates, persistent lifecycle upserts, Jobs-page task cards, retry-request controls for failed tasks, and Platform Settings queue health metrics.
*   **Completed:** External async worker bridge added for QA and Pro. When ERRORSWEEP_ASYNC_WORKER_URL or REDIS_URL/CELERY_BROKER_URL is configured, uploaded input and rules files are stored through the object-storage adapter and queued to the worker; local development keeps the inline execution path.
*   **Completed:** Standalone async task worker receiver added with `/health`, `/tasks`, and `/tasks/{id}/status` endpoints, bearer-token protection, local JSON spool, task lifecycle persistence, smoke-test mode, production env template fields, Platform Settings visibility, and production smoke-test endpoint probes.
*   **Completed:** Worker-side QA/Pro processor added with queued file-manifest loading, source/target detection, rules ZIP ingestion, deterministic QA checks for placeholders, emojis/icons, numbers, DNT, terminology, and Zero Width Non-Joiner, professional QA workbook generation, Pro human-review workbook generation, editor-job persistence, output file manifests, usage logging, CLI loop/once/smoke modes, and receiver process-on-accept support.
*   **Completed:** Async result delivery added to Jobs: completed task cards now surface QA/Pro summaries, direct result downloads or hosted object-storage links, and Pro Human Review editor links; manual job attachment manifests also expose direct download actions from the job context panel.
*   **Completed:** Billing & subscription gateway foundation added with a plan catalog, workspace subscription records, checkout-intent records, usage allowance summaries, payment history, billing notification events, Supabase schema, Billing-page upgrade flow, and Platform Settings diagnostics. Live Stripe/Razorpay checkout and webhooks remain external launch steps.
*   **Completed:** Billing plan selection upgraded from plain cards to a graphic pricing panel with plan visuals, current-plan badge, usage limits, and hosted payment-link support through pasted URLs or `ERRORSWEEP_PAYMENT_LINK_*` secrets.
*   **Completed:** Billing catalog localized to Indian rupee pricing for subscription plans, checkout intents, manual payment records, and payment notification copy.
*   **Completed:** Trial subscription flow now keeps the free trial at 14 days, requires selecting the post-trial paid plan, and requires a card/UPI monthly mandate link with explicit cancel-anytime-before-trial-end acknowledgement.
*   **Completed:** All paid subscription checkouts now use card/UPI monthly mandate links for recurring monthly deduction instead of optional one-time payment links.
*   **Completed:** Billing cancellation foundation added for active subscriptions and pending trial/payment mandates, including persisted cancellation fields, audit trail, and cancellation notification events.
*   **Completed:** Billing webhook reconciliation foundation added with Stripe/Razorpay/manual event normalization, optional signature verification, persisted billing-event records, owner-side event import, mandate checkout status updates, subscription activation, and payment recording.
*   **Completed:** Billing provider checkout bridge added for Stripe/Razorpay subscriptions: CogniSweep now builds provider-specific checkout/subscription payloads from plan selection, stores downloadable JSON/curl diagnostics with checkout intents, supports hosted mandate links as fallback, and can optionally create live provider checkout URLs when `ERRORSWEEP_BILLING_CREATE_PROVIDER_CHECKOUT=true` plus plan IDs/price IDs are configured.
*   **Completed:** Standalone billing webhook receiver service added with `/webhooks/billing/stripe` and `/webhooks/billing/razorpay` routes, provider signature checks, durable billing-event persistence, subscription/payment lifecycle updates, health check support, production env template fields, and launch preflight gating for `ERRORSWEEP_BILLING_WEBHOOK_RECEIVER_URL`.
*   **Completed:** Billing reconciliation diagnostics added in Platform Settings with checkout/webhook/subscription/payment/invoice mismatch detection, high/medium/low severity findings, CSV export, and launch preflight blocking for high-risk billing inconsistencies.
*   **Completed:** Plan usage enforcement added for QA and Pro workflows: uploads are estimated before execution or external queue handoff, over-limit jobs are blocked with upgrade guidance, near-limit jobs warn the user, and completed QA/Pro runs are logged as billable segment/character usage.
*   **Completed:** Seat allowance enforcement added for Team & Roles and Billing: active/invited users are counted against the workspace plan, duplicate users are blocked, over-limit invites require upgrade or suspension, and seat usage is shown beside segment/character allowances.
*   **Completed:** Authentication & onboarding foundation includes secure password hashes, compliance-gated signup/login, persisted users, email verification links, password-reset links, onboarding notifications, and auth-token schema. Enterprise SSO remains a provider-specific launch step.
*   **Completed:** Public verification and password-reset routes now consume hashed one-time auth tokens, mark email verification status, update stored password hashes, and queue transactional outbox messages with local fallback links.
*   **Completed:** Public auth upgraded to one unified email/password login, replacing owner/workspace/demo login tabs while preserving role-based access after authentication.
*   **Completed:** Signup now collects only basic account details, then prompts users with an optional profile completion dialog for professional/freelancer details. Profile completion status and searchable talent metadata are persisted for the owner/management Talent Database page and future job matching.
*   **Completed:** Enterprise SSO readiness foundation added with owner-managed workspace SSO connection records, OIDC/SAML metadata tracking, verified-domain/JIT/role-mapping notes, Platform Settings diagnostics, login-surface provider awareness, production `.env` template fields, and launch preflight gating.
*   **Completed:** Enterprise SSO signed handoff bridge added with a public `?public=sso_handoff` route, HMAC-verified short-lived payloads, replay tracking, domain/workspace matching against enabled SSO connections, optional JIT user provisioning, login-surface provider links, launch configuration checks, and preflight gating for `ERRORSWEEP_SSO_HANDOFF_SECRET`.
*   **Completed:** Dashboard now uses a bento-style operations grid with inline sparklines and an activity pulse drawer.
*   **Completed:** CogniSweep Pro page-load performance improved by making MT diagnostics on-demand and delaying Human Review session restoration until the editor is opened.
*   **Completed:** The unauthenticated entry point now includes a product landing page adapted from the Tailwind landing reference: first-viewport CogniSweep hero, browser-frame workflow preview, social proof, stats, persona cards, feature sections, pricing/readiness bands, final CTA, footer, login forms, demo access, and enterprise SSO placeholders.
*   **Completed:** Landing page CTAs now clearly present a free trial path with "Try for Free" and a paid growth path with "Subscribe" for teams needing more seats, usage, or guided support.
*   **Completed:** The navigation now uses one shared horizontal top bar for all accounts, with permission-based route tabs, clickable NOTES and UI-language panels, and Team/Billing/Admin links shown only when allowed.
*   **Completed:** Team, Billing, Admin, Notes, and language visibility now resolve through an account-type + role + permission-flag matrix. Company management roles receive Team/Billing/Admin by default, lower company roles require explicit grants, and individual/freelancer accounts get personal Billing/Premium access without company Team/Admin sections.
*   **Completed:** Signup now asks for Enterprise / Company vs Individual Contractor. Enterprise signups become workspace owners, while Individual Contractors become solo individual owners with Team, Billing, and Admin scoped to their personal workspace.
*   **Completed:** NOTES now opens a professional notification drawer with deduped notes, sanitized email-verification/reset messages, unread/action-required badge counts, and actions for Verify email, Complete profile, Mark as read, and Dismiss.
*   **Completed:** Long settings-style pages now use sectioned layouts with a left section rail and right-side active section content for Account, Admin, Billing, Team & Roles, and Memory & Rules, while Platform Settings keeps its existing sectioned rail.
*   **Completed:** Profile completion now keeps the post-signup popup as a prompt only; Complete Profile routes users to Account > Professional Profile in inline edit mode, with a redesigned professional Account settings sidebar.
*   **Completed:** Platform Owner navigation now uses a two-row topbar again: primary workspace/product navigation remains in row one, while owner-only tools render in a separate owner tools row without a horizontal scrolling strip.
*   **Completed:** CAT assist panels now highlight placeholders/DNT terms and show inline reviewer diffs before saving changed target text.
*   **Completed:** Subtitling/transcription editors now include media preview, waveform-style visual context, and segment timeline blocks.
*   **Completed:** Scorecards now include radar-style LQA category visualization, error heatmap cells, and drill-down inline diff review for changed segments.
*   **Completed:** Scorecard workbooks now include a separate Reviewer Version QA sheet that checks reviewer/final-file mistakes independently; clean reviewer files are marked as no errors with 100% reviewer quality.
*   **Completed:** Local `linguisticrules.md` is now loaded as a master linguistic profile source in Memory & Rules, included in matching-language AI prompts, and backed by deterministic QA checks for Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam, Marathi, Gujarati, Punjabi, Urdu, Arabic, Persian, Hebrew/RTL context, English locale spelling, French spacing/formality, German formality/length risk, Spanish inverted punctuation, Italian/Portuguese/Turkish/Russian/Ukrainian/Afrikaans formality, Greek question marks/formality, Dutch/Nordic length risk, Polish gendered-formality review, Swahili time-expression review, Hausa Ajami-script review, Sinhala/Zulu profile guidance, Amharic punctuation/formality, Yoruba honorific address, Chinese/Japanese full-width punctuation, Korean direct-pronoun review, Thai gendered particles, Indonesian/Malay formality and locale formatting, Tagalog over-localization hints, Burmese/Khmer native punctuation, Lao Thai-script contamination, Mongolian formality, and Ukrainian apostrophe handling.
*   **Completed:** Project source/target selectors now use a shared 48-language catalog aligned with implemented `linguisticrules.md` profiles instead of the earlier short demo list.
*   **Completed:** Pro translation routing now explicitly uses BYO AI when an API key is present and opens Human Review with a clear notice when no draft translation route is active.
*   **Completed:** CogniSweep Pro and Human Review now provide a same-format reviewed download matching common business/localization upload extensions (`.xlsx`, `.xlsm`, `.csv`, `.tsv`, `.docx`, `.txt`, `.html`, `.json`, `.xliff`, `.xlf`, `.po`, `.pot`, `.xml`, `.properties`, `.srt`, or `.vtt`) alongside the standard Excel/CSV/text exports.
*   **Completed:** Pro translation now splits large source containers into sentence-level Human Review segments while storing a reconstruction map on each sentence row, so same-format export joins reviewed sentences back into the original paragraph, table/cell, slide text box, JSON value, HTML/XML text node, or text line instead of flattening the file into sentence rows.
*   **Completed:** QA and Pro uploaders now prioritize high-use company file formats only; QA still exports the professional Excel QA workbook, while Pro preserves the uploaded file type for reviewed delivery when that format is supported.
*   **Completed:** Source/target extraction now uses the same structured header detector for CSV/TSV and blocks metadata columns such as `target language` from being treated as target text. QA stops with a clear message when bilingual content cannot be detected; Pro continues with source-only content and routes uncertain rows to Human Review.
*   **Completed:** Public SaaS consent foundation added with an explicit privacy/cookie banner, essential-only vs all-consent choices, session/audit recording for signed-in users, and a public Cookie Notice linked beside Terms, Privacy, and Security.
*   **Completed:** Project-to-job linking added across manual Jobs, QA, Pro, and subtitle/transcription workflows, with project IDs/job counts and direct Open Editor links for Pro CAT and media editor tasks from Jobs, Owner Console usage, and Recent Editor Jobs tables.
*   **Completed:** Manual job creation now disables Enter-to-submit, validates job type/target language/assignee before creation, and supports optional multi-file assignment uploads for any file type including ZIP packages, with attachment manifests linked to the job record.
*   **Completed:** Replaced the normal left navigation rail with a horizontal translator-portal-inspired top navigation bar: brand block, workspace route tabs, task/notification indicators, language marker, user avatar, logout affordance, and owner-only route strip.
*   **Completed:** Top-nav profile area now opens an account dropdown with Profile, Settings, Billing, Jobs, and explicit Logout actions instead of logging out when the avatar/caret is clicked.
*   **Completed:** Restored the Jobs navigation wording and manual job assignment upload controls after the rollback, including project context, multi-file/ZIP uploads, attachment manifests, validation, and disabled Enter-to-submit behavior.
*   **Completed:** Jobs attachment persistence now includes Supabase schema and persistence allow-list fields for project context and attachment metadata.
*   **Completed:** Restored the horizontal top navigation after a rollback to the legacy left rail, and kept the recent security/media cleanup fixes active.
*   **Completed:** Email notification outbox upgraded with provider-ready dispatch for Resend, SendGrid, and SMTP, automatic notifications for signup, team invites, QA completion, Pro completion, and payment records, plus Account and Platform Settings visibility.
*   **Completed:** Transactional email templates added with branded HTML plus plain-text fallback for verification, password reset, signup, job assignment, QA/Pro completion, billing, support, privacy, and status events; dispatch now sends provider-ready HTML through Resend, SendGrid, and SMTP, with Platform Settings template preview and launch preflight checks.
*   **Completed:** Email deliverability test workflow added in Platform Settings, with owner-triggered test sends, persisted latest-test status, provider/sender/template evidence, error capture, and launch preflight gating for recent successful delivery before production launch.
*   **Completed:** Standalone email dispatch worker added for production outbox delivery, with Resend/SendGrid/SMTP support, dry-run smoke testing, persisted delivery/error status, `.env` template fields, and launch preflight gating for `ERRORSWEEP_EMAIL_DISPATCH_WORKER_ENABLED`.
*   **Completed:** Platform Settings was reorganized into a page-local left category panel with framed section cards and active-state highlighting, so owners can open one operational section at a time instead of scrolling through all launch, billing, SSO, storage, privacy, support, queue, email, and diagnostics controls in one long page.
*   **Completed:** Platform Settings now includes a Public Launch Readiness table showing completed foundations, external launch gates, and exact next actions for billing, async workers, object storage, auth/SSO, legal, CDN/WAF, email, and persistence.
*   **Completed:** Platform Settings now includes a production launch configuration pack with status-only secret checks, provider-aware missing configuration guidance, and downloadable `.env` templates for production setup without exposing secret values.
*   **Completed:** Platform Settings now includes a manual launch preflight self-test that runs read-only checks for production mode, session secret, public URL, Supabase, object storage, async worker, billing/webhooks, email, legal approval, CDN/WAF, and SSO, with a downloadable Markdown report.
*   **Completed:** Platform Settings feature flags are now real owner controls with session persistence, environment-variable overrides, audit logging, and runtime gating for public registration, demo access, billing checkout collection, Pro Human Review, scorecards, subtitle/transcription workflows, and main translation routing.
*   **Completed:** Platform feature flags now persist through the SaaS persistence layer with local JSON fallback and Supabase schema support, so launch controls survive refreshes, restarts, and multi-instance deployments while still respecting environment-variable overrides.
*   **Completed:** Privacy/compliance export foundation added for workspace admins and platform owners, with redacted JSON exports for workspace records, audit logs, usage events, billing/file manifests, and explicit exclusion of authentication tokens and sensitive account/payment fields.
*   **Completed:** Privacy request tracker added for workspace admins and platform owners, including export/correction/deletion/restriction/consent-withdrawal cases, due dates, status updates, owner notes, CSV tracker downloads, audit events, notification outbox records, and Supabase schema support.
*   **Completed:** Data retention and cleanup foundation added in Platform Settings, with persisted retention policy controls, cleanup candidate counts, confirmed purge actions for expired auth tokens/file manifests, old sent notifications, old completed tasks, closed privacy requests, local media previews, and protected retention of audit/billing records.
*   **Completed:** In-app support ticket foundation added with Account-page ticket creation, Admin/Platform support queues, priority/status handling, owner replies, CSV downloads, audit events, email notification outbox records, privacy export coverage, retention cleanup coverage, and Supabase schema support.
*   **Completed:** Service status and maintenance notice foundation added with Platform Settings incident publishing, workspace/all-workspace scoping, severity/status tracking, signed-in app banners, CSV exports, audit/notification events, privacy export coverage, and Supabase schema support.
*   **Completed:** Platform Audit Logs upgraded with filtered tamper-evident audit snapshots, SHA-256 record hashes, chained final hash verification, CSV/JSON exports, and owner-only access enforcement for compliance review.
*   **Completed:** Billing invoice/receipt foundation added with persisted invoice records, GST-ready draft tax fields, configurable seller GST/profile metadata, invoice workbook downloads, invoice CSV exports, notification/audit events, privacy export coverage, and Supabase schema support.
*   **Completed:** Legal document versioning and acceptance tracking added for Terms, Privacy, Cookie Notice, NDA/confidentiality, and DPA versions, with persisted consent records, login/signup acceptance capture, Platform Settings visibility, stale-acceptance detection, CSV export, privacy export coverage, and Supabase schema support.
*   **Completed:** App-level abuse protection foundation added with configurable throttles for owner/workspace login, demo access, signup, password reset, checkout intents, support tickets, and privacy requests, plus Platform Settings visibility, session block telemetry, and audit events for blocked attempts.
*   **Completed:** Operational backup and restore foundation added in Platform Settings with owner-generated JSON snapshots, per-collection counts and SHA-256 hashes, auth-token exclusion, sensitive-field redaction, selected collection restore/import, restore-source metadata, launch preflight backup checks, and audit events for backup preparation/restoration.
*   **Completed:** Scheduled operational backup worker added for production persistence, with redacted all-workspace SaaS snapshots, local retention cleanup, optional object-storage upload, file manifest/audit persistence, dry-run smoke testing, `.env` template fields, and launch preflight gating for `ERRORSWEEP_BACKUP_WORKER_ENABLED`.
*   **Completed:** Standalone production smoke-test runner added for CI/CD and staging release checks, covering production mode, session secret, public URL, Supabase tables, object storage, async worker, billing/webhooks, email/dispatch worker, backup worker, legal review, CDN/WAF, and optional endpoint probes with JSON or Markdown output.
*   **Completed:** Launch rehearsal runner added with one-command release, env, runtime smoke, public route, async receiver, and billing webhook checks, producing secret-safe Markdown/JSON go/no-go reports for final staging and production rehearsals.
*   **Completed:** Production SaaS launch runbook added to the deployment pack, with phase-by-phase setup, smoke-test blocker mapping, final go/no-go checks, rollback commands, and release/smoke guards requiring the runbook to ship with the branch.
*   **Completed:** Production launch environment validator added for `deploy/.env.production`, with secret-safe Markdown/JSON output, placeholder detection, provider-specific checks for Supabase, object storage, async workers, billing, email, SSO, legal, WAF, and backups, plus strict-mode release gating.
*   **Completed:** Launch branch/file verification added so release checks enforce root `app.py`, root `requirements.txt`, Docker `streamlit run app.py`, current README instructions, and required production dependency coverage before deployment.
*   **Completed:** GitHub Actions release gate added for launch branches and pull requests, installing production dependencies, compiling launch entrypoints, running launch-safe regression tests, enforcing `deploy/release_check.py --strict`, and exercising the launch rehearsal runner without external probes.
*   **Completed:** Supabase and translation-route launch gates hardened with release checks for the production SQL schema, env/template coverage for Supabase anon/service keys, platform AI fallback variables, and retired local MT artifact checks.
*   **Completed:** Supabase launch schema drift checker added with offline table, column, and RLS comparison against `production_persistence.py`, optional REST probing through `deploy/.env.production`, release-check wiring, and runbook/deployment-pack commands.
*   **Completed:** Object storage launch checker added with offline adapter/template/dependency validation, provider-specific production env checks, optional tiny write/sign/cleanup probe for Supabase Storage/S3/GCS, release-check wiring, and runbook/deployment-pack commands.
*   **Completed:** Async worker launch checker added with offline queue/receiver/processor/supervisor/compose validation, provider env checks, optional local receiver/processor/supervisor smoke checks, optional receiver health probe, release-check wiring, and runbook/deployment-pack commands.
*   **Completed:** Operational backup launch checker added in `deploy/backup_check.py`, with offline worker/redaction/template/compose validation, provider/schedule env checks, optional local dry-run smoke, release-check and CI wiring, and runbook/deployment-pack commands.
*   **Completed:** Billing/webhook launch checker added in `deploy/billing_check.py`, with offline provider normalization/signature/receiver/template/compose validation, provider-specific env checks, optional local receiver health smoke, optional public `/health` probe, release-check and CI wiring, and runbook/deployment-pack commands.
*   **Completed:** Transactional email launch checker added in `deploy/email_check.py`, with offline worker/template/provider/dependency/compose validation, provider-specific Resend/SendGrid/SMTP env checks, optional local dry-run dispatch smoke, release-check and CI wiring, and runbook/deployment-pack commands.
*   **Completed:** Legal/compliance launch checker added in `deploy/legal_check.py`, with offline public legal route, legal versioning, consent capture, privacy workflow, subprocessor register, schema/RLS, legal/WAF env-template validation, optional public Terms/Privacy/Security/Cookie/DPA route probes, release-check and CI wiring, and runbook/deployment-pack commands.
*   **Completed:** Managed MT posture checker added with retired local engine artifact checks, future Amazon Translate placeholders, release-check integration, and runbook/deployment-pack commands.
*   **Completed:** Production AI fallback launch checker added with offline managed AI router/API/template validation, OpenAI-compatible URL safety checks, production env validation for platform OpenAI or managed vLLM routes, optional `/models` and chat probes, release-check wiring, and runbook/deployment-pack commands.
*   **Completed:** Production auth/session launch checker added with offline app/session/auth-token/template validation, secret-safe production env checks for session/public URL plus owner/workspace PBKDF2 bootstrap credentials, an interactive password-hash generator, public URL probing, release/smoke/env-check wiring, and runbook/deployment-pack commands.
*   **Completed:** Streamlit Cloud secrets template added with placeholder-only production keys for AI, Supabase, object storage, async workers, billing, email, legal, WAF, backups, and disabled future managed MT, plus release checks that require the template and block obvious live-secret patterns.
*   **Completed:** Tenant isolation diagnostics added in Platform Settings with read-only checks for missing workspace ownership, duplicate workspaces, duplicate active emails across tenants, non-owner Platform users, orphan project links, job/project workspace mismatches, storage prefix review, CSV export, and launch preflight gating for high-risk findings.
*   **Completed:** Subprocessor and data-routing register added in Platform Settings with runtime detection for Supabase, object storage, async workers, email, billing, BYO AI, and LanguageTool routes, plus approval/DPA/customer-notice status tracking, CSV export, audit events, and launch readiness/preflight blockers for active unapproved external processors.

### Security Checklist Status
*   **Completed:** Security & Authentication - secure password hashes, production session-secret enforcement, and timing-safe comparisons are implemented.
*   **Completed:** Data Privacy & NDA Compliance - public LanguageTool routing is disabled by default and QA calls use local-only mode unless explicitly enabled.
*   **Completed:** Performance Optimization - QA correction patterns are compiled when rules are parsed.
*   **Completed:** Data Integrity & State Storage - local editor-job writes use temp files plus `os.replace`.
*   **Completed:** Resource Management - session arrays are bounded and usage-event JSONL storage rotates.
*   **Completed:** Error Visibility - silent `except Exception: pass` paths in the audited app/engine modules were replaced with logging.
*   **Retired:** Local/self-hosted MT batch processing and GPU model-cache work are no longer part of the launch branch; future managed MT should use Amazon Translate.
*   **Completed:** Data Loss Prevention - rule ZIPs show visible size/expansion warnings instead of silently dropping data.
*   **Verified:** Code Maintainability - `qa_engine_global_v13.py` and `qa_engine_global_v14.py` remain as compatibility shims that re-export the canonical `qa_engine_global_v15.py`, with a direct regression check in `test_qa_engine_shims.py`.

## 1. Global UI & Styling System
**Implementation status:** Completed with custom CSS variables, bento cards, activity drawer, command palette, enhanced hover states, and responsive constraints.

The platform leverages advanced CSS injection to completely transcend standard Streamlit limitations, establishing a premium, Vercel-like aesthetic.
*   **Glassmorphism & Depth:** Heavy use of `backdrop-filter: blur(16px)` on floating panels, modals, and sticky headers, layered over a deep mesh-gradient background (`--es-bg-mesh`) to create a sense of Z-axis depth.
*   **Typography Hierarchy:** Implements variable fonts (e.g., `Inter Variable`) for fluid weight transitions. Monospaced elements (`Space Mono`) are strictly reserved for code, placeholders, and metrics to create sharp technical contrast.
*   **Skeleton States & Fluid Transitions:** Replaces standard Streamlit spinners with animated skeleton loaders (pulsing gray blocks) and injects smooth `cubic-bezier` transitions for all hover states and DOM updates.
*   **Global Command Palette:** A visually simulated `Cmd+K` / `Ctrl+K` floating omnibar for rapid navigation across workspaces, bypassing traditional nested menus.
*   **Compliance & Accessibility:** High-contrast WCAG 2.1 compliance modes, coupled with persistent security indicators for active data routes.

## 2. Landing Page & Login
**Implementation status:** Completed with product landing hero, product-scene visual, workflow cards, pricing/readiness bands, compliance-gated owner/workspace/demo login flows, secure password handling, and enterprise SSO placeholders.

The authentication gateway sets the tone with high-end micro-interactions.
*   **Dynamic Ambient Background:** A slow-moving, animated WebGL/CSS blob gradient (incorporating CogniSweep's cyan and purple brand colors) that reacts subtly to mouse movement.
*   **Floating Authentication Card:** The login form floats centrally with a heavily blurred backdrop, subtle 1px semi-transparent borders, and soft drop shadows (`box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5)`).
*   **Modern Input Micro-interactions:** Input fields feature floating labels that smoothly glide out of the way on focus, with validation rings that transition from neutral to red/green dynamically.
*   **Enterprise SSO Mockup:** Visual placeholders for SAML/SSO integrations (e.g., "Continue with Okta/Microsoft Entra") to immediately signal enterprise readiness to prospective clients.

## 3. Home Screen (Dashboard)
**Implementation status:** Completed with personalized command-center hero, animated bento metrics, radial TQI score, floating quick actions, needs-attention queue, empty-state illustration, system-readiness panel, and activity pulse drawer.

A mission-control hub redesigned around a modern "Bento Box" UI architecture.
*   **Bento Grid Layout:** Distinct, interlocking cards of varying sizes that adaptively flow based on screen width. No wasted whitespace.
*   **Interactive Sparklines:** Metric cards don't just show static numbers; they include minimal, inline SVG sparkline charts (via custom HTML injection) showing 7-day velocity for Jobs, QA runs, and TM additions.
*   **Activity Pulse Drawer:** A collapsible right-side drawer that serves as a real-time event feed, logging actions (e.g., "User X approved 50 segments") with subtle entrance animations.
*   **Custom Data-Tables:** The Recent Jobs grid abandons the default Streamlit dataframe look, instead using custom HTML/CSS grids featuring sticky headers, inline progress bars for job completion, and hover-action context menus (three-dots icon).

## 4. Translation Editor (CAT Tool)
**Implementation status:** Completed with full-window CAT routes, spreadsheet editing, QA markers, PII warnings, placeholder/DNT highlighting, TM/glossary/DNT assist panel, and inline diff preview. True drag-resizable panes are approximated with fixed responsive split panes due to Streamlit runtime constraints.

A professional, full-bleed localization environment rivaling desktop CAT tools (Phrase, memoQ).
*   **Resizable Split-Pane Architecture:** Uses custom CSS/JS to allow the user to drag and resize the main grid vs. the right assist panel dynamically.
*   **Semantic Syntax Highlighting:** Placeholders (`{{user}}`), HTML tags (`<b>`), and Do-Not-Translate terms are color-coded in real-time within the grid, replacing standard black-and-white text boxes.
*   **Inline Diff Visualizer:** When comparing TM matches or reviewer edits, differences are shown inline with GitHub-style red strikethroughs for removals and green highlights for additions.
*   **Floating Action Bar (FAB):** A contextual, floating format menu appears directly above text selection (like Medium or Notion), offering Bold, Italic, and Insert Tag shortcuts exactly where the user is typing.
*   **PII & NDA Threat Highlights:** Highly visible, glowing red hazard borders around segments containing undetected PII (SSNs, credit cards), locking external MT routes until the user explicitly masks the data.

## 5. Subtitling / Transcription Editor
**Implementation status:** Completed with media preview persistence, waveform-style visual context, timeline blocks, timing validation, focused segment editor, and collapsible grid. Direct drag editing of waveform blocks is approximated with numeric fields plus visual timeline because Streamlit does not expose low-level drag handles without a custom component.

An ultra-responsive media manipulation suite focused on precise temporal adjustments.
*   **Interactive Audio Waveform:** Replaces standard number inputs with a custom HTML/JS waveform visualizer timeline. Users can see audio peaks and valleys directly below the video player.
*   **Draggable Timecode Blocks:** Instead of typing `00:01:23`, users can visually drag the left/right edges of segment blocks on the timeline to snap them to audio transients.
*   **Picture-in-Picture (PiP) Mode:** The video player automatically shrinks and floats in the corner of the screen if the user scrolls deeply into the transcription grid, ensuring visual context is never lost.
*   **Media Compliance Gates:** Explicit, click-to-proceed legal overlays acknowledging copyright and data retention policies before audio is buffered for speech-to-text processing.

## 6. Scorecards
**Implementation status:** Completed with Excel generation, anonymized exports, LQA metrics, radar-style category visualization, heatmap cells, and drill-down inline diff review.

A rich, data-driven analytics dashboard for Linguistic Quality Assurance (LQA).
*   **Multi-Axis Radar Charts:** Instead of flat numbers, overall quality is visualized via interactive radar charts (via `st.components`), plotting Accuracy, Fluency, Terminology, and Formatting against expected benchmarks.
*   **LQA Heatmaps:** A visual grid showing error density across the document—dark red patches immediately draw the QA manager's eye to problematic sections of a large file.
*   **Drill-Down Error Modals:** Clicking a penalty score expands a beautifully styled modal window displaying the exact segment, the inline diff of the reviewer's correction, and the precise rule triggered.
*   **Anonymized PDF/Excel Generation:** Automated report generation featuring pristine, client-ready typography, brand watermarks, and enforced GDPR anonymization of the translators involved.

## Custom HTML/CSS Component Classes Used
*   `.es-hero`: Gradient header sections.
*   `.es-chip`: Status badges (`.green`, `.amber`, `.red`).
*   `.es-timeline` & `.es-timebar`: Visual representation for segment duration/overlaps.
*   `.es-resource-code` & `.es-resource-body`: Layout for TM/Glossary hits in the side panel.
*   `.es-nav-link`: Sidebar interactive buttons.
