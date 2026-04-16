from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import uuid
from pathlib import Path
from datetime import datetime
from pydantic import BaseModel

from ..models.database import get_db, SkillNode
from ..services.lightrag_client import LightRAGClient
from ..services.skill_tree_builder import SkillTreeBuilder

router = APIRouter(prefix="/api/documents", tags=["documents"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

lightrag_client = LightRAGClient()
skill_tree_builder = SkillTreeBuilder(lightrag_client)

class TextInsertRequest(BaseModel):
    text: str

class DocumentsRequest(BaseModel):
    page: int = 1
    page_size: int = 50
    status_filter: Optional[str] = None
    sort_field: str = "updated_at"
    sort_direction: str = "desc"

@router.post("/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        file_path = UPLOAD_DIR / file.filename
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        lightrag_result = await lightrag_client.upload_document(str(file_path))
        
        doc_id = lightrag_result.get("track_id", str(uuid.uuid4()))
        
        content_summary = f"已上传文档: {file.filename}"
        skills = await skill_tree_builder.build_skill_tree_from_document(doc_id, content_summary)
        
        for skill in skills:
            db_skill = SkillNode(
                id=skill["id"],
                name=skill["name"],
                description=skill["description"],
                parent_ids=skill["parent_ids"],
                doc_id=skill["doc_id"],
                status=skill["status"],
                mastery=skill["mastery"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(db_skill)
        
        db.commit()
        
        return {
            "status": "success",
            "doc_id": doc_id,
            "filename": file.filename,
            "skills_count": len(skills),
            "lightrag_result": lightrag_result
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/insert-text")
async def insert_text(request: TextInsertRequest, db: Session = Depends(get_db)):
    try:
        lightrag_result = await lightrag_client.insert_text(request.text)
        
        doc_id = lightrag_result.get("track_id", str(uuid.uuid4()))
        
        content_summary = request.text[:200] if len(request.text) > 200 else request.text
        skills = await skill_tree_builder.build_skill_tree_from_document(doc_id, content_summary)
        
        for skill in skills:
            db_skill = SkillNode(
                id=skill["id"],
                name=skill["name"],
                description=skill["description"],
                parent_ids=skill["parent_ids"],
                doc_id=skill["doc_id"],
                status=skill["status"],
                mastery=skill["mastery"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(db_skill)
        
        db.commit()
        
        return {
            "status": "success",
            "doc_id": doc_id,
            "skills_count": len(skills),
            "lightrag_result": lightrag_result
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
async def get_documents_list():
    try:
        result = await lightrag_client.get_documents()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/paginated")
async def get_documents_paginated(request: DocumentsRequest):
    try:
        result = await lightrag_client.get_documents_paginated(
            page=request.page,
            page_size=request.page_size,
            status_filter=request.status_filter,
            sort_field=request.sort_field,
            sort_direction=request.sort_direction
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pipeline-status")
async def get_pipeline_status():
    try:
        result = await lightrag_client.get_pipeline_status()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status-counts")
async def get_status_counts():
    try:
        result = await lightrag_client.get_document_status_counts()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/track/{track_id}")
async def get_track_status(track_id: str):
    try:
        result = await lightrag_client.get_track_status(track_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{doc_id}")
async def delete_document(doc_id: str, db: Session = Depends(get_db)):
    try:
        result = await lightrag_client.delete_document(doc_id)
        
        db.query(SkillNode).filter(SkillNode.doc_id == doc_id).delete()
        db.commit()
        
        return result
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{doc_id}/knowledge")
async def get_document_knowledge(doc_id: str, db: Session = Depends(get_db)):
    try:
        nodes = db.query(SkillNode).filter(SkillNode.doc_id == doc_id).all()
        
        return {
            "doc_id": doc_id,
            "knowledge_nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "description": node.description,
                    "status": node.status,
                    "mastery": node.mastery,
                    "parent_ids": node.parent_ids
                }
                for node in nodes
            ],
            "total_count": len(nodes)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
