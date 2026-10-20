# Assimilated Garage

Website for **Assimilated Garage**: Sean Hopkins' pallet finds, parts, hardware and everything else.
Live at **https://assimilatedgarage.com**.

## Files
- `site.html`: the page itself (edit this one).
- `build.sh`: wraps `site.html` into `dist/index.html` and deploys it to Cloudflare.
- `dist/index.html`: the built page that gets served.
- `wrangler.jsonc`: Cloudflare Worker config (static site on assimilatedgarage.com and www).

## Updating the shelf
Items live in the `ITEMS` list near the bottom of `site.html`. Each item has a lot number, category,
title, price, optional was-price, condition grade (new, open, used, asis), description and an optional
`photo` path. Set `SAMPLE = false` once the real inventory is in.

## Deploy
```
sh build.sh
```
Needs a Cloudflare login (`npx wrangler login`) on the account that hosts the site.

## Shop by vehicle (/parts)
- `parts.html`: the page at **/parts**. Year / Make / Model picker (models come live from the free NHTSA vPIC API),
  a 3D truck you can spin, "Open it up" to explode it, tap a part to see what Sean has for it, and a plain list
  of every part spot underneath (works without 3D).
- `models/tacoma-style.glb`: our own 3rd-gen (2016-2023) double cab short bed, built from published dimensions and
  reference photos by `tools/make_tacoma.py` (no downloaded models, no badges, Draco-compressed, ~0.5 MB, 25 named parts).
  Rebuild it (add `-- --render` for preview stills in `research/renders`):
  `"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup -P tools/make_tacoma.py`
  The first blocky model is kept as `models/tacoma-style-v1.glb` (`tools/make_truck.py`).
  Reference photos live in `research/` (gitignored, reference only, never shipped).
- Only the Toyota Tacoma has a 3D view so far. Any other pick shows "3D view coming soon" plus the part list.

### Adding Sean's parts (listing template)
Edit `data/parts.json`. One object per listing. Sean's listings come in this fixed order, and the part panel shows
them in the same order (empty fields are skipped). Copy this block, fill it in, paste it at the top of `items`:
```
{
  "id": "short-unique-id", "spot": ["tonneau_cover"], "listed": "2026-10-19", "sold": false,
  "brand": "",
  "part": "",
  "partNumber": "",
  "fitment": [{ "years": [2016, 2023], "make": "Toyota", "model": "Tacoma", "note": "5 ft bed" }],
  "size": "",
  "condition": "",
  "conditionNotes": "",
  "damaged": false, "functional": true, "inPackaging": true, "missingParts": false,
  "price": 700,
  "qty": 1,
  "shipping": "",
  "description": "",
  "video": "https://youtu.be/VIDEO_ID",
  "retailerLink": "",
  "photos": ["/photos/short-unique-id-1.jpg"]
}
```
- `spot` is one or more part spots (names below). A set of four wheels can list all four wheel spots.
- `fitment` is a list of year range + make + model (+ optional note), or the string `"universal"`. Model names are
  matched loosely, so "F-250 Super Duty" also matches NHTSA's "F-250".
- `price` is dollars, or `null` to show "Price: ask Sean". `qty` shows "Qty available". `sold: true` hides it.
- `video` is a YouTube link; it shows as a play thumbnail and only loads the (youtube-nocookie) player when tapped.
- `description` is written in our own words; never paste a manufacturer's marketing copy or use their photos.
- Photos go in a `photos/` folder (build.sh copies it); the first one is the card photo. None = "Photo coming soon".
- Every real listing also shows in **All parts** at the bottom of /parts, newest `listed` first.
- Items with `"sample": true` are placeholders. Delete them when real items go in.

Part spots (mesh names): body_cab, hood, grille, bumper_front, bumper_rear, headlight_l, headlight_r,
taillight_l, taillight_r, mirror_l, mirror_r, door_fl, door_fr, door_rl, door_rr, wheel_fl, wheel_fr,
wheel_rl, wheel_rr, bed, tailgate, engine, running_board_l, running_board_r, tonneau_cover. `_l` / `fl` / `rl` = driver side.

### Swapping in a real (purchased) truck model later
Export it as `models/tacoma-style.glb` with the same object names as above, one object per part, with each
object's origin at the part's own centre. Nothing in the code needs to change. Materials named `paint`, `glass`,
`trim_black`, `tire`, `rim` etc. get the tuned look from `parts.html`; any other material keeps its own look.
Check the licence allows use on a commercial website. For a second vehicle, add another GLB and a
make/model check in `parts.html` (`isTacoma`).
