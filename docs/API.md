# Media Studio API — reference

Base URL: `http://<host>:8000`. Interactive docs: `/docs` (Swagger), `/redoc`.

Two kinds of endpoints:

| Kind | Behaviour | Client code |
|---|---|---|
| **Instant** (`/adjust`, `/trim`, `/frame`) | Pillow/ffmpeg work, returns `MediaAsset` immediately | one request |
| **AI** (`/prompt`, `/generate`, `/upscale`, `/remove-background`, video prompt/generate) | returns `Job` with `202`, you poll `/v1/jobs/{id}` | poll every ~1.2 s |

---

## Objects

### MediaAsset
```json
{
  "id": "53aabea539514726",
  "kind": "image",
  "url": "http://host:8000/files/53aabea539514726/original.jpg",
  "thumb_url": "http://host:8000/files/53aabea539514726/thumb.jpg",
  "width": 1920, "height": 1080, "duration": null,
  "size_bytes": 284113, "mime": "image/jpeg",
  "created_at": "2026-10-29T02:55:20Z",
  "meta": {"tool": "adjust", "filename": "original.jpg"}
}
```

### Job
```json
{
  "id": "dca5b99f9176438b",
  "kind": "image.prompt",
  "status": "succeeded",          // queued | running | succeeded | failed
  "progress": 1.0,
  "asset": { ...MediaAsset... },  // present when succeeded
  "error": null                   // present when failed
}
```

---

## Media

### `POST /v1/media`
`multipart/form-data`, field `file`. Images (jpg/png/webp/bmp) and video (mp4/mov/mkv/webm/avi/m4v/3gp).
Returns `201` + `MediaAsset` with dimensions, duration and a thumbnail.

Errors: `413` too large, `415` unsupported type.

### `GET /v1/media/{id}`
Returns the `MediaAsset`.

---

## Images

### `POST /v1/images/{id}/adjust` → `MediaAsset`
All fields optional; omitted fields are no-ops.
```json
{
  "crop": {"x": 0, "y": 0, "width": 800, "height": 800},
  "rotate": 90,
  "flip_horizontal": false,
  "flip_vertical": false,
  "resize": {"width": 1080, "fit": "cover"},
  "brightness": 1.1, "contrast": 1.05, "saturation": 1.2,
  "sharpness": 1.0, "blur": 0,
  "filter": "sepia",
  "quality": 92
}
```
`filter` ∈ `none | grayscale | sepia | warm | cool | vintage | punch | mono`.
`resize.fit` ∈ `cover | contain | stretch`.

### `POST /v1/images/{id}/prompt` → `202 Job`
```json
{ "prompt": "make it a rainy night in Mumbai, neon reflections", "mask_media_id": null }
```

### `POST /v1/images/generate` → `202 Job`
```json
{ "prompt": "studio portrait, soft rim light", "width": 1024, "height": 1024 }
```

### `POST /v1/images/{id}/upscale?factor=2` → `202 Job`
Falls back to Lanczos sharpening when the provider has no upscaler.

### `POST /v1/images/{id}/remove-background` → `202 Job`
Returns a transparent PNG.

---

## Video

### `POST /v1/videos/{id}/trim` → `MediaAsset`
```json
{ "start": 1.5, "end": 6.0, "reencode": true }
```
`reencode: false` is instant but snaps to keyframes.

### `POST /v1/videos/{id}/frame` → `MediaAsset` (an image)
```json
{ "at": 2.4 }
```

### `POST /v1/videos/merge` → `202 Job`
```json
{ "media_ids": ["id1", "id2"] }
```

### `POST /v1/videos/generate` → `202 Job`
```json
{ "prompt": "drone shot over the ghats at sunrise", "duration": 5, "aspect_ratio": "16:9" }
```
`duration` 2–10 s, `aspect_ratio` ∈ `16:9 | 9:16 | 1:1`.

### `POST /v1/videos/{id}/prompt` → `202 Job`
Video-to-video restyle.

---

## Jobs & meta

| Endpoint | Purpose |
|---|---|
| `GET /v1/jobs/{id}` | poll one job |
| `GET /v1/jobs?limit=25` | recent jobs |
| `GET /health` | status + active provider |
| `GET /files/{media_id}/{file}` | raw media bytes (used by the app's image/video views) |

### Error shape
```json
{ "detail": "human readable message", "code": "video_engine_unavailable" }
```
`503` means ffmpeg is missing on the server. `501`-style failures surface as a
`Job` with `status: "failed"` and a message like
`"not supported by the configured provider: gemini cannot generate video"`.
