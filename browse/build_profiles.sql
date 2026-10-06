-- Optional: SMART Profiles (the i2 plugin, i_* tables). Appended to
-- build_browser_data.sql in the same DuckDB session (it reuses the lbl and emp
-- temp tables) by `./smart-able browse`, only when the backup has Profiles data.

-- ------------------------------------------------------------ profiles.json
COPY (
  SELECT
    (SELECT list(struct_pack(u := t.uuid, k := t.keyid, ca := tca.id,
                             l := coalesce(lt.label, t.keyid),
                             ida := t.id_attribute_uuid))
     FROM 'parquet/i_entity_type.parquet' t
     LEFT JOIN 'parquet/conservation_area.parquet' tca ON tca.uuid = t.ca_uuid
     LEFT JOIN lbl lt ON lt.element_uuid = t.uuid) AS types,
    (SELECT list(struct_pack(
        u := en.uuid, ty := en.entity_type_uuid, ca := eca.id,
        n := coalesce(nm.v, '(unnamed)'),
        -- local time through SMART 7.x, UTC from 8.0 (the browser converts)
        created := strftime(en.date_created, '%Y-%m-%d %H:%M:%S'),
        cmt := left(coalesce(en.comment, ''), 300),
        vals := (SELECT list([coalesce(la.label, ''),
                   coalesce(lli.label, v.string_value,
                            CASE WHEN v.double_value IS NOT NULL
                                 THEN CAST(v.double_value AS VARCHAR) END,
                            ev.name, '')])
                 FROM 'parquet/i_entity_attribute_value.parquet' v
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
            ON nm.entity_uuid = en.uuid AND nm.attribute_uuid = ty2.id_attribute_uuid) AS entities,
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
