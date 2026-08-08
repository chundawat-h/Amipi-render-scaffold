# AMIPI Rendering Standardization — MVP Scaffold

## What this is
A working skeleton for the two pipelines discussed:
- **Path A (`render_3d`)** — CAD/STL/OBJ mesh in → headless Blender render out, driven by a
  versioned config in Postgres (the "documented rendering guideline," made queryable).
- **Path B (`normalize_2d`)** — existing JPEG/vendor photo in → background removal +
  recomposition onto the brand background (fixes dark backgrounds / inconsistent framing;
  cannot fix baked-in blur or add missing detail — that needs a real re-render).
- A **technical image** variant is generated for any job linked to a `product`, pulling SKU/
  stone/dimension data from Postgres and deliberately never reading `metal_type`.

## Setup

```bash
# 1. Postgres
docker compose up -d db

# 2. Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Blender itself is a separate system install, not a pip package — free download:
# https://www.blender.org/download/ (or `apt install blender` on the render server)
uvicorn app.main:app --reload

# 3. Frontend
cd frontend
npm install
npm run dev
```

Frontend dev server proxies `/api/*` to `localhost:8000` (see `vite.config.js`).

## What's real vs. stubbed
- **Real and working:** the full FastAPI app (routers, DB models, job lifecycle), the Postgres
  schema, the ERP Excel/CSV import endpoint, the Path B image-normalization pipeline
  (`rembg` + Pillow — this will run as-is), the technical-image overlay, and the frontend.
- **Skeleton, needs your input to finish:** `blender_render.py`'s materials (flat placeholder
  colors — swap in real PBR node graphs per metal type), lighting (basic 3-point rig — swap
  for a real HDRI once one's chosen), and background (flat color — the config schema supports
  a gradient, the script only implements flat for now). These are exactly the decisions that
  should come out of validating the "AMIPI Standard v1" template (`schema.sql`) with Sales/
  Marketing/Product Dev before hardening — no point guessing at a look nobody's signed off on.

## Open items before this goes further
1. **Mesh availability** — confirm with Product Dev whether raw STL/OBJ exports exist per
   product, or only screenshots like the three CAD sheets shared. This determines what
   fraction of the catalog actually gets Path A vs. Path B.
2. **ERP column names** — `routers/products.py`'s `column_map` guesses common header
   spellings; update it to match the actual Excel export once you have a sample file.
3. **Prod2 integration** — unknown how Prod2 ingests images today (watch folder? API? manual
   upload?). Once known, add an export step that pushes `output_paths` there instead of
   leaving images to be manually pulled from `/outputs`.
4. **OneDrive** — existing "live" images live there; a sync job (Microsoft Graph API) can feed
   Path B automatically, but manual upload works for the MVP without needing that integration yet.
