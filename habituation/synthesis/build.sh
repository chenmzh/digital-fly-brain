#!/usr/bin/env bash
# Rebuild the integrated manuscript from existing audited summaries only.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 prepare_data.py
mkdir -p .build
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$PWD/../paper/.cache}"
compiler="${TECTONIC_BIN:-$PWD/../paper/.tools/tectonic}"
"$compiler" --version > .build/compiler-version.txt
"$compiler" --untrusted --keep-logs --keep-intermediates --outdir .build report.tex 2>&1 | tee .build/console.txt
qpdf --check .build/report.pdf
cp .build/report.pdf ../report.pdf
python3 - <<'PY'
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
p=Path.cwd()
def sha(x):return hashlib.sha256(x.read_bytes()).hexdigest()
files=[p/x for x in ['report.tex','references.bib','prepare_data.py','build.sh','summary.json','data_manifest.json','EDITORIAL_PLAN.md']]+sorted((p/'sections').glob('*.tex'))+sorted((p/'data').iterdir())
manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'compiler':(p/'.build/compiler-version.txt').read_text().strip(),
          'source_sha256':{str(x.relative_to(p)):sha(x) for x in files},'pdf':'../report.pdf','pdf_sha256':sha(p.parent/'report.pdf'),'pdf_bytes':(p.parent/'report.pdf').stat().st_size}
(p/'build_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
PY
