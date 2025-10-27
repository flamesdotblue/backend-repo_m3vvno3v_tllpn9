from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from bson import ObjectId
from datetime import datetime

from database import db, create_document, get_documents
from schemas import Document, Template, Activity

app = FastAPI(title="Sign Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def to_str_id(doc):
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id"))
    # isoformat timestamps
    for k in ("created_at", "updated_at"):
        if k in doc and isinstance(doc[k], datetime):
            doc[k] = doc[k].isoformat()
    # ensure nested signature times
    if "signatures" in doc:
        for s in doc["signatures"]:
            for k in ("signed_at",):
                if k in s and isinstance(s[k], datetime):
                    s[k] = s[k].isoformat()
    return doc


@app.get("/test")
async def test():
    # simple round trip query
    await db["health"].insert_one({"ok": True, "ts": datetime.utcnow()})
    doc = await db["health"].find_one(sort=[("ts", -1)])
    return {"status": "ok", "last": to_str_id(doc)}


# Templates
@app.post("/templates")
async def create_template(tpl: Template):
    saved = await create_document("template", tpl.model_dump())
    await create_document("activity", Activity(type="templated", message=f"Template '{tpl.name}' created").model_dump())
    return to_str_id(saved)


@app.get("/templates")
async def list_templates() -> List[dict]:
    docs = await get_documents("template", limit=100, sort=[("updated_at", -1)])
    return [to_str_id(d) for d in docs]


@app.post("/templates/{tpl_id}/instantiate")
async def instantiate_from_template(tpl_id: str, title: Optional[str] = None):
    tpl = await db["template"].find_one({"_id": ObjectId(tpl_id)})
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    title_final = title or f"Document from {tpl.get('name')}"
    doc = Document(
        title=title_final,
        status="draft",
        recipients=[],
        template_id=str(tpl.get("_id")),
        fields=tpl.get("fields", {}),
    )
    saved = await create_document("document", doc.model_dump())
    await create_document(
        "activity",
        Activity(type="created", message=f"Document '{title_final}' created from template", ref_id=str(saved.get("_id"))).model_dump(),
    )
    return to_str_id(saved)


# Documents
@app.post("/documents")
async def create_doc(doc: Document):
    saved = await create_document("document", doc.model_dump())
    await create_document("activity", Activity(type="created", message=f"Document '{doc.title}' created", ref_id=str(saved.get("_id"))).model_dump())
    return to_str_id(saved)


@app.get("/documents")
async def list_docs(status: Optional[str] = None) -> List[dict]:
    q = {"status": status} if status else {}
    docs = await get_documents("document", filter_dict=q, limit=200, sort=[("updated_at", -1)])
    return [to_str_id(d) for d in docs]


@app.get("/documents/{doc_id}")
async def get_doc(doc_id: str):
    doc = await db["document"].find_one({"_id": ObjectId(doc_id)})
    if not doc:
        raise HTTPException(404, "Not found")
    return to_str_id(doc)


@app.patch("/documents/{doc_id}")
async def update_doc(doc_id: str, payload: dict):
    payload["updated_at"] = datetime.utcnow()
    res = await db["document"].update_one({"_id": ObjectId(doc_id)}, {"$set": payload})
    if res.matched_count == 0:
        raise HTTPException(404, "Not found")
    doc = await db["document"].find_one({"_id": ObjectId(doc_id)})
    await create_document("activity", Activity(type="updated", message=f"Document updated", ref_id=doc_id).model_dump())
    return to_str_id(doc)


@app.delete("/documents/{doc_id}")
async def delete_doc(doc_id: str):
    doc = await db["document"].find_one({"_id": ObjectId(doc_id)})
    if not doc:
        raise HTTPException(404, "Not found")
    await db["document"].delete_one({"_id": ObjectId(doc_id)})
    await create_document("activity", Activity(type="deleted", message=f"Document '{doc.get('title')}' deleted", ref_id=doc_id).model_dump())
    return {"ok": True}


@app.post("/documents/{doc_id}/self-sign")
async def self_sign(doc_id: str):
    doc = await db["document"].find_one({"_id": ObjectId(doc_id)})
    if not doc:
        raise HTTPException(404, "Not found")
    sig = {"signer": "self", "signed_at": datetime.utcnow(), "ip": "127.0.0.1"}
    new_status = "completed"
    await db["document"].update_one(
        {"_id": ObjectId(doc_id)},
        {"$push": {"signatures": sig}, "$set": {"status": new_status, "updated_at": datetime.utcnow()}},
    )
    await create_document("activity", Activity(type="signed", message=f"Document '{doc.get('title')}' self-signed", ref_id=doc_id).model_dump())
    updated = await db["document"].find_one({"_id": ObjectId(doc_id)})
    return to_str_id(updated)


# Activities
@app.get("/activities")
async def list_activities(limit: int = 25):
    items = await get_documents("activity", limit=limit, sort=[("created_at", -1)])
    return [to_str_id(a) for a in items]


# Stats
@app.get("/stats")
async def stats():
    statuses = ["draft", "sent", "completed", "declined"]
    result = {}
    for s in statuses:
        result[s] = await db["document"].count_documents({"status": s})
    total = await db["document"].count_documents({})
    attention = await db["document"].count_documents({"status": {"$in": ["draft", "declined"]}})
    return {
        "total": total,
        "completed": result["completed"],
        "waiting": result["sent"],
        "attention": attention,
        "breakdown": result,
    }
