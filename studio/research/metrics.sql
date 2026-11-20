SELECT scenario,
       MAX(CASE WHEN probe='fresh_primary' THEN status END) AS fresh_primary,
       MAX(CASE WHEN probe='fresh_alternate' THEN status END) AS fresh_alternate,
       MAX(CASE WHEN probe='cached_primary' THEN status END) AS cached_primary
FROM samples GROUP BY scenario ORDER BY scenario
