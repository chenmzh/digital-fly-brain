#!/usr/bin/env bash
# Rebuild report tables/typesetting only; never launch neural simulations.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python make_report.py
mkdir -p .paper_build
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$PWD/../paper/.cache}"
compiler="${TECTONIC_BIN:-$PWD/../paper/.tools/tectonic}"
if [[ ! -x "$compiler" ]]; then
  printf '%s\n' 'Run python3 habituation/paper/setup_tex.py from project root, or set TECTONIC_BIN.' >&2
  exit 1
fi
"$compiler" --version > .paper_build/compiler-version.txt
"$compiler" --untrusted --keep-logs --keep-intermediates --outdir .paper_build report.tex 2>&1 | tee .paper_build/compile-console.txt
cp .paper_build/report.pdf report.pdf
python3 - <<'PY'
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
p=Path.cwd()
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
sources=[p/f for f in ['report.tex','figures.tex','references.bib','make_report.py','build_report.sh','stage_summary.json','REPORT.md']]+sorted((p/'report_data').iterdir())
m={'built_utc':datetime.now(timezone.utc).isoformat(),'compiler':(p/'.paper_build/compiler-version.txt').read_text().strip(),
   'source_sha256':{str(f.relative_to(p)):sha(f) for f in sources},'pdf_sha256':sha(p/'report.pdf'),'pdf_bytes':(p/'report.pdf').stat().st_size,
   'scope':'Stage2 report; figures and scores derived from audited results; no new neural simulations.'}
(p/'report_build_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
PY
