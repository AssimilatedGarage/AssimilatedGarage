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
