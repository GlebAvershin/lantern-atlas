def facts(m):
    return {"http_success": m["status"] == 200, "returned_cached_review": bool(m["cache_hit"]),
            "returned_backup_model": bool(m["alternate"])}
