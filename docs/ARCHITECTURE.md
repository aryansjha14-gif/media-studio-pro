# Architecture

```
┌────────────────────────────┐        HTTPS/JSON + multipart
│  Android app (Kotlin)      │  ───────────────────────────────┐
│  Compose UI                │                                 │
│  Retrofit + OkHttp         │  ◀──── polls /v1/jobs/{id} ────┐ │
│  Coil (images) / Media3    │                                │ │
└────────────────────────────┘                                │ │
                                                              │ │
┌─────────────────────────────────────────────────────────────┴─┴────────┐
│  FastAPI backend                                                       │
│                                                                        │
│  routers/          thin HTTP layer, validation via pydantic schemas    │
│     media.py       upload + probe + thumbnail                          │
│     images.py      adjust (sync) · prompt/generate/upscale/bg (jobs)   │
│     videos.py      trim/frame (sync) · merge/generate/prompt (jobs)    │
│     jobs_router.py polling                                             │
│                                                                        │
│  services/         deterministic engines                               │
│     image_ops.py   Pillow: crop, resize, grade, presets, Lanczos       │
│     video_ops.py   ffmpeg/ffprobe subprocess wrappers                  │
│                                                                        │
│  providers/        pluggable AI backends (one interface)               │
│     base.py        AIProvider ABC                                      │
│     fal.py         FLUX Kontext, Kling, clarity-upscaler, rembg        │
│     gemini.py      Gemini image editing (images only)                  │
│     replicate.py   any Replicate model                                 │
│     mock.py        offline placeholder results for dev/CI              │
│                                                                        │
│  storage.py        local disk MediaStore (swap for S3/R2)              │
│  jobs.py           in-process async job manager                        │
└────────────────────────────────────────────────────────────────────────┘
```

## Why the split between instant and job endpoints

Colour grading, cropping and trimming are pure CPU work that finishes in
tens of milliseconds — making the client poll for those would be pointless
latency. Everything that calls a model is 3–60 s (plus cold starts), so it is
queued as a `Job` and the client polls. That keeps the app responsive, survives
flaky mobile networks, and means a slow model never holds an HTTP connection
open on a phone.

## Request lifecycle for a prompt edit

1. App `POST /v1/media` with the picked file → `MediaAsset{id}`.
2. App `POST /v1/images/{id}/prompt` → `202 Job{id, status: queued}`.
3. `JobManager` runs `provider.edit_image(bytes, prompt)` on the event loop.
4. Provider returns bytes; the router's closure writes a new `MediaAsset`
   (result + thumbnail + `asset.json`) and attaches it to the job.
5. App polls `GET /v1/jobs/{id}` until `status` is terminal, then loads
   `asset.url` with Coil. The original asset is untouched, so undo is free —
   the app just keeps the previous `MediaAsset` in a history stack.

Nothing is ever edited in place: every operation produces a new asset with its
own id. That makes undo, versioning and provenance (`meta.tool`, `meta.prompt`)
trivial, and means a bad AI edit can never destroy the user's original.

## Adding a new AI provider

1. Subclass `AIProvider` in `backend/app/providers/yourprovider.py`.
2. Implement the methods you support; leave the rest to raise
   `NotImplementedError` (the job manager turns that into a clean job error).
3. Register it in `providers/__init__.py::get_provider`.
4. `AI_PROVIDER=yourprovider` in `.env`. No router, schema or Android change.

## Scaling notes

- **Jobs**: in-process. For more than one replica, move `JobManager` onto
  Redis + a worker (arq/Celery) and store job state in Redis. The routers only
  call `jobs.submit(...)` and `jobs.get(...)`, so that is the only surface to
  replace.
- **Storage**: `MediaStore` is four methods over a directory. Swap for S3/R2 and
  return presigned URLs from `url_for`.
- **Rate limiting / auth**: add an API-key dependency on the routers before
  exposing this publicly — model calls cost money per request.
- **Large uploads**: stream to storage instead of `await file.read()` if you
  raise `MAX_UPLOAD_MB` into the hundreds.
