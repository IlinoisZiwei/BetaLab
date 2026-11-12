# BetaLab

Live demo: https://ilinoisziwei.github.io/BetaLab/

Updates pushed to `main` are built and deployed by GitHub Actions.

A mobile-first climbing prototype built with React, TypeScript and Vite. Includes Community, Go Climbing, My Library, attempt review, example suggestions and skeleton previews.

## Run locally

Use Node.js 22.12 or newer.

```sh
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

Open http://127.0.0.1:5173.

## Build

```sh
npm run build
npm run preview -- --host 127.0.0.1 --port 5173
```

## Prototype scope

Climbing images and videos are included in `public/media`. Skeleton previews are precomputed demonstration assets. Profile changes do not run the separate CIS 5810 algorithm in this frontend. Suggestions are example content. Uploads, visibility, comments and account interactions are local demonstrations; session data resets on refresh. No backend authentication, online publishing or storage service is connected.

The latest interface uses gym and grade labels, a pale-blue theme, and Suggestions / Community Beta workspace tabs. See MEDIA-SOURCES.txt for recording provenance and README.txt for iteration notes.
