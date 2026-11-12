# Local Trial 2 quick preview + background detailed solve

The existing CIS 5810 algorithm is unchanged by this integration. GitHub Pages is not updated.

## Start

Use Node.js on PATH and the existing CIS 5810 Python environment with FFmpeg.

- One-time evidence preparation: `$BETA_TRANSLATOR_ROOT/.venv/bin/python local-server/prepare_quick.py` (the script also supports the project's default local path).
- Start both services: `bash local-server/start-local.sh`.
- Open http://127.0.0.1:5174 → Community → Gym A V3 → Skeleton Preview.

BETA_TRANSLATOR_ROOT defaults to the local CIS 5810/Beta_Translator directory. The API binds only to 127.0.0.1:8787 and Vite proxies /api. This is not a production service.

## Two results

Quick: Trial 2 frames 0–975 (full 32.53-second video), 30 FPS. Source seed comes from saved source-motion initialization, not a newly validated plan. Per-frame bounded IK uses the user's complete profile, exact bone lengths, known target contact anchors, a pose prior, continuity residual and coordinate-speed bounds. Eight function evaluations maximum per frame. No full dynamics/fatigue/force solve. Remaining contact gaps are rendered without snapping endpoints.

Detailed: the existing 15-iteration steady BodyModel solve runs through its own queue after quick completion. All its constraints and audits remain enabled. Quick output stays available on detailed failure. The user explicitly switches views; detailed output never auto-replaces a playing quick preview.

The renderer includes 14 inferred route-hold bounding footprints projected onto the calibrated wall. These are schematic footprints of detected holds, not scanned 3D hold meshes. Active contact targets are orange; other route holds blue. Camera/panel calibration and contact labels remain inferred, not expert-verified.

Unmeasured body lengths use declared template ratios; only height and arm span are user inputs. No generated result certifies physical feasibility. Initial source seed is 175 cm; every requested body is recomputed through personalized kinematics and IK.

## Files and cache

Ignored prepared/ contains video-dependent evidence; regenerate it after changing the source/calibration/contact evidence. Ignored jobs/ retains request snapshots, quick trajectories, diagnostics, status, videos and full solver artifacts. Engine/profile identity controls cache reuse. Restarted interrupted jobs are marked failed while completed quick videos remain available.

There are separate single-worker queues for quick and detailed tasks. A later quick request can run while an earlier detailed task is active, with possible CPU contention. No authentication or public hosting is added. Uploads/comments/library remain frontend prototype features.

## Contact-evidence and transition refinement (2026-11-12)

Quick fitting excludes contact episodes with zero supporting evidence frames; supported contacts with confidence below 0.45 receive weight 0.35. This is evidence screening, not a guarantee of correct labels. Trial 2 right-foot H109 frames 239–253 have no supporting frames and visual inspection shows the feet away from the hold. The original labels are preserved and no replacement contact is invented. Detailed solving still uses the original canonical evidence.

During unanchored intervals, a smooth approach guide looks ahead at most 15 frames (0.5 s) to the next supported contact. It does not release supported contacts early or change their timestamps. Existing personalized dimensions, joint/rate limits, iteration budget and hold rendering remain in place. Raw-label and supported-contact errors are reported separately.

The paired full-video benchmark is benchmarks/contact-guidance-comparison.json. At height 168 cm / arm span 170 cm, worker time was 28.98 s before and 31.20 s after; API ready time after was 31.57 s. These are single runs with a detailed solver active, not stable latency guarantees.
