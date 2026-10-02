-- Builds the browser's JSON data files from the Parquet dump.
-- Run by `./smart-able browse` from the work directory (reads parquet/,
-- writes site/data/). build_profiles.sql is appended when Profiles exist.
INSTALL spatial; LOAD spatial;

-- ---- SMART 7.5 / 8.x compatibility --------------------------------------
-- Some columns exist only in some SMART versions. These views add the missing
-- ones as NULL (UNION ALL BY NAME with an empty row set), so the queries below
-- run unchanged against every supported version. See docs/smart-data-model.md.
CREATE TEMP VIEW patrol_v AS
  SELECT * FROM 'parquet/patrol.parquet'
  UNION ALL BY NAME
  SELECT NULL::VARCHAR AS patrol_type,       -- through 8.0: GROUND / MARINE / AIR code
         NULL::VARCHAR AS patrol_type_uuid   -- 8.1+: references patrol_type.uuid
  WHERE false;
CREATE TEMP VIEW patrol_type_v AS            -- 8.1+ gives patrol_type a uuid and keyid
  SELECT * FROM 'parquet/patrol_type.parquet'
  UNION ALL BY NAME
  SELECT NULL::VARCHAR AS uuid, NULL::VARCHAR AS keyid WHERE false;
CREATE TEMP VIEW obs_attr_v AS               -- 8.0+ adds geometry attribute columns
  SELECT * FROM 'parquet/wp_observation_attributes.parquet'
  UNION ALL BY NAME
  SELECT NULL::DOUBLE AS number_value_2, NULL::VARCHAR AS geom WHERE false;

-- Default-language display names for any named row (category, attribute,
-- list item, team, station, ...). arg_max prefers the CA's default language.
CREATE TEMP TABLE lbl AS
SELECT element_uuid, arg_max(value, is_def) AS label
FROM (
  SELECT l.element_uuid, l.value, CASE WHEN lg.isdefault THEN 1 ELSE 0 END AS is_def
  FROM 'parquet/i18n_label.parquet' l
  JOIN 'parquet/language.parquet' lg ON l.language_uuid = lg.uuid
) GROUP BY element_uuid;

CREATE TEMP VIEW emp AS
SELECT uuid, trim(coalesce(givenname,'') || ' ' || coalesce(familyname,'')) AS name
FROM 'parquet/employee.parquet';

-- waypoint -> patrol linkage
CREATE TEMP TABLE wp_patrol AS
SELECT pw.wp_uuid, pl.patrol_uuid, pld.uuid AS leg_day_uuid
FROM 'parquet/patrol_waypoint.parquet' pw
JOIN 'parquet/patrol_leg_day.parquet' pld ON pw.leg_day_uuid = pld.uuid
JOIN 'parquet/patrol_leg.parquet' pl ON pld.patrol_leg_uuid = pl.uuid;

-- ---------------------------------------------------------------- meta.json
COPY (
  SELECT
    strftime(now(), '%Y-%m-%d') AS generated,
    (SELECT max(version) FROM 'parquet/db_version.parquet'
      WHERE plugin_id = 'org.wcs.smart') AS db_version,
    (SELECT list(struct_pack(u := uuid, id := id, n := name))
       FROM 'parquet/conservation_area.parquet') AS cas,
    (SELECT count(*) FROM 'parquet/patrol.parquet') AS patrols,
    (SELECT count(*) FROM 'parquet/waypoint.parquet') AS waypoints,
    (SELECT count(*) FROM 'parquet/wp_observation.parquet') AS observations,
    (SELECT count(*) FROM 'parquet/employee.parquet') AS employees
) TO 'site/data/meta.json' (FORMAT json, ARRAY true);

-- ---------------------------------------------------------- categories.json
COPY (
  SELECT c.uuid AS u, c.ca_uuid AS ca, c.hkey AS k, c.parent_category_uuid AS p,
         coalesce(l.label, c.keyid) AS l, c.is_active AS act
  FROM 'parquet/dm_category.parquet' c
  LEFT JOIN lbl l ON l.element_uuid = c.uuid
  ORDER BY c.hkey
) TO 'site/data/categories.json' (FORMAT json, ARRAY true);

