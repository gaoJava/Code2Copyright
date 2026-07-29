from __future__ import annotations

import fnmatch
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence, Union
from xml.sax.saxutils import escape


LINES_PER_PAGE = 60
SUPPORTED_EXTENSIONS = {
    ".py", ".pyw", ".java", ".kt", ".kts",
    ".vue", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh",
    ".go", ".sql", ".html", ".htm", ".css", ".scss", ".less",
    ".php", ".cs", ".rs", ".rb", ".swift", ".scala", ".sh",
    ".yaml", ".yml", ".xml", ".json", ".properties", ".gradle",
}
IGNORED_DIRECTORIES = {
    ".git", ".svn", ".hg", ".idea", ".vscode", "__pycache__",
    "node_modules", "venv", ".venv", "env", ".env", "build", "dist",
    "target", "out", "coverage", ".next", ".nuxt", ".cache", "vendor",
}
IGNORED_FILE_PATTERNS = {
    "*.min.js", "*.min.css", "*.map", "*.lock", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml",
}


@dataclass(frozen=True)
class SourceLine:
    number: int
    text: str
    file: str


@dataclass(frozen=True)
class ScanResult:
    root: Path
    files: tuple[Path, ...]
    lines: tuple[SourceLine, ...]


def _is_source_file(path: Path) -> bool:
    name = path.name.lower()
    return (
        path.suffix.lower() in SUPPORTED_EXTENSIONS
        and not any(fnmatch.fnmatch(name, pattern) for pattern in IGNORED_FILE_PATTERNS)
    )


PathLike = Union[str, Path]


def discover_files(root: PathLike, module_order: Optional[Sequence[str]] = None) -> list[Path]:
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("请选择有效的源码项目目录")

    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = sorted(
            d for d in dirs
            if d not in IGNORED_DIRECTORIES and not d.startswith(".")
        )
        current_path = Path(current)
        files.extend(
            current_path / name
            for name in sorted(names)
            if _is_source_file(current_path / name)
        )
    order = {name: index for index, name in enumerate(module_order or ())}

    def sort_key(path: Path):
        relative = path.relative_to(root)
        module = relative.parts[0] if len(relative.parts) > 1 else "."
        return (
            order.get(module, len(order)),
            relative.as_posix().lower(),
        )

    return sorted(files, key=sort_key)


def _read_text(path: Path) -> str:
    data = path.read_bytes()
    if b"\x00" in data:
        return ""
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")


def scan_project(
    root: PathLike, module_order: Optional[Sequence[str]] = None
) -> ScanResult:
    root_path = Path(root).expanduser().resolve()
    files = discover_files(root_path, module_order)
    output: list[SourceLine] = []
    line_no = 1
    for path in files:
        relative = path.relative_to(root_path).as_posix()
        text = _read_text(path)
        if not text:
            continue
        # 文件分隔行也计入连续行号，便于审查时定位源码来源。
        output.append(SourceLine(line_no, f"// ===== 文件：{relative} =====", relative))
        line_no += 1
        for raw_line in text.splitlines():
            output.append(SourceLine(line_no, raw_line.expandtabs(4), relative))
            line_no += 1
    return ScanResult(root_path, tuple(files), tuple(output))


def select_lines(lines: tuple[SourceLine, ...], mode: str) -> tuple[SourceLine, ...]:
    if mode == "all" or len(lines) <= 60 * LINES_PER_PAGE:
        return lines
    if mode != "first_last":
        raise ValueError("未知导出模式")
    count = 30 * LINES_PER_PAGE
    return lines[:count] + lines[-count:]


def _xml_text(value: str) -> str:
    # XML 1.0 不允许大多数控制字符。
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", value)
    return escape(cleaned)


def _paragraph(text: str, font_size: int = 15, bold: bool = False) -> str:
    bold_xml = "<w:b/>" if bold else ""
    return (
        "<w:p><w:pPr><w:spacing w:before=\"0\" w:after=\"0\" w:line=\"240\" "
        "w:lineRule=\"exact\"/></w:pPr><w:r><w:rPr>"
        f"{bold_xml}<w:rFonts w:ascii=\"Courier New\" w:hAnsi=\"Courier New\" "
        f"w:eastAsia=\"宋体\"/><w:sz w:val=\"{font_size}\"/>"
        f"</w:rPr><w:t xml:space=\"preserve\">{_xml_text(text)}</w:t></w:r></w:p>"
    )


def _source_row(line: Optional[SourceLine]) -> str:
    text = f"{line.number:06d}  {line.text}" if line is not None else " "
    # 固定行高 + 单元格禁止换行，避免 Word 因长源码行重排而破坏每页 60 行。
    return (
        '<w:tr><w:trPr><w:trHeight w:val="240" w:hRule="exact"/>'
        '<w:cantSplit/></w:trPr><w:tc><w:tcPr><w:tcW w:w="10466" w:type="dxa"/>'
        '<w:noWrap/><w:tcMar><w:top w:w="0" w:type="dxa"/>'
        '<w:left w:w="0" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/>'
        '<w:right w:w="0" w:type="dxa"/></w:tcMar></w:tcPr>'
        f'{_paragraph(text)}</w:tc></w:tr>'
    )


def _header_xml(title: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/>'
        '<w:rFonts w:eastAsia="宋体"/><w:sz w:val="18"/></w:rPr>'
        f'<w:t>{_xml_text(title)}</w:t></w:r></w:p></w:hdr>'
    )


def _footer_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>第 </w:t></w:r>'
        '<w:fldSimple w:instr=" PAGE "><w:r><w:t>1</w:t></w:r></w:fldSimple>'
        '<w:r><w:t> 页</w:t></w:r></w:p></w:ftr>'
    )


def _document_xml(lines: tuple[SourceLine, ...]) -> str:
    pages = [lines[i:i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)]
    if not pages:
        pages = [()]
    body: list[str] = []
    for page_index, page in enumerate(pages):
        rows = [_source_row(line) for line in page]
        rows.extend(_source_row(None) for _ in range(LINES_PER_PAGE - len(page)))
        body.append(
            '<w:tbl><w:tblPr><w:tblW w:w="10466" w:type="dxa"/>'
            '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="0" w:type="dxa"/>'
            '<w:left w:w="0" w:type="dxa"/><w:bottom w:w="0" w:type="dxa"/>'
            '<w:right w:w="0" w:type="dxa"/></w:tblCellMar></w:tblPr>'
            '<w:tblGrid><w:gridCol w:w="10466"/></w:tblGrid>'
            + "".join(rows) + '</w:tbl>'
        )
        if page_index < len(pages) - 1:
            body.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<w:body>' + "".join(body) +
        '<w:sectPr><w:headerReference w:type="default" r:id="rId1"/>'
        '<w:footerReference w:type="default" r:id="rId2"/>'
        '<w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" '
        'w:header="360" w:footer="360" w:gutter="0"/>'
        '</w:sectPr></w:body></w:document>'
    )


def export_docx(
    result: ScanResult,
    destination: PathLike,
    software_name: str,
    mode: str = "first_last",
) -> int:
    chosen = select_lines(result.lines, mode)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    title = f"{software_name.strip() or result.root.name} 源代码"

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
</Types>"""
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
    document_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>
</Relationships>"""

    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", content_types)
        docx.writestr("_rels/.rels", root_rels)
        docx.writestr("word/document.xml", _document_xml(chosen))
        docx.writestr("word/_rels/document.xml.rels", document_rels)
        docx.writestr("word/header1.xml", _header_xml(title))
        docx.writestr("word/footer1.xml", _footer_xml())
    return len(chosen)
