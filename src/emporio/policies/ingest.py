import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

import pypdfium2 as pdfium

from emporio.config import get_settings

SECTION_RE = re.compile(r"^(\d{1,2})\.\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][^:]{2,70})$")
SUBSECTION_RE = re.compile(r"^(\d{1,2}\.\d{1,2})\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ].{2,90})$")

_PAGE_RE = re.compile(r"^Página\s+\d+$", re.IGNORECASE)
_HEADER = "Empório da Música Manual de Políticas e Procedimentos"
_LIST_MARKER_RE = re.compile(r"^(•|-|\d{1,2}\.\s)")


@dataclass
class PolicyChunk:
    id: str
    section: str
    title: str
    text: str


def extract_lines(pdf_path: Path) -> list[str]:
    pdf = pdfium.PdfDocument(str(pdf_path))
    lines: list[str] = []
    for page in pdf:
        textpage = page.get_textpage()
        text = textpage.get_text_range()
        for raw in text.splitlines():
            line = " ".join(raw.split())
            if not line:
                continue
            if _PAGE_RE.match(line):
                continue
            if line == _HEADER:
                continue
            lines.append(line)
    return lines


def _append_line(buffer: list[str], line: str) -> None:
    # Junta quebras artificiais do PDF: uma linha continua a anterior, exceto
    # quando é um marcador de lista ou a anterior termina com dois-pontos.
    if (
        buffer
        and not _LIST_MARKER_RE.match(line)
        and not buffer[-1].rstrip().endswith(":")
    ):
        buffer[-1] = f"{buffer[-1]} {line}"
    else:
        buffer.append(line)


def _finalize(chunk_id: str, section: str, title: str, buffer: list[str]) -> PolicyChunk | None:
    text = "\n".join(buffer).strip()
    if not text:
        return None
    return PolicyChunk(id=chunk_id, section=section, title=title, text=text)


def split_sections(lines: list[str]) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []

    current_id = "0"
    current_title = "Capa"
    current_section = "Capa"
    current_section_title = ""
    buffer: list[str] = []

    for line in lines:
        section_match = SECTION_RE.match(line)
        subsection_match = SUBSECTION_RE.match(line)

        if section_match:
            finalized = _finalize(current_id, current_section, current_title, buffer)
            if finalized is not None:
                chunks.append(finalized)
            buffer = []
            current_id = section_match.group(1)
            current_title = line
            current_section_title = line
            current_section = line
        elif subsection_match:
            finalized = _finalize(current_id, current_section, current_title, buffer)
            if finalized is not None:
                chunks.append(finalized)
            buffer = []
            current_id = subsection_match.group(1)
            current_title = line
            parent = current_section_title or line
            current_section = f"{parent} > {line}" if current_section_title else line
        else:
            _append_line(buffer, line)

    finalized = _finalize(current_id, current_section, current_title, buffer)
    if finalized is not None:
        chunks.append(finalized)

    return chunks


def build(pdf_path: Path | None = None, out_path: Path | None = None) -> list[PolicyChunk]:
    settings = get_settings()
    pdf_path = pdf_path or (settings.raw_dir / "politicas_da_loja.pdf")
    out_path = out_path or settings.policies_json

    lines = extract_lines(pdf_path)
    chunks = split_sections(lines)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps([asdict(chunk) for chunk in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return chunks


def main() -> None:
    chunks = build()
    print(f"Trechos extraídos: {len(chunks)}")
    for chunk in chunks:
        print(f"[{chunk.id}] {chunk.section}")


if __name__ == "__main__":
    main()
