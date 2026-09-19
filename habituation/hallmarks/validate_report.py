#!/usr/bin/env python3
"""Check report hashes, numeric content, PDF text/fonts and local links."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
HERE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    manifest=json.loads((HERE/'report_build_manifest.json').read_text())
    assert sha(HERE/'report.pdf')==manifest['pdf_sha256']
    for name,digest in manifest['source_sha256'].items():assert sha(HERE/name)==digest,'Changed report source '+name
    summary=json.loads((HERE/'report_summary.json').read_text())
    for name,digest in summary['source_sha256'].items():assert sha(HERE/name)==digest,'Changed data/analysis source '+name
    r=json.loads((HERE/'analysis/final/report.json').read_text())
    assert r['analyzer_sha256']==sha(HERE/'analyze.py') and r['metrics_sha256']==sha(HERE/'metrics.py')
    assert r['actual_input_sequences_verified'] and summary['windows']==525 and summary['raw_event_files']==1026
    log=(HERE/'.paper_build/report.log').read_text(errors='replace')
    for pattern in [r'Overfull \\[hv]box',r'Missing character:',r'There were undefined references',r'Citation .* undefined',r'Reference .* undefined',r'^!']:
        assert not re.search(pattern,log,re.M),'LaTeX issue '+pattern
    console=(HERE/'.paper_build/compile-console.txt').read_text(errors='replace')
    assert "Can't begin an annotation" not in console and 'Tried to end an annotation' not in console
    info=subprocess.check_output(['pdfinfo',str(HERE/'report.pdf')],text=True)
    pages=int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1));assert 5<=pages<=15
    with tempfile.TemporaryDirectory(prefix='hallmark-pdf-') as temp:
        path=Path(temp)/'text.txt';subprocess.run(['pdftotext','-layout',str(HERE/'report.pdf'),str(path)],check=True)
        text=re.sub(r'\s+','',path.read_text())
        for x in ['部分恢复','525','1026','去习惯化','等时休息','H10','未测试','元可塑性']:assert x in text,'Missing content '+x
        assert '\ufffd' not in text
    fonts=subprocess.check_output(['pdffonts',str(HERE/'report.pdf')],text=True).splitlines()[2:]
    assert fonts and all(line.split()[-5]=='yes' for line in fonts),'Unembedded font'
    for p in [HERE/'REPORT.md',HERE/'README.md',HERE/'LAB_NOTES.md']:
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' not in link and not link.startswith('#'):assert (p.parent/link.split('#')[0]).exists(),'Broken link '+link
    result={'status':'passed','pages':pages,'pdf_sha256':sha(HERE/'report.pdf'),'pdf_bytes':(HERE/'report.pdf').stat().st_size,
            'fonts_embedded':len(fonts),'report_and_scientific_data_hashes_verified':True,'no_missing_glyphs_overfull_boxes_or_unresolved_references':True}
    (HERE/'report_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
