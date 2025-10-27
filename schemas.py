from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class Document(BaseModel):
    title: str
    status: str = Field(default="draft", description="draft|sent|completed|declined")
    recipients: List[str] = []
    template_id: Optional[str] = None
    fields: dict = {}
    signatures: List[dict] = []  # each: { signer, signed_at, ip }
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Template(BaseModel):
    name: str
    description: Optional[str] = None
    fields: dict = {}
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Activity(BaseModel):
    type: str  # created|sent|signed|deleted|templated
    message: str
    ref_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