-- ------------------------------------------------------------- patrols.json
COPY (
  SELECT
    p.uuid AS u, p.id, ca.id AS ca,
    coalesce(p.patrol_type, lpt.label, pt.keyid, '') AS ty,
    coalesce(ltm.label, '') AS tm,
    coalesce(lst.label, '') AS st,
    strftime(p.start_date, '%Y-%m-%d') AS sd,
    strftime(p.end_date, '%Y-%m-%d') AS ed,
    p.is_armed AS armed,
    left(coalesce(p.objective, ''), 400) AS obj,
    coalesce(wc.n, 0) AS nwp,
    (SELECT list(struct_pack(
        id := leg.id,
        sd := strftime(leg.start_date, '%Y-%m-%d'),
        ed := strftime(leg.end_date, '%Y-%m-%d'),
        tr := coalesce(ltr.label, ''),
        md := coalesce(lmd.label, ''),
        members := (SELECT list(struct_pack(n := e.name, ldr := m.is_leader))
                    FROM 'parquet/patrol_leg_members.parquet' m
                    JOIN emp e ON e.uuid = m.employee_uuid
                    WHERE m.patrol_leg_uuid = leg.uuid),
        days := (SELECT list(struct_pack(
                     d := strftime(pld.patrol_day, '%Y-%m-%d'),
                     dist := round(coalesce(tk.dist, 0), 1)))
                 FROM 'parquet/patrol_leg_day.parquet' pld
                 LEFT JOIN (SELECT patrol_leg_day_uuid, sum(distance) AS dist
                            FROM 'parquet/track.parquet' GROUP BY 1) tk
                        ON tk.patrol_leg_day_uuid = pld.uuid
                 WHERE pld.patrol_leg_uuid = leg.uuid)))
     FROM 'parquet/patrol_leg.parquet' leg
     LEFT JOIN lbl ltr ON ltr.element_uuid = leg.transport_uuid
     LEFT JOIN lbl lmd ON lmd.element_uuid = leg.mandate_uuid
     WHERE leg.patrol_uuid = p.uuid) AS legs
  FROM patrol_v p
  LEFT JOIN patrol_type_v pt ON pt.uuid = p.patrol_type_uuid
  LEFT JOIN lbl lpt ON lpt.element_uuid = pt.uuid
  JOIN 'parquet/conservation_area.parquet' ca ON ca.uuid = p.ca_uuid
  LEFT JOIN lbl ltm ON ltm.element_uuid = p.team_uuid
  LEFT JOIN lbl lst ON lst.element_uuid = p.station_uuid
  LEFT JOIN (SELECT patrol_uuid, count(*) AS n FROM wp_patrol GROUP BY 1) wc
         ON wc.patrol_uuid = p.uuid
  ORDER BY p.start_date DESC
) TO 'site/data/patrols.json' (FORMAT json, ARRAY true);

-- ----------------------------------------------------------- waypoints.json
COPY (
  SELECT w.uuid AS u, wp.patrol_uuid AS p, ca.id AS ca,
         round(w.x, 6) AS x, round(w.y, 6) AS y,
         strftime(w.datetime, '%Y-%m-%d %H:%M') AS t,
         coalesce(oc.n, 0) AS n
  FROM 'parquet/waypoint.parquet' w
  JOIN 'parquet/conservation_area.parquet' ca ON ca.uuid = w.ca_uuid
  LEFT JOIN wp_patrol wp ON wp.wp_uuid = w.uuid
  LEFT JOIN (SELECT g.wp_uuid, count(*) AS n
             FROM 'parquet/wp_observation.parquet' o
             JOIN 'parquet/wp_observation_group.parquet' g ON o.wp_group_uuid = g.uuid
             GROUP BY 1) oc ON oc.wp_uuid = w.uuid
  ORDER BY w.datetime
) TO 'site/data/waypoints.json' (FORMAT json, ARRAY true);

