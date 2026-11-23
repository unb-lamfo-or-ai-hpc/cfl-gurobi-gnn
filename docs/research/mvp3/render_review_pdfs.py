"""Render the English scientific protocol and inspect every PDF page locally."""
import argparse,datetime as dt,hashlib,json,os,re,shutil,subprocess
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import pymupdf

def font(size,bold=False):
    name='arialbd.ttf' if bold else 'arial.ttf'
    candidates=[Path('C:/Windows/Fonts')/name,Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')]
    for p in candidates:
        if p.exists():return ImageFont.truetype(str(p),size)
    return ImageFont.load_default()

def diagrams(out):
    im=Image.new('RGB',(2200,1120),'white');d=ImageDraw.Draw(im)
    def box(x,y,w,h,title,lines):
        d.rounded_rectangle((x,y,x+w,y+h),20,fill='#eef4f6',outline='#265d70',width=4)
        d.text((x+24,y+18),title,font=font(36,True),fill='#183e50')
        for i,line in enumerate(lines):d.text((x+24,y+76+i*46),line,font=font(31),fill='#26343b')
    def arrow(points):
        d.line(points,fill='#5e7580',width=5);x,y=points[-1];d.polygon([(x,y),(x-13,y-23),(x+13,y-23)],fill='#5e7580')
    box(600,18,1000,145,'66 original CFL instances',['30 easy + 30 medium + 6 hard'])
    box(45,245,1000,205,'Root-relaxation feature run',['Original-variable vector + cut-pass provenance','Feature identity, numerical checks and cost'])
    box(1155,245,1000,205,'Independent incumbent run',['Feasible integer solution + attained gap','Binary labels, trajectory and quality tier'])
    arrow([(1100,163),(1100,205),(545,205),(545,245)]);arrow([(1100,163),(1100,205),(1655,205),(1655,245)])
    box(600,535,1000,200,'Learning on 60 easy/medium parents',['42 training / 9 validation / 9 held-out test','Equivalent-work serial1 / DDP4; policy freeze'])
    arrow([(545,450),(545,495),(850,495),(850,535)]);arrow([(1655,450),(1655,495),(1350,495),(1350,535)])
    box(600,835,1000,200,'Paired evaluation and C2/C3 analysis',['9 held-out easy/medium + 6 hard; B/R/G','45 cells: quality, target times, cost and reuse'])
    arrow([(1100,735),(1100,835)])
    im.save(out/'pipeline.png',optimize=True)
    im=Image.new('RGB',(2200,1050),'white');d=ImageDraw.Draw(im)
    start=dt.date(2026,11,23);end=dt.date(2027,3,18);left=360;right=2110
    def x(date):return left+(date-start).days/(end-start).days*(right-left)
    pause1=dt.date(2026,12,19);pause2=dt.date(2027,1,11)
    d.rectangle((x(pause1),130,x(pause2),930),fill='#f2e8da')
    d.text((x(pause1)+10,145),'Planned pause',font=font(27),fill='#75552a')
    windows=[('S1  Contract',[(dt.date(2026,11,24),dt.date(2026,12,18))]),('S2  Dataset',[(dt.date(2026,12,4),dt.date(2026,12,18)),(dt.date(2027,1,11),dt.date(2027,1,22))]),('S3  Learning',[(dt.date(2027,1,25),dt.date(2027,1,29))]),('S4  B/R/G',[(dt.date(2027,2,1),dt.date(2027,2,19))]),('S5  Analysis',[(dt.date(2027,2,22),dt.date(2027,3,5))]),('S6  Synthesis',[(dt.date(2027,3,8),dt.date(2027,3,18))])]
    for i,(label,parts) in enumerate(windows):
        y=245+i*107;d.text((35,y+9),label,font=font(36,True),fill='#183e50')
        d.line((left,y+75,right,y+75),fill='#d7e0e4',width=2)
        for a,b in parts:d.rounded_rectangle((x(a),y,x(b+dt.timedelta(days=1)),y+58),10,fill='#356b7d')
    for date,label in [(dt.date(2026,12,1),'Dec 2026'),(dt.date(2027,1,1),'Jan 2027'),(dt.date(2027,2,1),'Feb 2027'),(dt.date(2027,3,1),'Mar 2027')]:
        d.line((x(date),200,x(date),930),fill='#b6c5cc',width=2);d.text((x(date)+7,90),label,font=font(31),fill='#26343b')
    d.text((35,980),'Working windows; two concurrent jobs; computational releases follow accepted inputs.',font=font(30),fill='#52636b')
    im.save(out/'sprint-calendar.png',optimize=True)

def build(source,out):
    out.mkdir(parents=True,exist_ok=True);diagrams(out)
    text=source.read_text(encoding='utf-8')
    forbidden=['compatibility','migration','DGX','Slurm job 3917','PR #99','TR-01','TR-02']
    assert not any(x.casefold() in text.casefold() for x in forbidden),'transient operational content in protocol'
    assert text.count('$$')%2==0 and text.count('$$')>=20
    assert all(f'| S{i}.' in text for i in range(1,7))
    # Preserve complete caption + initial rows on the same page.
    space={'1':20,'2':10,'3':16,'4':15,'5':19,'6':15,'7':17,'8':16,'9':18,'10':24,'11':21,'12':15,'13':25,'14':22,'A.1':12,'D.1':16}
    def table_space(match):
        key=match[0].split('Table ',1)[1].split('. ',1)[0]
        return '\\Needspace{'+str(space.get(key,18))+'\\baselineskip}\n\n'+match[0]
    intermediate=re.sub(r'(?m)^(\*\*Table [^\n]+)$',table_space,text)
    intermediate=intermediate.replace('# References','\\Needspace{12\\baselineskip}\n\n# References')
    intermediate=intermediate.replace('# 1. Research context and objectives','\\clearpage\n\n# 1. Research context and objectives')
    (out/'protocol-pdf.md').write_text(intermediate,encoding='utf-8')
    header=r'''\usepackage{microtype}
\usepackage{needspace}
\usepackage{url}
\def\UrlBreaks{\do\/\do\-\do\_\do\.\do\?\do\&\do\=}
\usepackage{fancyhdr}
\setlength{\emergencystretch}{3em}
\setlength{\tabcolsep}{4pt}
\renewcommand{\arraystretch}{1.08}
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\small CFL-GNN MVP 3.0}
\fancyhead[R]{\small Research methodology}
\fancyfoot[C]{\thepage}
\setlength{\headheight}{14pt}
'''
    (out/'header.tex').write_text(header,encoding='utf-8')
    pandoc=os.environ.get('PANDOC') or shutil.which('pandoc') or 'C:/Program Files/Quarto/bin/tools/pandoc.exe'
    engine=os.environ.get('XELATEX') or shutil.which('xelatex') or str(Path.home()/'AppData/Roaming/TinyTeX/bin/windows/xelatex.exe')
    common=[pandoc,'--standalone','--from=markdown+tex_math_dollars+autolink_bare_uris','--resource-path='+str(out)+os.pathsep+str(source.parent),'--toc']
    pdf=out/'CFL-GNN-MVP3-Research-Protocol-EN-20261123-v2.pdf'
    tex=out/(pdf.stem+'.tex')
    command=common+[str(out/'protocol-pdf.md'),'--to=latex','--variable=mainfont:Times New Roman','--variable=sansfont:Arial','--variable=monofont:Consolas','--variable=mathfont:Cambria Math','--include-in-header='+str(out/'header.tex'),'--output='+str(tex)]
    run=subprocess.run(command,cwd=out,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
    if run.returncode:raise RuntimeError(run.stderr[-6000:])
    logs=[]
    for attempt in range(3):
        run=subprocess.run([engine,'-no-shell-escape','-interaction=nonstopmode','-halt-on-error',tex.name],cwd=out,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120)
        logs.append(run.stdout+'\n'+run.stderr)
        (out/'pdf-build.log').write_text('\n'.join(logs),encoding='utf-8')
        if run.returncode:raise RuntimeError(run.stdout[-6000:]+run.stderr[-1000:])
    run=subprocess.run(common+[str(source),'--to=html5','--embed-resources','--mathml','--output='+str(out/'CFL-GNN-MVP3-Research-Protocol-EN-20261123-v2.html')],cwd=out,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=90)
    (out/'html-build.log').write_text(run.stderr,encoding='utf-8');assert run.returncode==0
    doc=pymupdf.open(pdf);qa=out/'qa';qa.mkdir(exist_ok=True);texts=[];bounds=[]
    for i,page in enumerate(doc):
        texts.append(page.get_text());assert '\ufffd' not in texts[-1]
        page.get_pixmap(matrix=pymupdf.Matrix(.8,.8)).save(qa/f'page-{i+1:02}.png')
        for block in page.get_text('blocks'):
            if block[0]<20 or block[2]>page.rect.width-20:bounds.append({'page':i+1,'box':list(block[:4]),'text':block[4][:100]})
    (out/'pdf-text.txt').write_text('\n\n'.join(texts),encoding='utf-8')
    pages=[qa/f'page-{i+1:02}.png' for i in range(len(doc))]
    for part,idx in enumerate(range(0,len(pages),6),1):
        sheet=Image.new('RGB',(1560,1540),'#d7dfe3');draw=ImageDraw.Draw(sheet)
        for j,p in enumerate(pages[idx:idx+6]):
            thumb=Image.open(p).convert('RGB');thumb.thumbnail((500,730));x=(j%3)*520+10;y=(j//3)*770+28
            sheet.paste(thumb,(x,y));draw.text((x,y-24),f'Page {idx+j+1}',font=font(18),fill='black')
        sheet.save(qa/f'contact-{part:02}.png')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    r={'date':'2026-11-23','pages':len(doc),'display_math_blocks':text.count('$$')//2,'table_labels':len(re.findall(r'^\*\*Table ',text,re.M)),'language':'English','transient_operational_content_check':'PASS','text_margin_warnings':bounds,'visual_review':'pending','source_sha256':sha(source),'pdf_sha256':sha(pdf),'new_solver_calls':0,'new_training_calls':0,'HPC_calls':0}
    (out/'build-receipt.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path(__file__).with_name('coauthor-methodological-protocol.md'));p.add_argument('--output',type=Path,default=Path(__file__).parent);args=p.parse_args();build(args.source.resolve(),args.output.resolve())