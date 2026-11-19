# Movement Fishtown route photos

Added 73 route-highlight photos from IMG_7518–IMG_7544 to gym `gym-a`, renamed **Movement Fishtown**. Existing route `r1` remains; Long Reach (`r2`) is removed from browsing, for 74 catalog entries in total. Migration 009 removes unused r2 data; if user videos reference it, it is archived to preserve those uploads. Different photos of the same physical route remain separate photo entries; this import does not deduplicate physical routes.

- Frontend data: `src/data/movementRoutes.json`
- Web assets: `public/media/movement-facetime/` (73 JPEGs, approximately 27 MB)
- Database import: `backend/db/migrations/008_movement_route_photos.sql`
- Navigation: Home → Go Climbing → Movement Fishtown → route

Images retain their full aspect ratio in the gallery and detail view. Photo entries do not borrow unrelated sample videos. Grades come from the image-editing selection notes; unspecified grades are Unrated. The highlighted images are generated visual edits, not exact hold masks. The two white routes in IMG_7536 and small teal holds in IMG_7539 require review; their detail views show a confirmation note.

## Apply to the database

Follow `backend/README.md` to start PostgreSQL and the API, then run from the repository root:

```sh
python3 backend/db/manage.py migrate
python3 backend/db/manage.py seed
```

The new migration works for an existing catalog or an empty database. It preserves existing route IDs and user uploads. Refresh the application after migrating. Do not edit migration 008 after applying it; create another numbered migration for corrections.

## Validation

Production build and TypeScript check passed. Browser validation with mocked API responses verified 74 cards, all 73 image URLs, grade filtering, white-route detail, desktop clicks, and a 390px viewport. The local machine has no Docker/PostgreSQL/API running, so the database migration and real authenticated workflow have not been executed here.

Original full-quality PNG files remain in the separate route-highlights delivery folder. The import script accepts that folder as its argument; it is a preparation utility, not part of runtime startup.
