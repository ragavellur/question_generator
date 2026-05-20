import re

from app.models.schemas import Chapter, Section


def detect_structure(outline: list[dict], total_pages: int, profile: dict) -> list[Chapter]:
    first_content_page = profile.get("first_content_page") or profile.get("front_matter_end_page") or 1
    back_matter_start_page = profile.get("back_matter_start_page")

    if outline and profile.get("has_outline"):
        return _from_outline(outline, first_content_page, back_matter_start_page, total_pages)
    return _from_patterns(total_pages, profile, first_content_page)


def _from_outline(
    outline: list[dict],
    first_content_page: int,
    back_matter_start_page: int | None,
    total_pages: int,
) -> list[Chapter]:
    relevant = [e for e in outline if e["page"] and e["page"] >= first_content_page]

    chapter_level = _detect_chapter_level(relevant)

    chapters: list[Chapter] = []
    current_chapter: Chapter | None = None
    current_section: Section | None = None
    content_index = 0

    for entry in relevant:
        title = entry["title"]
        page = entry["page"]
        level = entry.get("level", 1)

        if back_matter_start_page and page >= back_matter_start_page:
            break

        if level == chapter_level - 1:
            part_match = re.match(r"Part\s+\w+", title, re.IGNORECASE)
            if part_match:
                current_chapter = None
                current_section = None
                continue

        if level == chapter_level:
            content_index += 1
            current_chapter = Chapter(
                number=str(content_index),
                title=title,
                page_start=page,
                page_end=page,
                sections=[],
            )
            chapters.append(current_chapter)
            current_section = None

        elif level == chapter_level + 1 and current_chapter:
            current_section = Section(
                number=str(len(current_chapter.sections) + 1),
                title=title,
                page_start=page,
                page_end=page,
                subsections=[],
            )
            current_chapter.sections.append(current_section)

        elif level == chapter_level + 2 and current_section:
            sub = Section(
                number=f"{current_section.number}.{len(current_section.subsections) + 1}",
                title=title,
                page_start=page,
                page_end=page,
                subsections=[],
            )
            current_section.subsections.append(sub)

    for i, ch in enumerate(chapters):
        if i + 1 < len(chapters):
            ch.page_end = chapters[i + 1].page_start - 1
        else:
            ch.page_end = back_matter_start_page - 1 if back_matter_start_page else total_pages
        for j, sec in enumerate(ch.sections):
            if j + 1 < len(ch.sections):
                sec.page_end = ch.sections[j + 1].page_start - 1
            else:
                sec.page_end = ch.page_end
            for k, sub in enumerate(sec.subsections):
                if k + 1 < len(sec.subsections):
                    sub.page_end = sec.subsections[k + 1].page_start - 1
                else:
                    sub.page_end = sec.page_end

    return chapters


def _detect_chapter_level(entries: list[dict]) -> int:
    for e in entries:
        if re.match(r"Part\s+\w+", e.get("title", ""), re.IGNORECASE):
            return 2
    return 1


def _from_patterns(total_pages: int, profile: dict, first_content_page: int = 1) -> list[Chapter]:
    chapters = []
    ch_pattern = profile.get("chapter_pattern")
    if not ch_pattern:
        return chapters

    chapter = Chapter(
        number="1",
        title="Content",
        page_start=first_content_page,
        page_end=total_pages,
        sections=[],
    )
    chapters.append(chapter)
    return chapters
