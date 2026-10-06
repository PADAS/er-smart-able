#!/usr/bin/env bash
# Compare the schema of what was just extracted (the .columns sidecars in
# <csv_dir>, one per table) with the snapshot in smart_schema.tsv, and warn
# about every difference: tables or columns that are new or missing, and (for
# a database, whose types come from JDBC) columns whose type changed. It also
# warns when the data's SMART schema version is not the snapshot's, because
# the browser SQL and docs/smart-data-model.md were written against the
# snapshot and may not hold for other versions.
#
# For a Conservation Area export the column types come from the snapshot
# itself, so a new column is also a column that was loaded as text; and an
# export omits SMART's install-wide tables, so missing tables are only noted.
#
# Warnings go to stderr, prefixed "warning:". The exit status is always 0:
# differences are information for whoever reads the output, not failures.
#
# Usage: check_schema.sh <csv_dir> <database|export> [data_schema_version]
set -euo pipefail
CSV_DIR=${1:?usage: check_schema.sh <csv_dir> <database|export> [data_schema_version]}
INPUT=${2:?usage: check_schema.sh <csv_dir> <database|export> [data_schema_version]}
VER=${3:-}
SNAP=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/smart_schema.tsv
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
snap_ver=$(awk -F': ' '/^# schema-version:/ { print $2; exit }' "$SNAP")
warned=0

if [ -z "$VER" ]; then
  warn "the SMART schema version of this data is unknown (no db_version table), so it was compared with the snapshot's, $snap_ver"
  warned=1
elif [ "$VER" != "$snap_ver" ]; then
  warn "this data is SMART schema $VER; smart_schema.tsv, the browser, and docs/smart-data-model.md were written against $snap_ver, so what follows are the deltas, and the browser's assumptions may not all hold"
  warned=1
fi

# the extracted schema, as table<TAB>column<TAB>type lines
extracted() {
  local f t
  for f in "$CSV_DIR"/*.columns; do
    t=$(basename "$f" .columns)
    tr -d "{}'" < "$f" | tr ',' '\n' | sed 's/^ *//' | awk -F': ' -v t="$t" 'NF == 2 { print t "\t" $1 "\t" $2 }'
  done
}

# one line per difference: KIND<TAB>detail, sorted by kind then name.
# A snapshot row with a version in its 4th field is a later addition: it is
# expected only when the data is at least that version (major.minor compare).
diffs=$(awk -F'\t' -v input="$INPUT" -v ver="$VER" '
  function minor(v,  a) { split(v, a, "."); return a[1] * 1000 + a[2] }
  FNR == NR {
    if ($0 ~ /^#/ || NF < 3) next
    if (NF >= 4 && $4 != "" && (ver == "" || minor(ver) < minor($4))) { later[$1 SUBSEP $2] = 1; next }
    snap[$1 SUBSEP $2] = $3; stab[$1] = 1; next
  }
  { data[$1 SUBSEP $2] = $3; dtab[$1] = 1; ncol[$1]++ }
  END {
    for (t in dtab) if (!(t in stab)) print "new table\t" t " (" ncol[t] " columns)"
    for (t in stab) if (!(t in dtab)) print "missing table\t" t
    for (k in data) {
      split(k, p, SUBSEP); t = p[1]; c = p[2]
      if (!(t in stab)) continue
      if (k in later) print "new column\t" t "." c " (known from a later SMART version)"
      else if (!(k in snap)) print "new column\t" t "." c (input == "export" ? " (loaded as text)" : " (" data[k] ")")
      else if (input == "database" && snap[k] != data[k]) print "type change\t" t "." c " " snap[k] " -> " data[k]
    }
    for (k in snap) {
      split(k, p, SUBSEP); t = p[1]; c = p[2]
      if ((t in dtab) && !(k in data)) print "missing column\t" t "." c
    }
  }' "$SNAP" <(extracted) | sort)

if [ -n "$diffs" ]; then
  for kind in "new table" "missing table" "new column" "missing column" "type change"; do
    list=$(printf '%s\n' "$diffs" | awk -F'\t' -v k="$kind" '$1 == k { print $2 }')
    [ -n "$list" ] || continue
    n=$(printf '%s\n' "$list" | wc -l | tr -d ' ')
    if [ "$kind" = "missing table" ] && [ "$INPUT" = export ]; then
      echo "  not in the export ($n tables, normal for an export): $(printf '%s\n' "$list" | tr '\n' ' ')"
      continue
    fi
    warn "$kind${n:+ ($n)}, compared with smart_schema.tsv ($snap_ver):"
    printf '%s\n' "$list" | sed 's/^/    /' >&2
    warned=1
  done
fi
[ "$warned" = 1 ] || echo "  schema matches smart_schema.tsv ($snap_ver)"
