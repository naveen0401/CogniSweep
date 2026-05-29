# ErrorSweep Graphical Implementation Guide

## Proposed Public SaaS Launch Requirements
Before opening ErrorSweep to public sign-ups and paying customers, the following infrastructural and commercial upgrades are required to transition from a Streamlit MVP to a scalable SaaS:

*   **Billing & Subscription Gateway:** Foundation is implemented with plan catalog, subscriptions, checkout-intent records, usage allowance display, payment records, and Platform Settings diagnostics. Public launch still requires live Stripe/Razorpay checkout, webhooks, taxes/invoices, and reconciliation.
*   **Asynchronous Task Queues:** Foundation is implemented with durable task lifecycle records, progress, retry requests, Jobs/Platform visibility, and an external handoff adapter for HTTP workers or Redis/Celery-style queues. Public launch still requires deploying the worker process and testing end-to-end job completion outside the Streamlit request.
*   **Cloud Object Storage:** Foundation is implemented with workspace-scoped file manifests, size/MIME/SHA metadata, assignment upload tracking, media preview storage, and a provider adapter for local fallback, Supabase Storage, S3, and GCS. Public launch still requires configuring a production bucket and credentials.
*   **Authentication & Onboarding Flows:** Password hashing, compliance-gated signup/login, persisted users, email verification links, password-reset links, and auth-token schema are present. Public launch still requires real OAuth/SAML SSO provider wiring and live email deliverability testing.
*   **Legal & Compliance Finalization:** Draft Terms, Privacy, Security, Cookie Notice links, and consent choices are present. Public launch still requires lawyer-reviewed Terms, Privacy Policy, DPA, cookie notice, and customer data-processing language.
*   **Production CDN & Security (WAF):** App-level security controls are implemented. Public launch still requires HTTPS deployment behind Cloudflare, AWS CloudFront, or equivalent WAF/CDN with rate-limiting.
*   **Automated Email Notifications:** Foundation is implemented with a workspace outbox and Resend, SendGrid, and SMTP dispatch paths. Public launch still requires provider secrets, verified sender domain, templates, and deliverability testing.

---

## Implemented Global SaaS UI/UX Redesign (All Pages)
To elevate the entire ErrorSweep platform to a world-class, premium SaaS standard, the following visual and UX enhancements were implemented across application workflows:

### Global Layout & Navigation
*   **Completed:** Horizontal glassmorphic top navigation with workspace/owner sections, route tabs, job/notification indicators, and an account dropdown.
*   **Completed:** Omnibar-style global search support that deep-links to pages and finds projects, jobs, and TM entries where the command surface is enabled.

### Projects & Jobs Workspaces
*   **Completed:** Kanban board view for Job pipelines (Draft -> Translating -> Human Review -> QA -> Delivered). Drag-and-drop is represented visually; status changes still use Streamlit controls.
*   **Completed:** Job context flyout-style panel with metadata and notes, plus an optional raw table for auditability.

### ErrorSweep QA & Pro (Workflow Setup)
*   **Completed:** Branded dropzone panels above QA and Pro upload controls with file-type guidance and glowing dashed styling.
*   **Completed:** Wizard/stepper visual guidance for QA and Pro setup flows.

### Memory, Rules & Scorecards
*   **Completed:** Visual rule builder with tag clouds for glossary/DNT, ZIP analyzer imports, and bulk import for glossary pairs and DNT terms.
*   **Completed:** Interactive LQA dashboard filters for severity/category alongside radar, heatmap, and drill-down diff review.

### Team, Roles, Billing & Admin
*   **Completed:** Team avatar grid with monogram avatars and role badges, while retaining the detailed permissions table.
*   **Completed:** Owner Console usage visualization with animated area chart for AI/MT usage velocity.
*   **Completed:** System topology map in Owner Console and Platform Settings showing Streamlit, Supabase persistence, and self-hosted MT health with status dots.

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

The ErrorSweep platform is built on top of Streamlit, but it heavily overrides the default Streamlit UI using custom CSS injection, HTML rendering, and full-screen external routing to create a professional, SaaS-like experience. Furthermore, the graphical interface incorporates compliance, accessibility, and legal safeguards (such as data privacy indicators and NDA warnings) directly into the user experience.

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
*   **Completed:** Translation routing remains limited to commercial-safe self-hosted/BYO routes selected for ErrorSweep; AGPL-licensed LibreTranslate integration was intentionally removed.
*   **Completed:** Self-hosted MT workers use reduced model caches and clear CUDA cache after generation batches when running on GPU.
*   **Deferred:** The versioned `qa_engine_global_vX.py` shims remain for backward compatibility, with `qa_engine_global_v15.py` as the canonical implementation.

