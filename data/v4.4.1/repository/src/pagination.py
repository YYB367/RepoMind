def page(rows, offset, limit):
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    return {"items": rows[offset:offset + limit], "total": len(rows), "offset": offset, "limit": limit}

def page_query(rows, params):
    raise NotImplementedError("Implement the query adapter")
