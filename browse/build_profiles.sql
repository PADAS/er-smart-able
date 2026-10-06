-- Optional: SMART Profiles (the i2 plugin, i_* tables). Appended to
-- build_browser_data.sql in the same DuckDB session (it reuses the lbl and emp
-- temp tables) by `./smart-able browse`, only when the backup has Profiles data.

-- ------------------------------------------------------------ profiles.json
-- A Profile (i_profile_config) is a configured tracker inside the plugin:
-- it owns entity types and record sources and carries the main-menu label a
-- SMART user sees (i_config_option 'mainmenu', per CA).
COPY (
  SELECT
    (SELECT list(struct_pack(u := p.uuid, k := p.keyid, ca := pca.id,
                             l := coalesce(lp.label, p.keyid),
                             menu := coalesce(co.value, lp.label, p.keyid)))
     FROM 'parquet/i_profile_config.parquet' p
     LEFT JOIN 'parquet/conservation_area.parquet' pca ON pca.uuid = p.ca_uuid
     LEFT JOIN lbl lp ON lp.element_uuid = p.uuid
     LEFT JOIN 'parquet/i_config_option.parquet' co ON co.ca_uuid = p.ca_uuid AND co.keyid = 'mainmenu') AS profiles,
    (SELECT list(struct_pack(u := t.uuid, k := t.keyid, ca := tca.id,
                             l := coalesce(lt.label, t.keyid),
                             ida := t.id_attribute_uuid,
                             pr := (SELECT first(pe.profile_uuid) FROM 'parquet/i_profile_entity_type.parquet' pe
                                    WHERE pe.entity_type_uuid = t.uuid),
                             -- the type's attributes in order: key, label, SMART type (TEXT, NUMERIC, DATE, LIST, POSITION, ...)
                             atts := (SELECT list(struct_pack(k := a.keyid, l := coalesce(la.label, a.keyid), t := trim(a.type))
                                                  ORDER BY ta.seq_order)
                                      FROM 'parquet/i_entity_type_attribute.parquet' ta
                                      JOIN 'parquet/i_attribute.parquet' a ON a.uuid = ta.attribute_uuid
                                      LEFT JOIN lbl la ON la.element_uuid = a.uuid
                                      WHERE ta.entity_type_uuid = t.uuid)))
     FROM 'parquet/i_entity_type.parquet' t
     LEFT JOIN 'parquet/conservation_area.parquet' tca ON tca.uuid = t.ca_uuid
     LEFT JOIN lbl lt ON lt.element_uuid = t.uuid) AS types,
    (SELECT list(struct_pack(
        u := en.uuid, ty := en.entity_type_uuid, ca := eca.id, pr := en.profile_uuid,
        n := coalesce(nm.v, '(unnamed)'),
        -- local time through SMART 7.x, UTC from 8.0 (the browser converts)
        created := strftime(en.date_created, '%Y-%m-%d %H:%M:%S'),
        cmt := left(coalesce(en.comment, ''), 300),
        -- position: a POSITION attribute (x in double_value, y in double_value2),
        -- else the entity's first i_location point
        x := coalesce(pos.x, loc.x), y := coalesce(pos.y, loc.y),
        -- [label, value, attribute key]
        vals := (SELECT list([coalesce(la.label, ''),
                   CASE WHEN a.type = 'POSITION' AND v.double_value IS NOT NULL
                        THEN printf('%.5f, %.5f', v.double_value2, v.double_value)
                        ELSE coalesce(lli.label, v.string_value,
                                      CASE WHEN v.double_value IS NOT NULL
                                           THEN CAST(v.double_value AS VARCHAR) END,
                                      ev.name, '') END,
                   a.keyid])
                 FROM 'parquet/i_entity_attribute_value.parquet' v
                 LEFT JOIN 'parquet/i_attribute.parquet' a ON a.uuid = v.attribute_uuid
                 LEFT JOIN lbl la  ON la.element_uuid  = v.attribute_uuid
                 LEFT JOIN lbl lli ON lli.element_uuid = v.list_item_uuid
                 LEFT JOIN emp ev  ON ev.uuid = v.employee_uuid
                 WHERE v.entity_uuid = en.uuid),
        recs := (SELECT list(er.record_uuid)
                 FROM 'parquet/i_entity_record.parquet' er
                 WHERE er.entity_uuid = en.uuid)))
     FROM 'parquet/i_entity.parquet' en
     LEFT JOIN 'parquet/conservation_area.parquet' eca ON eca.uuid = en.ca_uuid
     JOIN 'parquet/i_entity_type.parquet' ty2 ON ty2.uuid = en.entity_type_uuid
     LEFT JOIN (SELECT v.entity_uuid, v.attribute_uuid,
                       coalesce(v.string_value, li.label,
                                CAST(v.double_value AS VARCHAR)) AS v
                FROM 'parquet/i_entity_attribute_value.parquet' v
                LEFT JOIN lbl li ON li.element_uuid = v.list_item_uuid) nm
            ON nm.entity_uuid = en.uuid AND nm.attribute_uuid = ty2.id_attribute_uuid
     LEFT JOIN (SELECT v.entity_uuid, first(v.double_value) AS x, first(v.double_value2) AS y
                FROM 'parquet/i_entity_attribute_value.parquet' v
                JOIN 'parquet/i_attribute.parquet' a ON a.uuid = v.attribute_uuid
                WHERE a.type = 'POSITION' AND v.double_value IS NOT NULL AND v.double_value2 IS NOT NULL
                GROUP BY v.entity_uuid) pos ON pos.entity_uuid = en.uuid
     LEFT JOIN (SELECT el.entity_uuid,
                       first(ST_X(ST_GeomFromWKB(unhex(l.geometry)))) AS x,
                       first(ST_Y(ST_GeomFromWKB(unhex(l.geometry)))) AS y
                FROM 'parquet/i_entity_location.parquet' el
                JOIN 'parquet/i_location.parquet' l ON l.uuid = el.location_uuid
                WHERE l.geometry IS NOT NULL
                GROUP BY el.entity_uuid) loc ON loc.entity_uuid = en.uuid) AS entities,
    -- A record's attributes are defined per record source
    -- (i_recordsource_attribute -> i_attribute); values are text, number,
    -- or list items (i_record_attribute_value_list, several for is_multi).
    (SELECT list(struct_pack(
        u := r.uuid, ca := rca.id, title := coalesce(r.title, ''),
        d := strftime(r.primary_date, '%Y-%m-%d'),
        src := coalesce(ls.label, ''), status := coalesce(r.status, ''),
        descr := coalesce(r.description, ''),
        cmt := coalesce(r.comment, ''),
        created := strftime(r.date_created, '%Y-%m-%d %H:%M:%S'),
        by := coalesce(ec.name, ''),
        vals := (SELECT list([coalesce(la.label, a.keyid, ''),
                   coalesce(li.items, v.string_value,
                            CASE WHEN v.double_value IS NOT NULL THEN
                              CAST(v.double_value AS VARCHAR) ||
                              CASE WHEN v.double_value2 IS NOT NULL
                                   THEN ' – ' || CAST(v.double_value2 AS VARCHAR) ELSE '' END
                            END, '')] ORDER BY ra.seq_order)
                 FROM 'parquet/i_record_attribute_value.parquet' v
                 JOIN 'parquet/i_recordsource_attribute.parquet' ra ON ra.uuid = v.attribute_uuid
                 LEFT JOIN 'parquet/i_attribute.parquet' a ON a.uuid = ra.attribute_uuid
                 LEFT JOIN lbl la ON la.element_uuid = a.uuid
                 LEFT JOIN (SELECT vl.value_uuid, string_agg(coalesce(ll.label, ''), ', ') AS items
                            FROM 'parquet/i_record_attribute_value_list.parquet' vl
                            LEFT JOIN lbl ll ON ll.element_uuid = vl.element_uuid
                            GROUP BY vl.value_uuid) li ON li.value_uuid = v.uuid
                 WHERE v.record_uuid = r.uuid)))
     FROM 'parquet/i_record.parquet' r
     LEFT JOIN 'parquet/conservation_area.parquet' rca ON rca.uuid = r.ca_uuid
     LEFT JOIN lbl ls ON ls.element_uuid = r.source_uuid
     LEFT JOIN emp ec ON ec.uuid = r.created_by) AS records
) TO 'site/data/profiles.json' (FORMAT json, ARRAY true);

-- ------------------------------------------------ profile_attachments.json
-- k: 'ent' = profile entity attachment, 'rec' = profile record attachment.
COPY (
  SELECT 'ent' AS k, ea.entity_uuid AS id,
         'attachments/' || ia.ca_uuid || '/intelligence2/attachments/' || ia.filename AS p
  FROM 'parquet/i_entity_attachment.parquet' ea
  JOIN 'parquet/i_attachment.parquet' ia ON ia.uuid = ea.attachment_uuid
  UNION ALL
  SELECT 'rec', ra.record_uuid,
         'attachments/' || ia.ca_uuid || '/intelligence2/attachments/' || ia.filename
  FROM 'parquet/i_record_attachment.parquet' ra
  JOIN 'parquet/i_attachment.parquet' ia ON ia.uuid = ra.attachment_uuid
) TO 'site/data/profile_attachments.json' (FORMAT json, ARRAY true);
