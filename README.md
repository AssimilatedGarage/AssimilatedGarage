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
- `models/tacoma-style.glb`: our own Tacoma-style crew cab, made by `tools/make_truck.py` (no downloaded models,
  no badges). Rebuild it with:
  `"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup -P tools/make_truck.py`
- Only the Toyota Tacoma has a 3D view so far. Any other pick shows "3D view coming soon" plus the part list.

### Adding Sean's parts
Edit `data/parts.json`. One object per item:
```
{ "id": "tac-hl-01", "spot": ["headlight_l"], "title": "Headlight assembly, driver side",
  "price": 85, "condition": "Used, tested", "photo": "/photos/tac-hl-01.jpg", "sold": false,
  "fitment": [{ "years": [2016, 2023], "make": "Toyota", "model": "Tacoma" }] }
```
- `spot` is one or more part spots (names below). A set of four wheels can list all four wheel spots.
- `fitment` is a list of year ranges + make + model, or the string `"universal"`.
- `price` is dollars, or `null` to show "Price: ask Sean". `sold: true` hides it.
- Photos go in a `photos/` folder (build.sh copies it). No photo shows a "Photo coming soon" tile.
- The six items marked `"sample": true` are placeholders so the flow can be seen. Delete them when real items go in.

Part spots (mesh names): body_cab, hood, grille, bumper_front, bumper_rear, headlight_l, headlight_r,
taillight_l, taillight_r, mirror_l, mirror_r, door_fl, door_fr, door_rl, door_rr, wheel_fl, wheel_fr,
wheel_rl, wheel_rr, bed, tailgate, engine. `_l` / `fl` / `rl` = driver side.

### Swapping in a real (purchased) truck model later
Export it as `models/tacoma-style.glb` with the same object names as above, one object per part, with each
object's origin at the part's own centre. Nothing in the code needs to change. Materials named `paint`, `glass`,
`trim_black`, `tire`, `rim` etc. get the tuned look from `parts.html`; any other material keeps its own look.
Check the licence allows use on a commercial website. For a second vehicle, add another GLB and a
make/model check in `parts.html` (`isTacoma`).
