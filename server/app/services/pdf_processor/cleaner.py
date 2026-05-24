import re


def clean_pages(pages: list[dict], profile: dict) -> list[dict]:
    front_matter_end = profile.get("front_matter_end_page") or profile.get("first_content_page")
    back_matter_start = profile.get("back_matter_start_page")

    start_idx = front_matter_end if front_matter_end else 0
    end_idx = back_matter_start - 1 if back_matter_start else len(pages)

    relevant_pages = pages[start_idx:end_idx]
    cleaned = []

    for page in relevant_pages:
        text = page["text"]
        text = _remove_headers_footers(text, profile)
        text = _remove_noise_patterns(text, profile)
        text = _remove_figure_captions(text, profile)
        text = _remove_page_numbers(text, profile)
        text = _collapse_whitespace(text)

        cleaned.append({
            "page_num": page["page_num"],
            "text": text.strip(),
            "original_char_count": page["char_count"],
            "cleaned_char_count": len(text.strip()),
        })

    return cleaned


def _remove_headers_footers(text: str, profile: dict) -> str:
    lines = text.split("\n")
    header = profile.get("header", {})
    footer = profile.get("footer", {})

    header_lines = header.get("lines_to_remove", 0)
    if header_lines > 0:
        for i in range(min(header_lines, len(lines))):
            pattern = header.get("odd_page_pattern") or header.get("even_page_pattern")
            if pattern and re.match(pattern, lines[i].strip()):
                lines[i] = ""
            elif not pattern:
                lines[i] = ""

    if footer.get("lines_to_remove"):
        remove_count = footer["lines_to_remove"]
        for i in range(max(0, len(lines) - remove_count), len(lines)):
            pattern = footer.get("pattern")
            if pattern and re.match(pattern, lines[i].strip()):
                lines[i] = ""
            elif not pattern:
                lines[i] = ""

    return "\n".join(lines)


def _remove_noise_patterns(text: str, profile: dict) -> str:
    for item in profile.get("noise_patterns", []):
        pattern = item.get("pattern")
        if pattern:
            try:
                text = re.sub(pattern, "", text)
            except re.error:
                pass
    return text


def _remove_figure_captions(text: str, profile: dict) -> str:
    patterns = []
    fig = profile.get("figure_caption_pattern")
    if fig:
        patterns.append(fig)
    tbl = profile.get("table_caption_pattern")
    if tbl:
        patterns.append(tbl)

    for pattern in patterns:
        try:
            text = re.sub(pattern, "", text)
        except re.error:
            pass
    return text


def _remove_page_numbers(text: str, profile: dict) -> str:
    pattern = profile.get("page_number_pattern")
    if pattern:
        try:
            text = re.sub(pattern, "", text)
        except re.error:
            pass

    lines = text.split("\n")
    filtered = [line for line in lines if not re.match(r"^\s*\d+\s*$", line.strip()) and line.strip()]
    return "\n".join(filtered)


def _collapse_whitespace(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()
