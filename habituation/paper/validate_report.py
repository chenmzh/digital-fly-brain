#!/usr/bin/env python3
"""Validate the delivered PDF, final TeX log, embedded fonts and provenance.

Requires Poppler's pdfinfo, pdftotext and pdffonts. Does not run a simulation.
Rendering/visual inspection is a separate step, not claimed by this script.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(*args):
    return subprocess.check_output(args, text=True)


def main():
    pdf = HERE / "report.pdf"
    build = json.loads((HERE / "build_manifest.json").read_text())
    assert sha(pdf) == build["pdf_sha256"], "PDF changed since build"
    for name, digest in build["source_sha256"].items():
        assert sha(HERE / name) == digest, f"Manuscript source changed: {name}"
    data = json.loads((HERE / "data_manifest.json").read_text())
    for name, digest in data["source_sha256"].items():
        assert sha(HERE.parent / name) == digest, f"Scientific input changed: {name}"
    for name, digest in data["generated_sha256"].items():
        assert sha(HERE / "data" / name) == digest, f"Derived data changed: {name}"
    log = (HERE / "_build/report.log").read_text()
    forbidden = [r"Overfull", r"Missing character", r"Undefined control sequence",
                 r"(?:Reference|Citation).*undefined", r"undefined references"]
    for pattern in forbidden:
        assert not re.search(pattern, log, re.I), f"Final TeX problem: {pattern}"
    console = (HERE / "_build/compile-console.txt").read_text()
    assert not re.search(r"annotation.*(?:pending|without starting)|special command.*failed", console, re.I)
    info = command("pdfinfo", str(pdf))
    pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    assert pages >= 10 and "A4" in info
    with tempfile.TemporaryDirectory(prefix="fly-report-validate-") as temp:
        path = Path(temp) / "text.txt"
        subprocess.run(["pdftotext", "-layout", str(pdf), str(path)], check=True)
        text = path.read_text()
    compact = re.sub(r"\s+", "", text).replace("％", "%")
    required = ["90.22%", "9.88%", "127,400", "14,687,178", "4,764", "280",
                "Englishabstract", "参考文献", "常见误读与阅读自检", "作者与单位待确认"]
    for token in required:
        assert token in compact, f"Missing PDF content: {token}"
    protocol = json.loads((HERE.parent / "analysis/report.json").read_text())["protocol_sha256"]
    assert protocol in compact, "Printed protocol hash does not match audited protocol"
    assert "??" not in text and "\ufffd" not in text
    assert len([p for p in text.split("\f") if p.strip()]) == pages
    fonts = command("pdffonts", str(pdf)).splitlines()[2:]
    assert fonts and all(row.split()[-5] == "yes" for row in fonts if row.strip()), "A font is not embedded"
    aux = (HERE / "_build/report.aux").read_text()
    bbl = (HERE / "_build/report.bbl").read_text()
    result = {
        "pdf": pdf.name, "pdf_sha256": sha(pdf), "pages": pages,
        "cjk_character_count_in_extracted_text": len(re.findall(r"[\u3400-\u9fff]", text)),
        "figures": len(re.findall(r"\\newlabel\{fig:", aux)),
        "tables": len(re.findall(r"\\newlabel\{tab:", aux)),
        "references": bbl.count("\\bibitem"),
        "checks": {"source_and_data_hashes": True, "all_fonts_embedded": True,
                   "text_extraction_and_key_numbers": True, "printed_protocol_hash": True,
                   "no_overfull_boxes_or_missing_characters": True, "no_unresolved_references": True,
                   "no_annotation_errors": True},
        "known_portability_note": "Tectonic reports system Noto CJK font paths; same named fonts are required on a new machine. Byte-identical PDFs are not promised.",
        "visual_review": "Not automated by this script. Inspect rendered figures and pages separately."
    }
    (HERE / "validation_report.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
