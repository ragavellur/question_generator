from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class ContentType(str, Enum):
    definition = "definition"
    example = "example"
    derivation = "derivation"
    problem = "problem"
    summary = "summary"
    conceptual = "conceptual"


class DocumentProfile(BaseModel):
    front_matter_end_page: int | None = None
    back_matter_start_page: int | None = None
    first_content_page: int | None = None

    header: dict | None = None
    footer: dict | None = None

    chapter_pattern: str | None = None
    section_pattern: str | None = None
    subsection_pattern: str | None = None

    noise_patterns: list[dict] = Field(default_factory=list)
    figure_caption_pattern: str | None = None
    table_caption_pattern: str | None = None
    page_number_pattern: str | None = None

    keep_sections: list[str] = Field(default_factory=lambda: ["summary", "problems", "examples", "definitions"])
    has_outline: bool = False
    structure_type: str = "chapters"

    notes: str = ""


class Section(BaseModel):
    number: str
    title: str
    page_start: int
    page_end: int
    subsections: list[Section] = Field(default_factory=list)


class Chapter(BaseModel):
    number: str
    title: str
    page_start: int
    page_end: int
    sections: list[Section] = Field(default_factory=list)


class DocumentRecord(BaseModel):
    id: str
    name: str
    path: str
    total_pages: int
    processed: bool = False
    chunk_count: int = 0
    chapters: list[Chapter] = Field(default_factory=list)
    profile: DocumentProfile | None = None


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    doc_name: str
    chapter: str
    chapter_title: str = ""
    section: str = ""
    section_title: str = ""
    subsection: str = ""
    content: str
    page_start: int
    page_end: int
    token_count: int
    content_type: ContentType = ContentType.conceptual
    content_preview: str = ""
    embedding: list[float] | None = None


class QuestionConfig(BaseModel):
    doc_ids: list[str]
    chapter_numbers: list[str] | None = None
    section_numbers: list[str] | None = None
    chunk_ids: list[str] | None = None
    question_types: list[str] = Field(default_factory=lambda: ["mcq", "truefalse", "fib"])
    domains: list[str] = Field(default_factory=lambda: ["factual", "comprehension", "application"])
    difficulty: str | None = None
    count_per_type: int = 2


class Question(BaseModel):
    question_type: str
    domain: str
    difficulty: str = "medium"
    marks: int
    question_text: str
    options: list[str] | None = None
    answer: str
    source: str = ""


class QuestionResponse(BaseModel):
    questions: list[Question]


class UploadStatus(BaseModel):
    document_id: str
    status: str
    progress: int
    message: str
