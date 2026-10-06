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
# Usage: csv_to_parquet.sh <csv_dir> <parquet_dir>
set -euo pipefail
CSV_DIR=${1:?usage: csv_to_parquet.sh <csv_dir> <parquet_dir>}
PQ_DIR=${2:?usage: csv_to_parquet.sh <csv_dir> <parquet_dir>}
mkdir -p "$PQ_DIR"
n=0
for f in "$CSV_DIR"/*.csv; do
  t=$(basename "$f" .csv)
  cols=$(cat "$CSV_DIR/$t.columns")
  duckdb -c "COPY (SELECT * FROM read_csv('$f', header=true, columns=$cols, quote='\"', escape='\"', allow_quoted_nulls=false, max_line_size=100_000_000)) TO '$PQ_DIR/$t.parquet' (FORMAT parquet, COMPRESSION zstd);" \
    || { echo "FAILED: $t"; exit 1; }
  n=$((n + 1))
done
echo "converted $n tables to parquet"
