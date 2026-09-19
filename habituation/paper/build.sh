#!/usr/bin/env bash
# Build derived manuscript material only. Never runs a neural simulation.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
python3 prepare_data.py
mkdir -p _build
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$PWD/.cache}"
if [[ -n "${TECTONIC_BIN:-}" ]]; then
  compiler="$TECTONIC_BIN"
elif [[ -x .tools/tectonic ]]; then
  compiler="$PWD/.tools/tectonic"
elif command -v tectonic >/dev/null 2>&1; then
  compiler="$(command -v tectonic)"
else
  printf '%s\n' 'Tectonic not found. Run: python3 setup_tex.py (local verified download), or set TECTONIC_BIN.' >&2
  exit 1
fi
"$compiler" --version > _build/compiler-version.txt
"$compiler" --untrusted --keep-logs --keep-intermediates --outdir _build report.tex 2>&1 | tee _build/compile-console.txt
cp _build/report.pdf report.pdf
python3 - <<'PY'
import hashlib,json
from pathlib import Path
from datetime import datetime,timezone
p=Path.cwd()
def sha(f): return hashlib.sha256(f.read_bytes()).hexdigest()
sources=[p/'report.tex',p/'references.bib',p/'prepare_data.py',p/'build.sh',p/'data_manifest.json']
sources+=sorted((p/'sections').glob('*.tex'))+sorted((p/'figures').glob('*.tex'))+sorted((p/'data').iterdir())
m={'built_utc':datetime.now(timezone.utc).isoformat(),
   'compiler':(p/'_build/compiler-version.txt').read_text().strip(),
   'source_sha256':{str(f.relative_to(p)):sha(f) for f in sources},
   'pdf_sha256':sha(p/'report.pdf'), 'pdf_bytes':(p/'report.pdf').stat().st_size,
   'scope':'Typesetting and data-derived plots; no new neural simulations.'}
(p/'build_manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
print('Built report.pdf; source and PDF hashes recorded in build_manifest.json.')
PY
