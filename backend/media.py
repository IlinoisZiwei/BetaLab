"""Shared byte-range transport. Callers retain authorization and integrity checks."""
import re
from fastapi import Request, Response
from fastapi.responses import StreamingResponse

RANGE = re.compile(r'bytes=(\d*)-(\d*)$')


def ranged_file(path, request: Request, media_type, *, upload_compatibility=False, extra_headers=None):
    size = path.stat().st_size
    start, end, status = 0, size - 1, 200
    header = request.headers.get('range')
    if header:
        # Preserve the existing upload endpoint's permissive empty-range behavior.
        # Compute artifacts retain their stricter syntax/length policy.
        match = RANGE.fullmatch(header) if upload_compatibility or len(header) <= 128 else None
        if not match or (not upload_compatibility and not any(match.groups())):
            return Response(status_code=416, headers={'Content-Range': f'bytes */{size}'})
        first, last = match.groups()
        if first:
            start = int(first)
            end = min(int(last), size - 1) if last else size - 1
        elif last:
            start = max(0, size - int(last))
        if start >= size or end < start:
            return Response(status_code=416, headers={'Content-Range': f'bytes */{size}'})
        status = 206
    headers = {'Accept-Ranges': 'bytes', 'Content-Length': str(end - start + 1),
               'Cache-Control': 'private, no-store', 'X-Content-Type-Options': 'nosniff',
               **(extra_headers or {})}
    if status == 206:
        headers['Content-Range'] = f'bytes {start}-{end}/{size}'

    def chunks():
        with path.open('rb') as stream:
            stream.seek(start)
            remaining = end - start + 1
            while remaining:
                data = stream.read(min(1024 * 1024, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(chunks(), status_code=status, media_type=media_type, headers=headers)
