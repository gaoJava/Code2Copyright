import tempfile
import unittest
import zipfile
from pathlib import Path

from generator import LINES_PER_PAGE, export_docx, scan_project, select_lines


class GeneratorTests(unittest.TestCase):
    def test_scan_filters_and_numbers_continuously(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "node_modules").mkdir()
            (root / "src" / "main.py").write_text("print('a')\nprint('b')\n", encoding="utf-8")
            (root / "src" / "web.vue").write_text("<template />\n", encoding="utf-8")
            (root / "node_modules" / "bad.js").write_text("ignored", encoding="utf-8")
            result = scan_project(root)
            self.assertEqual(len(result.files), 2)
            self.assertEqual([line.number for line in result.lines], list(range(1, 6)))
            self.assertFalse(any("bad.js" in line.file for line in result.lines))

    def test_first_last_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "big.py").write_text("\n".join(f"x={i}" for i in range(4000)), encoding="utf-8")
            result = scan_project(root)
            selected = select_lines(result.lines, "first_last")
            self.assertEqual(LINES_PER_PAGE, 60)
            self.assertEqual(len(selected), 60 * LINES_PER_PAGE)
            self.assertEqual(selected[0].number, 1)
            self.assertEqual(selected[-1].number, len(result.lines))

    def test_custom_module_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "frontend").mkdir()
            (root / "backend").mkdir()
            (root / "frontend" / "app.js").write_text("frontend()", encoding="utf-8")
            (root / "backend" / "app.py").write_text("backend()", encoding="utf-8")
            result = scan_project(root, ["backend", "frontend"])
            relative_files = [
                path.relative_to(result.root).as_posix() for path in result.files
            ]
            self.assertEqual(relative_files, ["backend/app.py", "frontend/app.js"])

    def test_export_is_valid_docx_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "project"
            root.mkdir()
            (root / "main.go").write_text("package main\nfunc main() {}\n", encoding="utf-8")
            result = scan_project(root)
            output = Path(tmp) / "source.docx"
            exported = export_docx(result, output, "示例软件", "all")
            self.assertEqual(exported, 3)
            with zipfile.ZipFile(output) as archive:
                self.assertIn("word/document.xml", archive.namelist())
                self.assertIn("示例软件".encode("utf-8"), archive.read("word/header1.xml"))
                document = archive.read("word/document.xml")
                self.assertIn(b'<w:sz w:val="15"/>', document)
                self.assertNotIn(b"{font_size}", document)


if __name__ == "__main__":
    unittest.main()
