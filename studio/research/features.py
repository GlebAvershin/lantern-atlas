def facts(m):
    return {"fresh_primary_succeeded": m["fresh_primary"]==200,
            "fresh_alternate_succeeded": m["fresh_alternate"]==200,
            "cached_read_succeeded": m["cached_primary"]==200}
