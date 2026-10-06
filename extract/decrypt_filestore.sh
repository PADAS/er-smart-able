#!/usr/bin/env bash
# Decrypt the SMART filestore attachments into a plaintext mirror.
#
# SMART encrypts attachment files with AES-128-CBC: the key is the 16 raw
# bytes of the conservation-area UUID (= the CA's folder name in the
# filestore), and the first 16 bytes of each file are the IV
# (org.wcs.smart.cipher.EncryptUtils in the SMART source).
#
# Covers patrol waypoint attachments (<ca>/patrol/...) and Profiles
# attachments (<ca>/intelligence2/attachments/...). The output mirrors the
# filestore layout: <out_dir>/<ca_uuid>/...
#
# A Conservation Area export's filestore holds a single CA and omits the
# <ca_uuid>/ level (patrol/... sits at its top). Pass that CA's uuid as the
# third argument: it is the key for every file, and the output still goes
# under <out_dir>/<ca_uuid>/ so the browser finds it in the usual place.
#
# Usage: decrypt_filestore.sh <filestore_dir> <out_dir> [ca_uuid]
set -u
FS=${1:?usage: decrypt_filestore.sh <filestore_dir> <out_dir> [ca_uuid]}
OUT=${2:?usage: decrypt_filestore.sh <filestore_dir> <out_dir> [ca_uuid]}
SINGLE_CA=${3:-}
FS=${FS%/}
hexbytes() { od -An -tx1 -N "$1" "$2" | tr -d ' \n'; }
ok=0; plain=0; fail=0
while IFS= read -r -d '' f; do
  rel=${f#"$FS"/}
  if [ -n "$SINGLE_CA" ]; then ca=$SINGLE_CA; dest="$OUT/$ca/$rel"; else ca=${rel%%/*}; dest="$OUT/$rel"; fi
  mkdir -p "$(dirname "$dest")"
  case $(hexbytes 4 "$f") in
    ffd8*|8950*|2550*|4749*) cp "$f" "$dest"; plain=$((plain + 1)); continue ;;  # already plaintext jpg/png/pdf/gif
  esac
  iv=$(hexbytes 16 "$f")
  if [ ${#iv} -ne 32 ]; then echo "SKIP (too small): $rel"; fail=$((fail + 1)); continue; fi
  if tail -c +17 "$f" | openssl enc -d -aes-128-cbc -K "$ca" -iv "$iv" -out "$dest" 2>/dev/null; then
    ok=$((ok + 1))
  else
    rm -f "$dest"; echo "FAILED: $rel"; fail=$((fail + 1))
  fi
done < <(find "$FS" \( -path "*/patrol/*" -o -path "*/intelligence2/attachments/*" \) -type f -print0)
echo "decrypted: $ok, copied plaintext: $plain, failed: $fail"
