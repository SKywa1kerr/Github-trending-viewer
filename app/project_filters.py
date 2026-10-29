"""Shared, parameterized filters for the library and saved projects."""


def build_project_filters(*, category=None, language=None, q=None, min_stars=0, prefix=""):
    conditions = []
    params = []
    if category:
        conditions.append(f"{prefix}category = ?")
        params.append(category)
    if language:
        conditions.append(f"{prefix}language = ?")
        params.append(language)
    if min_stars:
        conditions.append(f"{prefix}stars >= ?")
        params.append(min_stars)
    if q and q.strip():
        # Search user text literally, including percent signs and underscores.
        text = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        fields = ("repo_full_name", "description", "description_zh", "readme_summary_zh", "topics")
        conditions.append("(" + " OR ".join(
            f"{prefix}{field} LIKE ? ESCAPE '\\'" for field in fields
        ) + ")")
        params.extend([f"%{text}%"] * len(fields))
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    return where, params