### UI & Workflow Progress
*   **Completed:** Login flows now require explicit Terms of Service, Privacy Policy, and NDA/confidentiality acknowledgement before owner, workspace, or demo access.
*   **Completed:** ErrorSweep Pro shows a persistent routing privacy indicator so users can distinguish local self-hosted MT from external BYO AI routes.
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
*   **Completed:** Billing & subscription gateway foundation added with a plan catalog, workspace subscription records, checkout-intent records, usage allowance summaries, payment history, billing notification events, Supabase schema, Billing-page upgrade flow, and Platform Settings diagnostics. Live Stripe/Razorpay checkout and webhooks remain external launch steps.
*   **Completed:** Billing plan selection upgraded from plain cards to a graphic pricing panel with plan visuals, current-plan badge, usage limits, and hosted payment-link support through pasted URLs or `ERRORSWEEP_PAYMENT_LINK_*` secrets.
*   **Completed:** Billing catalog localized to Indian rupee pricing for subscription plans, checkout intents, manual payment records, and payment notification copy.
*   **Completed:** Trial subscription flow now keeps the free trial at 14 days, requires selecting the post-trial paid plan, and requires a card/UPI monthly mandate link with explicit cancel-anytime-before-trial-end acknowledgement.
*   **Completed:** All paid subscription checkouts now use card/UPI monthly mandate links for recurring monthly deduction instead of optional one-time payment links.
*   **Completed:** Billing cancellation foundation added for active subscriptions and pending trial/payment mandates, including persisted cancellation fields, audit trail, and cancellation notification events.
*   **Completed:** Billing webhook reconciliation foundation added with Stripe/Razorpay/manual event normalization, optional signature verification, persisted billing-event records, owner-side event import, mandate checkout status updates, subscription activation, and payment recording.
*   **Completed:** Plan usage enforcement added for QA and Pro workflows: uploads are estimated before execution or external queue handoff, over-limit jobs are blocked with upgrade guidance, near-limit jobs warn the user, and completed QA/Pro runs are logged as billable segment/character usage.
*   **Completed:** Seat allowance enforcement added for Team & Roles and Billing: active/invited users are counted against the workspace plan, duplicate users are blocked, over-limit invites require upgrade or suspension, and seat usage is shown beside segment/character allowances.
*   **Completed:** Authentication & onboarding foundation includes secure password hashes, compliance-gated signup/login, persisted users, email verification links, password-reset links, onboarding notifications, and auth-token schema. Enterprise SSO remains a provider-specific launch step.
*   **Completed:** Public verification and password-reset routes now consume hashed one-time auth tokens, mark email verification status, update stored password hashes, and queue transactional outbox messages with local fallback links.
*   **Completed:** Dashboard now uses a bento-style operations grid with inline sparklines and an activity pulse drawer.
*   **Completed:** ErrorSweep Pro page-load performance improved by making MT diagnostics on-demand and delaying Human Review session restoration until the editor is opened.
*   **Completed:** The unauthenticated entry point now includes a product landing page adapted from the Tailwind landing reference: first-viewport ErrorSweep hero, browser-frame workflow preview, social proof, stats, persona cards, feature sections, pricing/readiness bands, final CTA, footer, login forms, demo access, and enterprise SSO placeholders.
*   **Completed:** Landing page CTAs now clearly present a free trial path with "Try for Free" and a paid growth path with "Subscribe" for teams needing more seats, usage, or guided support.
*   **Completed:** The navigation now uses a horizontal translator-portal-inspired top bar with workspace route tabs, job/notification indicators, owner strip, and account dropdown.
*   **Completed:** CAT assist panels now highlight placeholders/DNT terms and show inline reviewer diffs before saving changed target text.
*   **Completed:** Subtitling/transcription editors now include media preview, waveform-style visual context, and segment timeline blocks.
*   **Completed:** Scorecards now include radar-style LQA category visualization, error heatmap cells, and drill-down inline diff review for changed segments.
*   **Completed:** Scorecard workbooks now include a separate Reviewer Version QA sheet that checks reviewer/final-file mistakes independently; clean reviewer files are marked as no errors with 100% reviewer quality.
*   **Completed:** Local `linguisticrules.md` is now loaded as a master linguistic profile source in Memory & Rules, included in matching-language AI prompts, and backed by deterministic QA checks for Hindi, Bengali, Tamil, Telugu, Kannada, Malayalam, Marathi, Gujarati, Punjabi, Urdu, Arabic, Persian, Hebrew/RTL context, English locale spelling, French spacing/formality, German formality/length risk, Spanish inverted punctuation, Italian/Portuguese/Turkish/Russian/Ukrainian/Afrikaans formality, Greek question marks/formality, Dutch/Nordic length risk, Polish gendered-formality review, Swahili time-expression review, Hausa Ajami-script review, Sinhala/Zulu profile guidance, Amharic punctuation/formality, Yoruba honorific address, Chinese/Japanese full-width punctuation, Korean direct-pronoun review, Thai gendered particles, Indonesian/Malay formality and locale formatting, Tagalog over-localization hints, Burmese/Khmer native punctuation, Lao Thai-script contamination, Mongolian formality, and Ukrainian apostrophe handling.
*   **Completed:** Project source/target selectors now use a shared 48-language catalog aligned with implemented `linguisticrules.md` profiles instead of the earlier short demo list.
*   **Completed:** Pro translation routing now explicitly uses BYO AI when an API key is present, falls back to built-in MT when no key is present, and opens Human Review with a clear MT-unavailable notice when the configured engines cannot translate the requested language.
*   **Completed:** ErrorSweep Pro and Human Review now provide a same-format reviewed download matching common business/localization upload extensions (`.xlsx`, `.xlsm`, `.csv`, `.tsv`, `.docx`, `.txt`, `.html`, `.json`, `.xliff`, `.xlf`, `.po`, `.pot`, `.xml`, `.properties`, `.srt`, or `.vtt`) alongside the standard Excel/CSV/text exports.
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
*   **Completed:** Platform Settings now includes a Public Launch Readiness table showing completed foundations, external launch gates, and exact next actions for billing, async workers, object storage, auth/SSO, legal, CDN/WAF, email, and persistence.