-- -------------------------------------------------------- observations.json
COPY (
  SELECT g.wp_uuid AS w, o.category_uuid AS c, coalesce(e.name, '') AS e,
         (SELECT list([coalesce(la.label, ''),
                 CASE da.att_type
                   -- 8.0+ geometry attributes: number_value = length or perimeter (km),
                   -- number_value_2 = area (km²); string_value is how it was drawn
                   WHEN 'POLYGON' THEN 'Polygon: ' ||
                        coalesce(printf('%.3f km² area, ', a.number_value_2), '') ||
                        coalesce(printf('%.3f km perimeter', a.number_value), 'no measurements')
                   WHEN 'LINE' THEN 'Line: ' ||
                        coalesce(printf('%.3f km', a.number_value), 'no length')
                   WHEN 'BOOLEAN' THEN CASE WHEN a.number_value IS NULL THEN ''
                                            WHEN a.number_value <> 0 THEN 'Yes' ELSE 'No' END
                   ELSE coalesce(lli.label, ltn.label, a.string_value,
                                 CASE WHEN a.number_value IS NOT NULL
                                      THEN CAST(a.number_value AS VARCHAR) END, '')
                 END])
          FROM obs_attr_v a
          LEFT JOIN 'parquet/dm_attribute.parquet' da ON da.uuid = a.attribute_uuid
          LEFT JOIN lbl la  ON la.element_uuid  = a.attribute_uuid
          LEFT JOIN lbl lli ON lli.element_uuid = a.list_element_uuid
          LEFT JOIN lbl ltn ON ltn.element_uuid = a.tree_node_uuid
          WHERE a.observation_uuid = o.uuid) AS a
  FROM 'parquet/wp_observation.parquet' o
  JOIN 'parquet/wp_observation_group.parquet' g ON o.wp_group_uuid = g.uuid
  LEFT JOIN emp e ON e.uuid = o.employee_uuid
) TO 'site/data/observations.json' (FORMAT json, ARRAY true);

-- ---------------------------------------------------------- boundaries.json
COPY (
  SELECT area_type AS ty, keyid AS k, ca.id AS ca,
         ST_AsGeoJSON(ST_Simplify(ST_GeomFromWKB(unhex(geom)),
           CASE area_type WHEN 'ADMIN' THEN 0.0005 ELSE 0.002 END)) AS g
  FROM 'parquet/area_geometries.parquet' a
  JOIN 'parquet/conservation_area.parquet' ca ON ca.uuid = a.ca_uuid
  WHERE area_type IN ('CA', 'ADMIN', 'MNGT')
) TO 'site/data/boundaries.json' (FORMAT json, ARRAY true);

-- -------------------------------------------------------------- tracks.json
COPY (
  SELECT wp.patrol_uuid AS p,
         list(ST_AsGeoJSON(ST_Simplify(ST_GeomFromWKB(unhex(t.geometry)), 0.0001))) AS g
  FROM 'parquet/track.parquet' t
  JOIN (SELECT DISTINCT patrol_uuid, leg_day_uuid FROM wp_patrol) wp
    ON wp.leg_day_uuid = t.patrol_leg_day_uuid
  GROUP BY 1
) TO 'site/data/tracks.json' (FORMAT json, ARRAY true);

-- --------------------------------------------------------- attachments.json
-- Paths point into site/attachments/, the decrypted mirror of the filestore.
-- k: 'wp' = waypoint photo (Profiles attachments: see build_profiles.sql).
COPY (
  SELECT 'wp' AS k, a.wp_uuid AS id,
         'attachments/' || w.ca_uuid || '/patrol/' || wp.patrol_uuid || '/' || a.filename AS p
  FROM 'parquet/wp_attachments.parquet' a
  JOIN 'parquet/waypoint.parquet' w ON w.uuid = a.wp_uuid
  JOIN wp_patrol wp ON wp.wp_uuid = a.wp_uuid
) TO 'site/data/attachments.json' (FORMAT json, ARRAY true);

-- ----------------------------------------------------------- employees.json
COPY (
  SELECT e.name AS n, emp2.id, coalesce(lag.label, '') AS agency,
         coalesce(lrk.label, '') AS rank,
         strftime(emp2.startemploymentdate, '%Y-%m-%d') AS sd,
         strftime(emp2.endemploymentdate, '%Y-%m-%d') AS ed
  FROM emp e
  JOIN 'parquet/employee.parquet' emp2 ON emp2.uuid = e.uuid
  LEFT JOIN lbl lag ON lag.element_uuid = emp2.agency_uuid
  LEFT JOIN lbl lrk ON lrk.element_uuid = emp2.rank_uuid
  ORDER BY e.name
) TO 'site/data/employees.json' (FORMAT json, ARRAY true);
