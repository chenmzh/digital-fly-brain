#!/usr/bin/env python3
"""Read-only scientific/source/PDF checks; writes this report's validation record."""
import csv
import hashlib
import json
import re
import statistics as st
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE=Path(__file__).resolve().parent
HAB=HERE.parent
ROOT=HAB.parent


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    data=json.loads((HERE/'data_manifest.json').read_text());build=json.loads((HERE/'build_manifest.json').read_text())
    for name,digest in data['sources_sha256'].items():assert sha(HAB/name)==digest,'Changed scientific source '+name
    for name,digest in data['generated_sha256'].items():assert sha(HERE/name)==digest,'Changed generated data '+name
    assert data['generator_sha256']==sha(HERE/'prepare_data.py')
    for name,digest in build['source_sha256'].items():assert sha(HERE/name)==digest,'Changed manuscript source '+name
    assert sha(HAB/'report.pdf')==build['pdf_sha256']
    old=json.loads((HERE/'preserved_sources.json').read_text())
    for name,digest in old['sha256'].items():assert sha(ROOT/name)==digest,'Changed historical artifact '+name
    with (HAB/'analysis/metrics_by_seed.csv').open() as f:metrics=list(csv.DictReader(f))
    d={t:st.mean(float(r['decrement_fraction'])*100 for r in metrics if r['model']=='std' and float(r['interval_ms'])==t) for t in [500,2000]}
    assert round(d[500],2)==90.22 and round(d[2000],2)==9.88
    summary=json.loads((HERE/'summary.json').read_text());assert summary['formal_observation_windows']==1006 and summary['raw_event_files_previously_audited']==1212
    assert len(summary['distinct_seed_identifiers'])==11 and summary['blank_windows']==6 and summary['new_simulations']==summary['new_fits']==0
    h=summary['hallmark_groups'];assert h['H3_partial']['supported']==3 and h['H5']['supported']==2 and h['H4b_qualified']['eligible']==3 and h['H4b_qualified']['supported']==0
    for key in ['H6','H8:neu_JON_F','H8:neu_JON_D_m']:assert h[key]['supported']==0
    log=(HERE/'.build/report.log').read_text(errors='replace')
    for pattern in [r'Overfull \\[hv]box',r'Missing character:',r'There were undefined references',r'Citation .* undefined',r'Reference .* undefined',r'^!']:
        assert not re.search(pattern,log,re.M),'LaTeX issue: '+pattern
    console=(HERE/'.build/console.txt').read_text(errors='replace');assert "Can't begin an annotation" not in console and 'Tried to end an annotation' not in console
    info=subprocess.check_output(['pdfinfo',str(HAB/'report.pdf')],text=True);pages=int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1));assert 15<=pages<=35 and pages!=40
    subprocess.run(['qpdf','--check',str(HAB/'report.pdf')],check=True,capture_output=True)
    outlines=json.loads(subprocess.check_output(['qpdf','--json','--json-key=outlines',str(HAB/'report.pdf')],text=True))['outlines']
    titles=[]
    def walk(items):
        for item in items:
            titles.append(item['title']);walk(item.get('kids',[]))
    walk(outlines);assert len(titles)>=25
    with tempfile.TemporaryDirectory(prefix='fly-synthesis-validation-') as temp:
        textpath=Path(temp)/'text.txt';boxpath=Path(temp)/'boxes.html'
        subprocess.run(['pdftotext','-layout',str(HAB/'report.pdf'),str(textpath)],check=True)
        raw=textpath.read_text();text=re.sub(r'\s+','',raw)
        for token in ['1006','1212','90.22','9.88','1.036','3.019','0.490','0.732','0.591','4.303','98.0','83.3','29.4','事后综合','资格','尚未稳健建立','拟合','回顾性','前瞻','不等于','参考文献']:
            assert token in text,'Missing numeric/narrative content '+token
        assert '\ufffd' not in text
        subprocess.run(['pdftotext','-bbox',str(HAB/'report.pdf'),str(boxpath)],check=True)
        tree=ET.parse(boxpath);ns={'x':'http://www.w3.org/1999/xhtml'};violations=[]
        for i,page in enumerate(tree.findall('.//x:page',ns),1):
            w=float(page.attrib['width']);height=float(page.attrib['height'])
            for word in page.findall('.//x:word',ns):
                x0,y0,x1,y1=[float(word.attrib[k]) for k in ['xMin','yMin','xMax','yMax']]
                if x0<20 or y0<15 or x1>w-20 or y1>height-15:violations.append((i,word.text))
        assert not violations,violations
    fonts=subprocess.check_output(['pdffonts',str(HAB/'report.pdf')],text=True).splitlines()[2:]
    assert fonts and all(line.split()[-5]=='yes' for line in fonts)
    for p in [HAB/'REPORT.md',HERE/'README.md',HERE/'EDITORIAL_PLAN.md']:
        for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
            if '://' not in link and not link.startswith('#'):assert (p.parent/link.split('#')[0]).exists(),'Broken link '+link
    result={'status':'passed','pages':pages,'pdf_sha256':sha(HAB/'report.pdf'),'pdf_bytes':(HAB/'report.pdf').stat().st_size,
            'historical_files_unchanged':len(old['sha256']),'source_files_verified':len(data['sources_sha256']),
            'formal_observation_windows':1006,'prior_raw_event_file_audits':1212,'distinct_seed_identifiers':11,'blank_windows':6,
            'new_simulations':0,'new_fits':0,'bookmark_count':len(titles),'fonts_embedded':len(fonts),
            'no_missing_glyphs_overfull_boxes_unresolved_references_or_page_overflow':True,
            'scientific_scope':'Synthesis and re-tabulation of previously audited evidence, not a new raw-event audit or biological validation.'}
    (HERE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
