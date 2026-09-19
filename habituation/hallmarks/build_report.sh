#!/usr/bin/env bash
# Report generation only; no simulation and no fitting.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python make_report.py
mkdir -p .paper_build
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$PWD/../paper/.cache}"
compiler="${TECTONIC_BIN:-$PWD/../paper/.tools/tectonic}"
"$compiler" --version > .paper_build/compiler-version.txt
"$compiler" --untrusted --keep-logs --keep-intermediates --outdir .paper_build report.tex 2>&1 | tee .paper_build/compile-console.txt
cp .paper_build/report.pdf report.pdf
python3 - <<'PY'
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
p=Path.cwd()
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
files=[p/n for n in ['report.tex','references.bib','make_report.py','build_report.sh','report_summary.json','REPORT.md']]+sorted((p/'report_data').iterdir())
m={'built_utc':datetime.now(timezone.utc).isoformat(),'compiler':(p/'.paper_build/compiler-version.txt').read_text().strip(),
   'source_sha256':{str(f.relative_to(p)):sha(f) for f in files},'pdf_sha256':sha(p/'report.pdf'),'pdf_bytes':(p/'report.pdf').stat().st_size}
(p/'report_build_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
PY
