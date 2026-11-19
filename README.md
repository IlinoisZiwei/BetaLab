# BetaLab

[English](README.md) · [简体中文](README.zh-CN.md)

A mobile-first climbing prototype built with React, TypeScript, Vite, FastAPI and PostgreSQL. This handbook describes the **implementation verified locally as of November 19, 2026**; this does not imply that the deployed site includes every feature. It replaces the separate phase reports and handoff guides; their originals remain in a local-only archive, excluded from Git commits and pushes.

## Contents

1. [Project overview](#overview)
2. [Current implementation status](#status)
3. [Repository structure](#structure)
4. [Local setup and startup](#setup)
5. [Product workflows](#workflows)
6. [Backend and API contracts](#api)
7. [Video and skeleton pipeline](#pipeline)
8. [Data and assets](#data)
9. [Results and known limitations](#results)
10. [Testing and performance](#testing)
11. [Demo and troubleshooting](#demo)
12. [Responsibilities and next steps](#next)
13. [References and version history](#history)

<a id="overview"></a>
## 1. Project overview

BetaLab connects route browsing, climbing videos and body-proportion-based skeleton previews. The intended workflow is to analyze an uploader's movement, adapt it to another user's height and arm span while preserving contact order and timing, then compare a small number of applicable techniques after validation.

The local application includes authenticated accounts, persistent uploads, private media, background tasks and notifications. Algorithm coverage is narrower: Trial2 supports diagnostic source/target previews; other videos support input extraction and calibration review, not complete skeleton adaptation yet.

The [GitHub Pages site](https://ilinoisziwei.github.io/BetaLab/) is a static frontend deployment. It does not host the local API, database, private uploads or worker. A Git push does not transfer local user data or scientific model assets.

<a id="status"></a>
## 2. Current implementation status

| Area | Available locally | Remaining work |
| --- | --- | --- |
| Accounts and videos | Authentication, profile, route-linked upload, playback, visibility and deletion | Deployment hardening, backup/restore and broader device testing |
| Catalog | Movement Fishtown and 73 highlighted route-photo entries, plus r1 | Review uncertain photo annotations; additional catalog data |
| Tasks and notifications | Persistent queue, one worker, retries, notifications, protected artifacts | Broader operational/performance testing |
| Upload analysis | Automatic submission, submission recovery, failure/retry and refresh recovery | More real-video failure cases and clearer corrective guidance |
| Community → My Library | Source-bound generation request, body inputs, task state and diagnostic playback | Generalize generation beyond the calibrated Trial2 source |
| New-video inputs | Extraction, contact versions, local calibration; measured-input panel assembly/camera alignment and unified export | Real handheld calibration data, automatic moving-camera recovery, body depth/source reconstruction and adaptation |
| Trial2 geometry | v5 source and target diagnostic previews | Baselines still fail; source-motion investigation is currently paused |
| Result presentation | Separate examples, diagnostics and gated technique results | Full-model checks and real technique comparison are not implemented in the current flow |
| Social interactions | Prototype UI interactions | Persistent likes, saves, comments/replies and cross-device synchronization remain incomplete |

Task completion means computation and storage finished. It does not mean the climbing movement passed geometric or physical validation.

<a id="structure"></a>
## 3. Repository structure

```text
BetaLab-github/
├── README.md / README.zh-CN.md   English handbook and matching Chinese edition
├── src/                         Main React application and shared API client
│   ├── app/                     Pages, session/navigation hooks and coordination
│   ├── features/                Catalog, comments and video hooks / video reducer
│   ├── components/              Shared controls and media components
│   ├── styles/                  Main UI styles in preserved cascade order
│   ├── compute/                 Task, upload, input review and results UI
│   └── data/                    Route-photo catalog metadata
├── backend/
│   ├── app.py                   Assembly, middleware and health check
│   ├── auth.py / database.py    Session authentication and database connections
│   ├── routes/                  Account, catalog and video endpoints
│   ├── media.py                 Shared byte-range file transport
│   ├── db/                      Versioned migrations and catalog seed
│   └── compute/                 Task service, worker and scientific adapters
├── public/media/                Bundled public demonstration media
├── vite/plugins/                Five preview/build plugins
├── tests/build/                 Plugin contracts and live dev-server regression
├── scripts/                     Asset preparation/import utilities
├── tests/frontend/              Frontend classification tests
├── tests/compute/               Contracts, API, scientific and browser tests
│   └── support/                 Disposable database and browser environment helpers
├── docs/compute/examples/       Machine-readable schemas and example payloads
├── local-server/                Historical unauthenticated Trial2 experiment
├── compute.html                 Separate authenticated compute review page
└── compose.yaml / .env.example  Local database and environment configuration
```

`backend/README.md` is a compatibility symlink to the English handbook, not a separately maintained document. Existing source comments referring to it still resolve.

The normal entry is `/`; `/compute.html` is a developer review tool. `local-server/` and `/api/skeleton-jobs` belong to the old experiment on port 8787; the current main-page compute flow uses `/api/tasks` through port 8788. Keep legacy timings and outputs separate from v5.

Within `backend/compute/`: `api`, `service`, `storage`, `runner`, `worker` and `media` handle execution and access; `real_job` and the fitting/geometry modules handle Trial2; `input_job`, `input_schema`, `input_calibration` and `input_review` handle new-video inputs; `contact_schema` and `contact_review` handle manual contact versions and dense exports; `world_schema`, `world_geometry`, `world_job` and `world_review` handle versioned global geometry; `preflight` and `standby` support demonstrations. `mock` is explicitly synthetic. File locations and algorithm logic were not changed during documentation consolidation.

Generated `dist/`, private `data/`, virtual environments and `backend/compute/runs/` are not source documentation. Historical `before-*.css` backups are preserved outside the repository and excluded from source/commits.

The first deduplication pass shares `src/api.ts` between the main UI and compute review page, including JSON/multipart requests and explicit CSRF. Both use Task/Result/Moment/Note definitions in `src/compute/results.ts`; the review page keeps CSRF in component state. Upload progress still uses its existing XHR path. Shared `backend/media.py` handles byte ranges only: callers keep their authorization, path checks and artifact checksums, plus existing endpoint-specific headers/range policies. Test cases use `tests/compute/support/` helpers instead of invoking another test class's lifecycle methods. Helpers isolate in-memory login throttling per disposable test environment; production throttling is unchanged. No solver, engine version, evidence or legacy algorithm code changed. The second pass completes App/page and business-router separation; the third pass organizes CSS and extracts Vite plugins.

In the second pass, `src/App.tsx` selects pages and renders navigation/global dialogs; `src/app/pages/` holds page presentation, and `useAppController.tsx` coordinates cross-page actions and supplies page-specific data/callbacks. Session/navigation hooks live in `app/hooks/`; catalog loading, example comments and upload/video lists live in `features/`. One video reducer updates owned, public and route-Beta collections on upload, visibility changes and deletion. History display records derive from owned videos; account changes reset state and cancel old list requests. Samples remain separate from actual videos. Backend `auth.py` provides shared authentication; `routes/accounts.py`, `catalog.py` and `videos.py` own business endpoints. Endpoints, authorization, CSRF, upload rules and algorithm logic are preserved.

In the third pass, `src/index.css` contains only font/Tailwind imports and 12 ordered stylesheet imports. `src/styles/01–05` preserve the existing foundation, typography/motion, workspace, theme and community-control layers; `06–12` retain subsequent navigation/media, home, catalog, shared polish, route/upload, inner-page and community/viewport overrides. Numbers encode cascade order: do not alphabetically reorder imports. Apparently repeated declarations with context-dependent effects are retained. `src/compute/*.css` remain loaded by their existing components.

`vite.config.ts` retains build entries, plugin order, aliases, proxies and private-directory denial. Site metadata, error replay, React refresh fallback, Make kit and linked-package sourcemaps each live in `vite/plugins/`; the sourcemap plugin receives the project root explicitly so moving its file does not change path resolution. No dependencies, Figma settings, business code or algorithms changed.

<a id="setup"></a>
## 4. Local setup and startup

Run commands from the repository root. Requirements: Node.js 22.12+, Python for the API, Docker Desktop/Compose or an existing PostgreSQL server, and FFmpeg/ffprobe. Real computation additionally requires the pinned CIS5810 checkout and its verified Python 3.12 environment, models and evidence. A clean-machine scientific installation has not been independently validated.

### Install and configure

```sh
npm ci
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
cp .env.example .env
```

Copy `.env.example` only when creating a new configuration; preserve an existing `.env`. Set the local database password, then configure:

| Variable | Required setting |
| --- | --- |
| `POSTGRES_HOST/PORT/DB/USER/PASSWORD` | Same database for API and worker; Compose defaults to host 127.0.0.1, port 5433 |
| `APP_ORIGINS` | Exact browser origins; add `http://127.0.0.1:5173` for the commands below |
| `UPLOAD_DIR` | Private upload directory; default `./data/uploads` |
| `COMPUTE_MODE` | `real`; use `mock` only for explicitly synthetic development/testing |
| `COMPUTE_STORAGE_DIR` | Private artifact directory; default `./data/compute`, never inside `public/` |
| `BETA_TRANSLATOR_ROOT` | Absolute path to the pinned local Beta_Translator checkout |
| `BETA_TRANSLATOR_PYTHON` | Optional override; defaults to that checkout's `.venv/bin/python` |
| `COMPUTE_TIMEOUT_SECONDS` | Default 1800; per-job timeout, not a latency promise |
| `REGISTRATION_ENABLED` / `COOKIE_SECURE` | Local registration policy; secure cookies for an HTTPS deployment |

`.env.example` does not include port 5173 in its origin list. Use the actual Vite port if it selects another. Keep secrets and private data out of Git.

### Database

```sh
docker compose up -d db
backend/.venv/bin/python -m backend.db.manage migrate
backend/.venv/bin/python -m backend.db.manage seed
```

For an existing host PostgreSQL server, configure `POSTGRES_*` and use `migrate --direct` / `seed --direct` instead. Do not edit applied migration files; add a new numbered migration. Catalog seed and migrations are repeatable.

### Start services in separate terminals

```sh
# API
backend/.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8788
```

```sh
# Preflight followed by the single persistent worker
backend/.venv/bin/python -m backend.compute.preflight run
```

```sh
# Frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`; API reference is `http://127.0.0.1:8788/docs`. Preflight currently checks Trial2 evidence as well as the scientific environment; it is not a complete new-video model installer. API and worker must share database and storage settings. Environment variables already exported in the shell can override `.env`.

Build with `npm run build`; `npm run preview` previews static output and does not replace the API/worker development setup. To stop/start the Compose database without deleting its volume, use `docker compose stop` / `docker compose start`.

For LAN testing, bind Vite to `0.0.0.0`, add the exact LAN origin to `APP_ORIGINS`, and keep the API behind the same-origin proxy. The host must remain running. HTTPS, tunnels, physical-phone acceptance and database/media backup recovery still need coordinated validation.

<a id="workflows"></a>
## 5. Product workflows

- **Upload:** choose a route → Add my video → title and Private/Public → upload. Saving and analysis submission are separate operations: an analysis failure does not delete the video. Refresh can recover the task or offer Start analysis if submission never reached the server. Retry creates a new attempt.
- **Community:** public user videos are browsable by signed-in users. Community Beta filters public videos with `share_as_beta=true`; that opt-in exposes uploader measurements for comparison. Bundled samples remain examples, not uploaded records.
- **Personal skeleton:** open an actual Community video → Generate beta → retrieve its source analysis → enter height and arm span → submit → My Library / My skeletons → notification or saved result. Requests bind to the actual video and analysis version, never a substitute from the same route. Currently only the supported Trial2 analysis can seed this diagnostic flow.
- **New-video review:** after input preparation, open New video inputs → inspect candidates and reference image → review calibration → save. Input completion does not unlock personal generation.
- **Results:** example suggestions are isolated; real diagnostic moments seek within their own task video. Personal outputs stay private and continue to depend on access to the source video.

<a id="api"></a>
## 6. Backend and API contracts

Browser requests use same-origin `/api`, session cookies and `X-CSRF-Token` on authenticated mutations. Mutation origins must match `APP_ORIGINS`, including registration/login. Ownership comes from the session. Sessions use HttpOnly cookies; restore CSRF state through `/api/auth/me` after refresh.

| API group | Routes and purpose |
| --- | --- |
| Account | `POST /auth/register`, `/auth/login`, `/auth/logout`; `GET /auth/me`; `PUT /profile` |
| Catalog/health | `GET /health`, `/gyms`, `/routes`, `/routes/{id}` |
| Uploads | `POST /videos`; `GET /videos`, `/videos/{id}`, `/videos/{id}/content`; `PATCH` / `DELETE /videos/{id}` |
| Upload orchestration | `GET` / `POST /tasks/upload-analysis/{video_id}`; uploader-only |
| Tasks | `POST /tasks/analyze`, `/tasks/generate`; `GET /tasks`, `/tasks/{id}`, `/tasks/{id}/result` |
| Retry | `POST /tasks/{id}/retry`; new attempt, original failure retained |
| Source reference | `GET /tasks/source-analysis/{video_id}`; returns usable source ID/version and quality, not another user's private task |
| Artifacts | `GET /tasks/{id}/artifacts/{name}`; shared source preview via `/tasks/source-analysis/{video_id}/artifacts/{name}` limited to allowed preview types |
| Input review | `GET` / `POST /tasks/{id}/input-review`; owner-only, versioned calibration |
| Contact review | `GET` / `POST /tasks/{id}/contact-review`; optional GET `version`; owner-only |
| Contact computation input | `GET /tasks/{id}/contact-review/export?version=...`; confirmed version required |
| Global geometry | `GET` / `POST /tasks/{id}/world-review`; owner-only, optional GET version |
| Global computation input | `GET /tasks/{id}/world-review/export?version=...`; pinned version, unresolved states retained |
| Notifications | `GET /notifications`; `PATCH /notifications/{id}/read` |

All routes above have the `/api` prefix. Interactive OpenAPI describes exact payloads. Compute [schemas and fixtures](docs/compute/examples/) remain machine-readable examples; authoritative models are `contracts.py` and `input_schema.py`. Exporting examples uses `python -m backend.compute.export_examples` in the API environment.

Upload defaults: MP4/MOV, at most 90 seconds and 200 MiB, verified by ffprobe. Multipart fields include route, visibility, optional Beta-sharing flag, title, description and video. Private videos cannot be shared as Beta. Unsupported browser codecs in an otherwise accepted MOV are not automatically transcoded on upload.

Profile height is 100–230 cm and arm span 80–260 cm. Missing values may stay null; `PUT /profile` is a full update, so omitted/null measurements clear them. Generation requires user-entered or manually corrected target measurements.

Task states are `queued → running → succeeded / failed`. Stages describe actual work, not invented percentages. An algorithm can finish with insufficient evidence. Idempotency keys for analyze/generate/retry prevent duplicate acceptance; reusing a key with different input returns 409. Notifications and terminal results are committed together. A single-worker lock protects execution; interrupted running tasks become retryable failures on recovery.

Errors use `{"error":{"message":"..."}}`; task failures additionally carry structured `Task.error`. Typical statuses: 401 login, 403 Origin/CSRF, 404 missing/inaccessible resource, 409 conflict/stale/not ready, 422 invalid input. Upload and task lists use their documented pagination parameters.

Artifacts remain private and checksum-verified. Source visibility/deletion is checked during task handling and reads; a viewer loses access to derived outputs when source access is withdrawn. Access revocation is not a complete disk-retention/garbage-collection policy. Personal tasks and notifications are owner-only.

<a id="pipeline"></a>
## 7. Video and skeleton pipeline

### Trial2 diagnostic path

The original recording is matched by SHA-256, uses route `r1`, engine `trial2-source-fit-v5`, calibration `trial2-grid143-v2` and reference frame 450. It has 976 frames at 30 fps. A different upload on the same route cannot inherit its evidence.

Confirmed inputs: adjacent hole centers are 14.3 cm apart on both axes; upper wall is 70° and middle/start wall 28° relative to horizontal; upper/lower folds and the ground image line are confirmed. Height is approximately 173 cm; arm span 176 cm is an allowed assumption, not a measured fact. Bottom-wall geometry, camera assumptions and ground contacts are not fully established.

Source fitting and target adaptation preserve declared contact order/timing. Their outputs remain diagnostic because the current baseline fails. No automatic full-physics continuation or real technique comparison runs after preview generation.

### Independent new-video path

`video-inputs-v1` prepares a fresh task directory, samples up to 15 fps at width 720 with an explicit original-frame/timestamp map, extracts RTMW whole-body pose and MediaPipe tracking, builds wall/hold candidates, predicts contacts, and publishes review inputs. It records source/model/code hashes and does not reuse upstream Trial2 output caches.

Artifacts include sampled video, reference image, numbered holds, masks, pose, identity/alignment data, frame map, contact rows/events, summary and provenance. The video is the sampled input recording, **not a generated skeleton**. Detector scores and `accepted_model` contacts are not human confirmation; missing observations and homography/parallax limitations remain relevant.

The current calibration editor is a developer JSON review tool. Select hold IDs; supply each convex wall polygon, four grid corners ordered top-left → top-right → bottom-right → bottom-left in wall-grid coordinates, horizontal/vertical interval counts, angle from horizontal (null if unknown), and measurement notes. Click the reference image for pixel coordinates. Count hole intervals, not holes.

Saved reviews have immutable versions and reject stale updates, unknown holds, wrong reference frames or invalid geometry. Coordinates are plane-local centimeters. Holds outside all panels or in overlapping panels remain unassigned/ambiguous. Confirm identity only after review; calibration JSON keeps `contact_reviewed=false`, with contact confirmation tracked in a separate version. Global wall/camera review now has a separate entry, but real footage lacks measured inputs and source adaptation is not integrated; new videos retain `generation_ready=false`.

### Manual contact review

Open a completed new-video input task in My skeletons → New video inputs → Contact and release review. Load automatic candidates, change limb/hold assignments and contact/release frames, add/remove intervals, mark hold/free/unknown, and record observations. Use the numbered hold image and dedicated video player to inspect contact/release moments. Candidates are not automatically human-confirmed; edits require confirmation again, and drafts can be saved.

Times use sampled analysis frames with half-open intervals `[start_frame, release_frame)`. At 15 fps, [3,9) covers frames 3–8 and 0.2–0.6 seconds; release may equal frame count. Beta Translator's inclusive `end_frame` converts to `release_frame=end_frame+1`, with attribution in code. Gaps and unresolved wall/ground contact remain unknown; mark free only when visibly off the wall. Different limbs may share a hold; intervals for one limb cannot overlap. Holds must come from this task's candidates; adding missed holds is not implemented.

Saving binds the task, source video and five original artifact SHA-256 values into an immutable version in private `COMPUTE_STORAGE_DIR/contact-reviews/{task_id}/`. Predictions, calibration and Trial2 evidence are not overwritten. Stale concurrent updates return409; the UI retains unsaved edits and offers reload. Current/previous versions can be inspected; historical versions remain addressable. Confirmation means the intervals were reviewed, not that unknown gaps are resolved or geometry/mechanics passed.

Future consumers use `GET /api/tasks/{id}/contact-review/export?version={full hash}` or `contact_review.export(task_id, owner_id, version)`. An explicit confirmed version is required; drafts return409. The export contains normalized intervals, per-frame states and hold IDs for all four limbs, original source-frame/time mapping and input hashes. Every read rechecks ownership, source access and content integrity. This input interface is ready for downstream use; the worker does not yet reconstruct new-video source motion or start adaptation from an export.

### Global wall and camera review

Open a completed new-video input task → Global wall and camera alignment. First save wall calibration with confirmed identity and a confirmed contact version, then enter geometry JSON. Blank templates keep unknown values null and cannot be saved as valid calibration. A separate scientific process handles this step; Trial2 diagnostics and technique comparison are not invoked.

- **Panel assembly:** centimeters, right-handed coordinates, Y up. Supply a root origin and orthogonal unit u/v axes matching its local grid; an arbitrary origin does not establish ground height. Each parent/child join supplies corresponding ordered local seam endpoints and a signed fold angle (right-hand rotation along the parent edge). Panels must form a connected tree, edge lengths must agree within 0.1 cm, and resulting inclination must agree with separately supplied wall angles within 2°.
- **Camera:** supply fx/fy/cx/cy, [k1,k2,p1,p2,k3] distortion and provenance for the exact sampled image resolution/crop, not the original phone resolution. Each camera frame needs at least six well-spread noncoplanar fit points across folded panels and two distinct independently observed check points, pairing local wall centimeters with image pixels. PnP solves extrinsics only; it does not guess intrinsics. Fit RMSE must be ≤5 px, check maximum ≤8 px, and all controls must lie in front of the camera. The UI shows reference-frame observation/projection overlays and errors.
- **Handheld video:** the reference camera is not reused by default. Supply controls per aligned frame; missing frames stay unaligned. No camera interpolation or multi-plane homography-as-3D inference occurs. Only explicitly confirmed fixed-camera recordings may reuse the reference camera, gated by valid tracking and maximum image displacement ≤3 px. This is a conservative screen, not independent calibration accuracy.
- **Unified output:** undistorted hold rays intersect assigned world planes to form wall-surface anchors. Two-dimensional body observations produce world-space ray origins/directions and original scores, never invented depth. Unobserved identity, low scores (<0.3), invalid points and uncalibrated frames retain nulls. Contacts retain the pinned manual review's source frame/time mapping and bind to world hold targets; these targets are not actual joint locations or measured hold protrusion. Body depth, full motion and physical feasibility still require reconstruction.

Versions live separately under `world-reviews/{task_id}/{version}.json`, binding wall/contact versions, input artifacts and implementation hashes without overwriting predictions. GET supports historical versions; exports require an explicit full version and recheck access/dependency integrity. Exports include panel frames, camera extrinsics, per-frame camera indices, holds, pose rays, contact targets and missing-camera frames. Calibration does not unlock generation: `generation_ready=false`.

**Real-data status, confirmed by the user:** footage is handheld; no acceptance video has been selected, wall inclinations/seams are unmeasured, and camera intrinsics are unavailable. Only 14.3 cm grid spacing is confirmed. Code and synthetic acceptance are complete; real-video global calibration is not. Next collect a chosen recording, measured seam/grid correspondences and wall angles, camera calibration matching resolution/focal length/crop, and controls at target frames. Grid spacing alone does not validate the camera/wall geometry used by this implementation. Trial2's 28°/70° measurements are not transferred to other videos.

<a id="data"></a>
## 8. Data and assets

Movement Fishtown retains gym ID `gym-a`. Its photo import adds 73 entries from IMG_7518–IMG_7544; with r1 this gives 74 catalog entries. Long Reach (`r2`) is removed from browsing; migration 009 preserves referenced uploads by archiving the route when needed. Different photographs may show the same physical route; the import does not deduplicate physical routes.

- Catalog: `src/data/movementRoutes.json`; import migration 008 and removal migration 009.
- Images: `public/media/movement-facetime/`. The historical directory spelling remains for compatibility; the displayed gym name is Movement Fishtown.
- Original media attribution: [MEDIA-SOURCES.txt](MEDIA-SOURCES.txt).
- Highlighted photos are visual edits, not exact segmentation masks or calibrated algorithm inputs. Unspecified grades are Unrated; white routes in IMG_7536 and small teal holds in IMG_7539 need review.
- `scripts/import-route-photos.py` prepares assets from the separate full-quality delivery folder; it is not a startup step. Gym B has no supplied route footage.

Private uploads use `UPLOAD_DIR`; task work, published artifacts and immutable reviews use `COMPUTE_STORAGE_DIR`. Local test reports and standby packages live under ignored `backend/compute/runs/`. They are machine-local evidence, not files guaranteed to exist in a fresh clone. Database records, upload files and compute storage need separate backup coverage.

<a id="results"></a>
## 9. Results and known limitations

| Result class | Meaning |
| --- | --- |
| Example | Interface illustration or mock content, not an observation of this upload |
| Diagnostic | Real model error or insufficient evidence, with source-bound time links |
| Technique result | Only promoted with non-mock evidence, passed baseline, compared candidates and `full_model` checks; no such comparison currently runs |

Latest v5 geometry evidence:

| Metric | Source, 173/176 cm | Target, 170/175 cm |
| --- | ---: | ---: |
| Maximum known-wall contact gap | 16.74 cm | 16.66 cm |
| Frames above the 5 cm diagnostic threshold | 6 | 4 |
| Rate violations | 0 | 0 |
| Frames with known-wall joint-center penetration above 1 cm | 0 | 0 |
| Overall baseline | failed | failed |

The remaining source segments are left hand H137 at frames 175–178 (5.833–5.933 s), and right foot H149 → H163 at frames 298–299 (9.933–9.967 s). Review release/switch timing and actual foot contact mode before revising evidence. Previously confirmed wall angles/folds do not need repeated confirmation. Ground has 78 unverified candidate samples; H109 right-foot frames 239–253 retain insufficient-evidence labels.

Joint-center checks do not establish whole-body collision avoidance, balance, contact forces or physical feasibility. Global 3D reconstruction for new videos, reliable automatic body measurements, full-model physics and technique optimization remain incomplete. Trial1's 2D technique constraints cannot be directly treated as validated constraints for the Trial2 3D model.

<a id="testing"></a>
## 10. Testing and performance

### Reproducible checks

```sh
npx tsc --noEmit
npm run build
node --experimental-transform-types --test tests/frontend/*.test.ts tests/build/*.test.ts
backend/.venv/bin/pip install -r backend/requirements-test.txt
backend/.venv/bin/python -m unittest discover -s tests/compute -v
```

Database tests require an explicitly configured disposable test database via `POSTGRES_*`; do not point them at application data. Then enable `BETALAB_TEST_DB=1`. Tests create isolated schemas; some worker locks are database-wide, so run worker/browser suites sequentially.

Browser tests additionally need `backend/requirements-browser.txt` and `backend/.venv/bin/python -m playwright install chromium`. Scientific tests use the verified Beta Translator Python environment. Opt-in examples:

Browser tests resolve Node from PATH by default; set `BETALAB_NODE` to an absolute executable path for another installation. Tests do not depend on a personal machine path.

| Test file | Additional opt-in |
| --- | --- |
| `test_community_browser.py` | `BETALAB_COMMUNITY_TEST=1` |
| `test_upload_browser.py` | `BETALAB_UPLOAD_BROWSER_TEST=1` |
| `test_result_browser.py` | `BETALAB_RESULT_BROWSER_TEST=1` |
| `test_input_browser.py` | `BETALAB_INPUT_BROWSER=1` |
| `test_world_review.py` | `BETALAB_WORLD_TEST=1` |
| `test_world_browser.py` | `BETALAB_WORLD_BROWSER=1` |
| `test_world_geometry.py` | Scientific Python (OpenCV/NumPy) |
| `test_review_client_browser.py` | `BETALAB_REVIEW_CLIENT_TEST=1` |
| `test_video_management_browser.py` | `BETALAB_VIDEO_BROWSER_TEST=1` |
| `test_new_inputs.py` | `BETALAB_TEST_INPUTS=1` |
| `test_phase5_rehearsal.py` | `BETALAB_REHEARSAL_TEST=1` |

These suites also require their documented local recordings/reports and source environment; inspect their setup prerequisites before running in a fresh clone. Several browser tests deliberately import verified precomputed artifacts and do not rerun source fitting.

### Latest regression and historical algorithm evidence

Global-alignment acceptance passed 41 ordinary backend tests (74 discovered, 33 environment-gated skips), two separately enabled scientific API tests, four known-truth scientific geometry tests, 15 frontend/build tests and six browser cases (three further browser cases skipped). Type checking and production build passed. Tests cover joined seams, camera/hold truth, world pose rays/contact anchors, handheld missing-frame behavior, fixed-camera motion rejection, invalid calibration, pinned versions, stale conflicts, access/integrity, UI errors, reprojection overlay and refresh. Geometry and GUI success use explicitly synthetic measured inputs; real handheld calibration remains blocked by missing data. Existing compute files other than API route registration are byte-identical; no Trial2 refit or technique comparison ran. Evidence: `backend/compute/runs/world-alignment-acceptance/`.

Manual-contact acceptance passed 41 backend tests (67 discovered, 26 environment-gated skips), 15 frontend/build tests and five enabled browser cases (three additional cases skipped), plus type checking and production build. Six contact-specific tests cover interval boundaries, overlap/hold validation, unknown coverage, versions, draft export rejection, concurrent conflicts, source/review tampering and access control. The input browser case edits limb, hold and contact/release frames, saves, seeks, exports and verifies refresh recovery on mobile/desktop viewports. Synthetic corrections test the workflow; they are not reviewed climbing evidence. Existing Trial2/scientific compute modules are unchanged; no source fitting or technique comparison was rerun. Evidence: `backend/compute/runs/contact-review-acceptance/`.

The third structural pass passed 15 frontend/build tests (nine existing frontend cases, five plugin contracts and one live dev-server test), five enabled browser cases, and 35 backend tests (61 discovered, 26 environment-gated skips). Browser discovery skipped three additional opt-in cases. Type checking, production build and diff checks passed. All eight generated JS/CSS/HTML/robots files matched the pre-refactor build byte for byte; concatenated CSS declarations and order matched exactly. The other 88 snapshotted source files, including compute and legacy code, were unchanged. Plugin regression covers metadata, error replay, refresh fallback, Make kit, linked sourcemaps, API proxies and private-file denial. No source fitting or technique comparison was rerun. Local evidence: `backend/compute/runs/refactor-round3/`.

The second structural pass passed 35 API/contract/operations tests (61 discovered, 26 environment-gated skips), nine frontend tests, and six separately enabled browser cases: upload/retry, result playback, input review, compute review, video visibility/deletion/refresh, and Community retry/account isolation. Type checking and production build passed. The pre/post-extraction OpenAPI schemas are identical; all 31 snapshotted compute Python files and the main CSS file are byte-identical. No source fitting or technique comparison was rerun. Local records: `backend/compute/runs/refactor-round2/`.

The first deduplication regression passed 33 API/contract/operations tests (58 discovered, 25 environment-gated skips), seven frontend tests, four separately enabled browser cases (upload/retry, result playback, input review and compute-review login/upload/notifications/playback), and one calibration/provenance test in the scientific environment. Type checking, production build and diff whitespace checks passed. Media tests cover byte-exact partial/open-ended/suffix responses, invalid ranges, endpoint-specific compatibility, private access and integrity. The 39 snapshotted compute/legacy modules outside media were byte-identical. Scientific source fitting and technique comparison were not rerun. Local records: `backend/compute/runs/refactor-round1/`.

Run ordinary API tests without enabling scientific prerequisites; use the Beta Translator Python environment for scientific tests. Browser suites require the source checkout but do not need scientific imports in the API interpreter. The shared fixture gives each schema its own login-throttle state to avoid unrelated suites exhausting the same in-memory limit.

The earlier new-input update recorded 56 discovered tests: 32 passed, 24 environment-gated skips. Separately, two real new-input worker tests, a scientific plane-calibration test, input-review and upload browser suites, and four frontend classification tests passed. Type checking and production build passed. Skips are not passes; these figures are historical execution evidence, not a new algorithm run during refactoring.

| Run | Input | Measured time and scope |
| --- | --- | --- |
| v5 source | Trial2, 32.533 s, 976 frames | 371.44 s analysis |
| v5 target | Same source, 170/175 cm | 93.93 s generation |
| New-video extraction | 4 s Trial3 clip starting at original 5 s; 720×1280, 60 analysis frames | 34.07 s initial direct run; approximately 22–24 s scientific processing in queue acceptance |

The new-video clip produced 50 hold candidates and 240 limb observations; it is not full-length Trial3 acceptance. The recorded local machine is Apple M5 with 16 GiB RAM. CPU contention, warm files/models and queue delay affect measurements. No phone latency or stable preview-time target is established.

Local evidence paths: `backend/compute/runs/phase3-real-62fc330f/validation.json`, `new-inputs-acceptance/validation.json`, `new-inputs-suite.log`, and `community-v5-*/` under the same runs directory. Chromium viewport tests are not physical iOS/Safari or multi-phone acceptance.

<a id="demo"></a>
## 11. Demo and troubleshooting

Start the local stack, log in, and use an actual uploaded video to demonstrate permissions. For Trial2, upload the unchanged original to r1, run analysis, then use another account for personal generation. Show baseline labels alongside playback and diagnostic jumps. For a new video, demonstrate extracted inputs and calibration review without claiming completed adaptation.

The existing offline v5 fallback is `backend/compute/runs/standby-v5-community/index.html`, packaged as `standby-v5-community.zip` alongside it. It contains real precomputed source/target diagnostic results with failed baselines, not a live task. Verify with:

```sh
backend/.venv/bin/python -m backend.compute.standby verify backend/compute/runs/standby-v5-community
```

ZIP SHA-256: `64dcfe608ee71f8e92457991708e17ce065c94cb380ea072ef913337f654de67`. Copy it separately to another machine; it is Git-ignored. This is an artifact fallback, not a full database/application backup. Old v2 standby packages remain historical.

| Symptom | Action |
| --- | --- |
| Login/mutation rejected | Check exact origin, session and CSRF; restart API after configuration changes |
| Queue does not progress | Check database/storage settings and the single worker; a second worker is intentionally rejected |
| Worker interrupted | Restart with the same configuration; retry the failed attempt explicitly |
| Source/version mismatch | Use the correct recording and current analysis; never relabel old artifacts |
| Input extraction fails | Inspect private `work/<task-id>/worker.log`; the saved upload remains available |
| Calibration conflict | Reload the saved review before editing; supply measured geometry, not guessed pass-producing values |
| Artifact access denied | Check current source visibility and account; do not bypass protection with static URLs |
| Baseline fails | Show diagnostics and preserve the failed status; do not claim a feasible technique |

<a id="next"></a>
## 12. Responsibilities and next steps

A owns account/video foundations, storage, deployment and backup recovery. B owns catalog/community experience, persistent social interactions and shared visual polish. C owns algorithm adapters, task execution, result contracts and notification services. C has also connected the main-page compute workflows; this supersedes older plans that described that integration as wholly pending for B.

Recommended C sequence:

1. Manual contact correction is implemented; review real recordings and bind an explicit contact version when future reconstruction tasks consume these inputs.
2. Global alignment code passes synthetic known-truth acceptance; collect real handheld wall/camera measurements and per-frame controls for real-data validation. Automatic camera self-calibration/SfM is not implemented.
3. Integrate new-video source reconstruction, then target-body adaptation; validate on a non-Trial2 full recording.
4. When source investigation resumes, resolve the two remaining Trial2 contact segments without weakening thresholds or deleting failures.
5. After a valid baseline, implement full-model checks and limited applicable technique comparisons, with reproducible scoring and explanations. Initial scope preserves contact order/timing and compares at most three candidates; ties retain the baseline.
6. Measure full-length latency, test real devices, improve the developer calibration editor with B, and update standby/handoff evidence after algorithm changes.

Source-motion diagnostics and real technique comparison remain paused by the current project decision. Social persistence, deployment and device rehearsal need A/B collaboration. Email recovery, operating-system push notifications, user-created gyms/routes, cloud scaling and automatic backup tooling are outside the completed prototype.

<a id="history"></a>
## 13. References and version history

Algorithm source: CIS5810 **Beta_Translator**, commit `ff85726da2fbbd2616c409b01d6c03833ab62ce9`. Attribution remains in the code. Referenced modules include `trials`, `trial2_scene3d`, `body_regions`, `body_legs`, notebook section 8D / `trial1_technique_pipeline`, and the new-video `trial_pipeline` / `wholebody_pose` entry points. Borrowed ideas are distinguished from new BetaLab validation and orchestration; the original project was not modified by this documentation cleanup.

Original Trial2 video SHA-256: `9964d27ca051953d77cf10ee94a1772bd73e30d7e23fa09a54983c3630e8a068`. Versions, hashes and actual confidence belong with each artifact, not just its display name.

| History | Current interpretation |
| --- | --- |
| Frontend-only / local-server experiments | Historical; their session-only claims and quick/detailed timings do not describe the current authenticated stack |
| A's foundation and Yiru engineering log | Accounts, catalog, private uploads and sharing decisions retained; later task implementation supersedes old pending-task notes |
| C phases 1–5 | Contracts → persistence → real artifacts → diagnostics → operational rehearsal; completion of a stage did not establish algorithm feasibility |
| v3/v4 source studies | Historical geometry assumptions/results; not current wall measurements or performance |
| v5 geometry repair | Confirmed wall angles/boundaries, improved source/target fit; baseline still failed |
| Subsequent product work | Community generation, upload/retry, result classification and independent new-video inputs integrated |
| Documentation consolidation | Two synchronized language editions, original documents archived; code, algorithms and output paths unchanged |
| First deduplication pass | Shared frontend client/types, shared media transport and independent test helpers; algorithm behavior and source fingerprints retained |
| Second structural pass | Pages and feature hooks, unified video mutations, and backend auth/catalog/video modules; API contracts and algorithms retained |
| Third structural pass | CSS split in original cascade order and five extracted Vite plugins; production assets remain byte-identical |
| Manual contact review | Separate immutable human corrections and pinned dense exports; new-video reconstruction remains pending |
| Global geometry review | Measured hinge/camera workflow and pinned world export; synthetic acceptance only, real handheld data pending |

The local-only, Git-ignored `docs/archive/documentation-2026-11-19.zip` archive contains all 23 prior documentation files, including README.txt, the implementation plan, Yiru's log, backend/local-server guides and 15 compute documents. `MANIFEST.json` inside the ZIP records each original path and SHA-256. Archive SHA-256: `1288612b30634c28fe4189432c341cd8e97dd16712a9cb6f8e265455cc4b469a`. Extract it into a separate directory to inspect history without overwriting this handbook. Original text and authorship are preserved; historical claims are not current instructions.

Maintain both language editions together. Keep operational explanations here, schemas in their existing machine-readable directory, and detailed run evidence in private/local artifact storage. Do not create another phase-specific README for each update.
