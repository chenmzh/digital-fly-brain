#!/usr/bin/env python3
"""Validate the built stage2 report without rerunning or fitting models."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads((HERE/'report_build_manifest.json').read_text())
    assert sha(HERE/'report.pdf')==manifest['pdf_sha256'],'PDF hash changed'
    for name,digest in manifest['source_sha256'].items():assert sha(HERE/name)==digest,'Changed source '+name
    summary=json.loads((HERE/'stage_summary.json').read_text())
    for name,digest in summary['source_sha256'].items():assert sha(HERE/name)==digest,'Changed scientific summary source '+name
    frozen=json.loads((HERE/'analysis/cycle2/frozen_models.json').read_text())
    assert sha(HERE/'analysis/cycle2/prospective_predictions.csv')==frozen['prediction_sha256']
    report=json.loads((HERE/'analysis/cycle3/report.json').read_text())
    assert report['frozen_predictions_sha256']==frozen['prediction_sha256']
    assert summary['formal_new_windows']==201 and summary['raw_event_files_verified']==126
    assert sum(r['mae_screen'] for r in report['scores'] if r['surrogate']=='resource')==summary['resource_mae_pass_conditions']
    assert sum(r['mae_screen'] for r in report['scores'] if r['surrogate']=='accumulator')==summary['accumulator_mae_pass_conditions']
    log=(HERE/'.paper_build/report.log').read_text(errors='replace')
    forbidden=[r'Overfull \\[hv]box',r'Missing character:',r'There were undefined references',r'Citation .* undefined',r'Reference .* undefined',r'^!']
    for pattern in forbidden:assert not re.search(pattern,log,re.M),'LaTeX issue '+pattern
    console=(HERE/'.paper_build/compile-console.txt').read_text(errors='replace')
    assert "Can't begin an annotation" not in console and 'Tried to end an annotation' not in console
    info=subprocess.check_output(['pdfinfo',str(HERE/'report.pdf')],text=True)
    pages=int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1));assert 8<=pages<=20
    with tempfile.TemporaryDirectory(prefix='fly-stage2-pdf-') as temp:
        textfile=Path(temp)/'report.txt'
        subprocess.run(['pdftotext','-layout',str(HERE/'report.pdf'),str(textfile)],check=True)
        text=textfile.read_text();compact=re.sub(r'\s+','',text)
        for marker in ['三轮闭环','201','126','8.2','0.4','1.039','4.303','0.999','2.247','1.036','3.019','尚未执行','探索性']:
            assert marker in compact,'Missing PDF content '+marker
        assert '\ufffd' not in text,'Replacement glyph'
    fonts=subprocess.check_output(['pdffonts',str(HERE/'report.pdf')],text=True)
    font_rows=fonts.splitlines()[2:];assert font_rows
    for line in font_rows:assert line.split()[-5]=='yes','Unembedded font '+line
    for path in [HERE/'README.md',HERE/'REPORT.md',HERE/'LOOP_LOG.md']:
        for link in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if '://' not in link and not link.startswith('#'):assert (path.parent/link.split('#')[0]).exists(),'Broken link '+link
    result={'status':'passed','pages':pages,'pdf_sha256':sha(HERE/'report.pdf'),'pdf_bytes':(HERE/'report.pdf').stat().st_size,
            'embedded_font_count':len(font_rows),'content_and_numeric_checks':True,'source_and_frozen_prediction_hash_checks':True,
            'no_missing_glyphs_overfull_boxes_or_unresolved_references':True,
            'nonblocking_warnings':'Portable Tectonic Fontconfig compatibility and system-font path warnings; no system configuration modified.'}
    (HERE/'report_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
