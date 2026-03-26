from fastapi import APIRouter, HTTPException
from app.database import get_connection
from app.models import KeywordIn

router = APIRouter(prefix="/api")


@router.get("/keywords")
def list_keywords():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM keywords ORDER BY created_at DESC").fetchall()
    conn.close()
    return [{"id": r["id"], "keyword": r["keyword"],
             "category": r["category"], "created_at": r["created_at"]} for r in rows]


@router.post("/keywords")
def add_keyword(kw: KeywordIn):
    if not kw.keyword or len(kw.keyword) > 100:
        raise HTTPException(status_code=400, detail="Invalid keyword")
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO keywords (keyword, category, created_at) VALUES (?, ?, datetime('now'))",
            (kw.keyword, kw.category)
        )
        conn.commit()
        kw_id = cur.lastrowid
    except Exception:
        conn.close()
        raise HTTPException(status_code=409, detail="Keyword already exists")
    conn.close()
    return {"id": kw_id, "keyword": kw.keyword, "category": kw.category}


@router.delete("/keywords/{keyword_id}")
def delete_keyword(keyword_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM keywords WHERE id = ?", (keyword_id,))
    conn.commit()
    conn.close()
    return {"message": "deleted"}
