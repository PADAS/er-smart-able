#!/usr/bin/env bash
# Convert the DumpSmartDb CSV output to one Parquet file per table.
# Column types come from the .columns sidecar the dumper writes (real Derby
# types via JDBC metadata), so nothing is ever type-sniffed — all-numeric
# VARCHAR ids like '000123' keep their leading zeros.
# allow_quoted_nulls=false keeps quoted empty strings ('') distinct from NULL
# (the dumper writes NULL as an unquoted empty field). quote/escape are set
# explicitly: both DumpSmartDb and SMART's Conservation Area exports double
# quotes inside values (RFC 4180), and DuckDB's sniffer sometimes guesses an
# empty escape from the sample, which then fails on a value such as "a ""b"" c".
#
# Credentials are left out of the Parquet unless KEEP_CREDENTIALS=1
# (./smart-able extract --keep-credentials): SMART stores each user's desktop
# login as a bcrypt hash in employee.smartpassword, and SMART Connect server
# logins in connect_account.connect_pass. The Parquet is what gets shared
# with analysts; the CSV and database copy in work/ still hold everything.
#
# Usage: csv_to_parquet.sh <csv_dir> <parquet_dir>
set -euo pipefail
CSV_DIR=${1:?usage: csv_to_parquet.sh <csv_dir> <parquet_dir>}
PQ_DIR=${2:?usage: csv_to_parquet.sh <csv_dir> <parquet_dir>}
CREDENTIAL_COLUMNS="employee.smartpassword connect_account.connect_pass"
mkdir -p "$PQ_DIR"
n=0
for f in "$CSV_DIR"/*.csv; do
  t=$(basename "$f" .csv)
  cols=$(cat "$CSV_DIR/$t.columns")
  drop=
  if [ "${KEEP_CREDENTIALS:-0}" != 1 ]; then
    for tc in $CREDENTIAL_COLUMNS; do
      [ "${tc%%.*}" = "$t" ] || continue
      c=${tc#*.}
      case $cols in *"'$c':"*) drop="$drop${drop:+, }$c"; echo "  dropping $t.$c (credentials; --keep-credentials keeps them)" ;; esac
    done
  fi
  duckdb -c "COPY (SELECT * ${drop:+EXCLUDE ($drop)} FROM read_csv('$f', header=true, columns=$cols, quote='\"', escape='\"', allow_quoted_nulls=false, max_line_size=100_000_000)) TO '$PQ_DIR/$t.parquet' (FORMAT parquet, COMPRESSION zstd);" \
    || { echo "FAILED: $t"; exit 1; }
  n=$((n + 1))
done
echo "converted $n tables to parquet"
