#!/bin/sh
# site.html (artifact format) -> dist/index.html (standalone), then deploy
cd "$(dirname "$0")"
{ printf '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n<style>body{margin:0}img{max-width:100%%}[hidden]{display:none!important}</style>\n'
  sed -n '1,/^<\/style>$/p' site.html; printf '</head>\n<body>\n'
  sed -n '/^<\/style>$/,$p' site.html | tail -n +2; printf '\n</body>\n</html>\n'; } > dist/index.html
npx wrangler deploy
