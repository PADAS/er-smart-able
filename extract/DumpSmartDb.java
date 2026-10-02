import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.ResultSetMetaData;
import java.sql.Statement;
import java.sql.Types;
import java.util.ArrayList;
import java.util.List;

/**
 * Dumps every table in the SMART schema of an embedded Derby database to one
 * CSV file per table (UTF-8, header row, RFC-4180 quoting). Binary columns
 * (the CHAR(16) FOR BIT DATA uuids, WKB geometry BLOBs) are written as
 * lowercase hex strings. NULL is written as an unquoted empty field;
 * non-null strings are always quoted, so a CSV reader with
 * allow_quoted_nulls=false can tell NULL from ''.
 *
 * Usage: java -cp "lib/derby/*" extract/DumpSmartDb.java <dbPath> <outDir>
 *   (normally run by `./smart-able extract`, which loads .env first)
 */
public class DumpSmartDb {
    static final char[] HEX = "0123456789abcdef".toCharArray();

    static String env(String name) {
        String v = System.getenv(name);
        if (v == null || v.isEmpty()) {
            System.err.println("missing required env var " + name + " (see .env.example)");
            System.exit(2);
        }
        return v;
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2) {
            System.err.println("usage: DumpSmartDb <dbPath> <outDir>");
            System.err.println("set SMART_DB_USER and SMART_DB_PASSWORD (see .env.example)");
            System.exit(2);
        }
        // SMART's embedded Derby uses fixed credentials baked into the desktop
        // app. They are not secret, but we read them from the environment so no
        // credential literal lives in source. See .env.example.
        String user = env("SMART_DB_USER"), password = env("SMART_DB_PASSWORD");
        Path outDir = Path.of(args[1]);
        Files.createDirectories(outDir);
        String url = "jdbc:derby:" + args[0];
        try (Connection c = DriverManager.getConnection(url, user, password)) {
            List<String> tables = new ArrayList<>();
            DatabaseMetaData md = c.getMetaData();
            try (ResultSet rs = md.getTables(null, "SMART", "%", new String[] {"TABLE"})) {
                while (rs.next()) tables.add(rs.getString("TABLE_NAME"));
            }
            System.out.println(tables.size() + " tables in schema SMART");
            long total = 0;
            for (String t : tables) {
                total += dumpTable(c, t, outDir.resolve(t.toLowerCase() + ".csv"));
            }
            System.out.println("done: " + total + " rows across " + tables.size() + " tables");
        }
        // embedded Derby wants an explicit shutdown; XJ015 is its "clean shutdown" SQLState
        try { DriverManager.getConnection("jdbc:derby:;shutdown=true"); }
        catch (java.sql.SQLException e) { if (!"XJ015".equals(e.getSQLState())) throw e; }
    }

    static long dumpTable(Connection c, String table, Path file) throws Exception {
        long rows = 0;
        try (Statement st = c.createStatement();
             ResultSet rs = st.executeQuery("select * from smart.\"" + table + "\"");
             BufferedWriter w = Files.newBufferedWriter(file, StandardCharsets.UTF_8)) {
            ResultSetMetaData m = rs.getMetaData();
            int n = m.getColumnCount();
            // Sidecar with the real column types so the CSV reader never has to
            // guess (sniffing coerces all-numeric VARCHAR ids like '000123').
            StringBuilder types = new StringBuilder("{");
            StringBuilder sb = new StringBuilder();
            for (int i = 1; i <= n; i++) {
                if (i > 1) { sb.append(','); types.append(", "); }
                String col = m.getColumnName(i).toLowerCase();
                sb.append(col);
                types.append('\'').append(col).append("': '").append(duckdbType(m.getColumnType(i))).append('\'');
            }
            types.append('}');
            Files.writeString(Path.of(file.toString().replaceFirst("\\.csv$", ".columns")), types.toString(), StandardCharsets.UTF_8);
            sb.append('\n');
            w.write(sb.toString());
            while (rs.next()) {
                sb.setLength(0);
                for (int i = 1; i <= n; i++) {
                    if (i > 1) sb.append(',');
                    writeValue(sb, rs, i, m.getColumnType(i));
                }
                sb.append('\n');
                w.write(sb.toString());
                rows++;
            }
        }
        System.out.printf("%-45s %8d rows%n", table, rows);
        return rows;
    }

    static String duckdbType(int jdbcType) {
        return switch (jdbcType) {
            case Types.INTEGER, Types.SMALLINT, Types.TINYINT, Types.BIGINT -> "BIGINT";
            case Types.DOUBLE, Types.FLOAT, Types.REAL, Types.DECIMAL, Types.NUMERIC -> "DOUBLE";
            case Types.BOOLEAN, Types.BIT -> "BOOLEAN";
            case Types.DATE -> "DATE";
            case Types.TIME -> "TIME";
            case Types.TIMESTAMP -> "TIMESTAMP";
            default -> "VARCHAR"; // strings, CLOBs, and hex-encoded binary
        };
    }

    static void writeValue(StringBuilder sb, ResultSet rs, int i, int type) throws Exception {
        switch (type) {
            case Types.BINARY, Types.VARBINARY, Types.LONGVARBINARY, Types.BLOB -> {
                byte[] b = rs.getBytes(i);
                if (b == null) return;
                sb.append('"');
                for (byte x : b) { sb.append(HEX[(x >> 4) & 0xf]).append(HEX[x & 0xf]); }
                sb.append('"');
            }
            default -> {
                String s = rs.getString(i);
                if (s == null) return;
                sb.append('"');
                for (int k = 0; k < s.length(); k++) {
                    char ch = s.charAt(k);
                    if (ch == '"') sb.append("\"\"");
                    else sb.append(ch);
                }
                sb.append('"');
            }
        }
    }
}
