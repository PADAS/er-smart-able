#!/usr/bin/env bash
# Convert a SMART Conservation Area export (SMART Desktop: File > Export
# Conservation Area) into the CSV layout DumpSmartDb writes, so the rest of the
# pipeline (csv_to_parquet.sh, the browser) is the same for both inputs.
#
# The export's database/ folder holds one Derby table export per table:
#   smart.<table>.<Entity>.dat  the rows: RFC-4180 CSV, no header row, NULL as
#                               an unquoted empty field, binary as lowercase hex
#                               (the same conventions DumpSmartDb uses)
#   smart.<table>.<Entity>.def  line 1 "SMART.<TABLE>", line 2 the column names
#                               (CRLF, and no newline after the last line)
# The .def carries no column types, so they come from smart_schema.tsv;
# every column not listed there is VARCHAR. db_versions.dat (plugin_id,version;
# it has no .def) is written as db_version.csv, the table name the database has.
# A table that backs several Hibernate subclasses (plan_target: Numeric-,
# Spatial-, AdministrativePlanTarget) is exported once per subclass, with the
# same columns; those parts are concatenated into one CSV.
#
# Usage: export_to_csv.sh <export_dir> <csv_dir>
set -euo pipefail
EXP=${1:?usage: export_to_csv.sh <export_dir> <csv_dir>}
CSV_DIR=${2:?usage: export_to_csv.sh <export_dir> <csv_dir>}
TYPES=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/smart_schema.tsv
[ -d "$EXP/database" ] || { echo "no database/ folder in $EXP"; exit 1; }
mkdir -p "$CSV_DIR"
n=0; rows=0; seen=
for def in "$EXP"/database/smart.*.def; do
  dat=${def%.def}.dat
  [ -f "$dat" ] || { echo "no .dat for $(basename "$def")"; exit 1; }
  table=$(awk 'NR==1 { sub(/\r$/, ""); sub(/^SMART\./, ""); print tolower($0) }' "$def")
  cols=$(awk 'NR==2 { sub(/\r$/, ""); print tolower($0) }' "$def")
  [ -n "$table" ] && [ -n "$cols" ] || { echo "unreadable .def: $def"; exit 1; }
  case " $seen " in
    *" $table "*)   # another subclass of a table already started: append its rows
      [ "$(head -1 "$CSV_DIR/$table.csv")" = "$cols" ] || { echo "column mismatch between parts of $table: $def"; exit 1; }
      cat "$dat" >> "$CSV_DIR/$table.csv"
      r=$(wc -l < "$dat"); rows=$((rows + r))
      printf '%-45s %8d rows (appended)\n' "$table" "$r"
      continue ;;
  esac
  seen="$seen $table"
  { printf '%s\n' "$cols"; cat "$dat"; } > "$CSV_DIR/$table.csv"
  # .columns sidecar in the same form DumpSmartDb writes: {'col': 'TYPE', ...}
  awk -F'\t' -v t="$table" -v cols="$cols" '
    /^#/ || NF < 3 { next }
    $1 == t { type[$2] = $3 }
    END {
      k = split(cols, c, ",")
      out = "{"
      for (i = 1; i <= k; i++)
        out = out (i > 1 ? ", " : "") "\047" c[i] "\047: \047" (c[i] in type ? type[c[i]] : "VARCHAR") "\047"
      printf "%s}", out
    }' "$TYPES" > "$CSV_DIR/$table.columns"
  r=$(wc -l < "$dat")
  rows=$((rows + r)); n=$((n + 1))
  printf '%-45s %8d rows\n' "$table" "$r"
done
if [ -f "$EXP/database/db_versions.dat" ]; then
  { echo "plugin_id,version"; cat "$EXP/database/db_versions.dat"; } > "$CSV_DIR/db_version.csv"
  printf "{'plugin_id': 'VARCHAR', 'version': 'VARCHAR'}" > "$CSV_DIR/db_version.columns"
  n=$((n + 1))
fi
echo "done: $rows rows across $n tables"   # line count: a value with embedded newlines counts more than once