### Security Checklist Status
*   **Completed:** Security & Authentication - secure password hashes, production session-secret enforcement, and timing-safe comparisons are implemented.
*   **Completed:** Data Privacy & NDA Compliance - public LanguageTool routing is disabled by default and QA calls use local-only mode unless explicitly enabled.
*   **Completed:** Performance Optimization - QA correction patterns are compiled when rules are parsed.
*   **Completed:** Data Integrity & State Storage - local editor-job writes use temp files plus `os.replace`.
*   **Completed:** Resource Management - session arrays are bounded and usage-event JSONL storage rotates.
*   **Completed:** Error Visibility - silent `except Exception: pass` paths in the audited app/engine modules were replaced with logging.
*   **Completed:** Batch MT Processing - self-hosted MT routes process segment batches and preserve protected placeholders.
*   **Completed:** GPU Memory Stability - self-hosted MT endpoints clear CUDA cache and use reduced/configurable model caches.
*   **Completed:** Data Loss Prevention - rule ZIPs show visible size/expansion warnings instead of silently dropping data.
*   **Deferred:** Code Maintainability - `qa_engine_global_v13.py` and `qa_engine_global_v14.py` remain as compatibility shims that re-export the canonical `qa_engine_global_v15.py`.

## 1. Global UI & Styling System
**Implementation status:** Completed with custom CSS variables, bento cards, activity drawer, command palette, enhanced hover states, and responsive constraints.

The platform leverages advanced CSS injection to completely transcend standard Streamlit limitations, establishing a premium, Vercel-like aesthetic.
*   **Glassmorphism & Depth:** Heavy use of `backdrop-filter: blur(16px)` on floating panels, modals, and sticky headers, layered over a deep mesh-gradient background (`--es-bg-mesh`) to create a sense of Z-axis depth.
*   **Typography Hierarchy:** Implements variable fonts (e.g., `Inter Variable`) for fluid weight transitions. Monospaced elements (`Space Mono`) are strictly reserved for code, placeholders, and metrics to create sharp technical contrast.
*   **Skeleton States & Fluid Transitions:** Replaces standard Streamlit spinners with animated skeleton loaders (pulsing gray blocks) and injects smooth `cubic-bezier` transitions for all hover states and DOM updates.
*   **Global Command Palette:** A visually simulated `Cmd+K` / `Ctrl+K` floating omnibar for rapid navigation across workspaces, bypassing traditional nested menus.
*   **Compliance & Accessibility:** High-contrast WCAG 2.1 compliance modes, coupled with persistent, glowing security indicators (e.g., a pulsing green dot for "Local MT Air-gapped").

## 2. Landing Page & Login
**Implementation status:** Completed with product landing hero, product-scene visual, workflow cards, pricing/readiness bands, compliance-gated owner/workspace/demo login flows, secure password handling, and enterprise SSO placeholders.

The authentication gateway sets the tone with high-end micro-interactions.
*   **Dynamic Ambient Background:** A slow-moving, animated WebGL/CSS blob gradient (incorporating ErrorSweep's cyan and purple brand colors) that reacts subtly to mouse movement.
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
