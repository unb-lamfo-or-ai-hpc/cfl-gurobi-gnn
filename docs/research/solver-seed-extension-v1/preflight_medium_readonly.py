"""Bounded original-file preflight. No solver, ML, scheduler or cache imports.

The author pastes this into tfm_env. Only a private metadata ZIP is created
in an existing evidence directory, outside PR89. No original file changes.
"""
import datetime as dt
import gzip
import hashlib
import importlib.metadata
import json
import math
import os
import re
import socket
import stat
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

PARENTS = tuple("CFL_medium_instance_"+str(i) for i in (5,6,9,13,20,26))
EXPECTED = {
    "CFL_medium_instance_13":"f219560e7ee07013152d4069af8585848e853d6d8bc213b248ba2ebcd0d8dde5",
    "CFL_medium_instance_26":"568bbff8df060b2de1df4d9bf3815d77e2e18ac73158fe676ba121182add70c8",
}
MIB=2**20
MAX_COMPRESSED=512*MIB
MAX_DECODED=512*MIB
MAX_LINE=MIB
MAX_VARIABLE_ID=2000000
SECONDS=300
NUMBER=r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
TERM=re.compile(r"\s*([+-]?)\s*(?:("+NUMBER+r")\s+)?x(\d+)\s*")
RELATION=re.compile(r"(<=|>=|=)\s*([+-]?"+NUMBER+r")\s*$")

def need(ok, code):
    if not ok:raise ValueError(code)

class Budget:
    def __init__(self, seconds=SECONDS):
        self.started=time.monotonic();self.seconds=seconds;self.hashed_bytes=0;self.decoded_bytes=0
    def tick(self):
        need(time.monotonic()-self.started<=self.seconds,"time_budget_exceeded")

def safe(path, data_root):
    path=Path(path);root=Path(data_root).resolve(strict=True)
    need(not path.is_symlink(),"symlink_leaf")
    path=path.resolve(strict=True)
    need(path!=root and path.is_relative_to(root),"outside_data_root")
    need(stat.S_ISREG(path.stat().st_mode),"regular_file_required")
    return path

def fingerprint(path):
    s=Path(path).stat();return (s.st_size,s.st_mtime_ns)

def digest(path,budget):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(MIB),b""):
            budget.tick();budget.hashed_bytes+=len(block)
            need(budget.hashed_bytes<=3*1024**3,"hash_byte_budget_exceeded")
            h.update(block)
    return h.hexdigest()

def summarize(stream,budget):
    """Syntax/size inventory, not feasibility or formulation certification."""
    seen=bytearray(MAX_VARIABLE_ID);domains=bytearray(MAX_VARIABLE_ID)
    section=None;row_open=False;ended=False;original_sense=None
    variables=binary=general=rows=matrix_terms=objective_terms=bounds_lines=decoded=0
    matrix_min=objective_min=math.inf;matrix_max=objective_max=0.0
    def mark(index):
        nonlocal variables
        need(index<MAX_VARIABLE_ID,"variable_index_budget")
        if not seen[index]:seen[index]=1;variables+=1
    for line_number in range(3000001):
        raw=stream.readline(MAX_LINE+1)
        if not raw:break
        need(len(raw)<=MAX_LINE,"line_size_budget")
        decoded+=len(raw);budget.decoded_bytes+=len(raw)
        need(decoded<=MAX_DECODED and budget.decoded_bytes<=3*1024**3,"decoded_byte_budget")
        if line_number%2048==0:budget.tick()
        s=raw.decode("utf-8").strip()
        if not s or s.startswith("\\"):continue
        if s in ("Maximize","Minimize","Subject To","Bounds","Binaries","Generals","End"):
            need(not row_open,"unclosed_linear_row")
            section=s
            if s in ("Maximize","Minimize"):original_sense=s.upper()
            if s=="End":ended=True
            continue
        need(not ended,"content_after_end")
        if section in ("Binaries","Generals"):
            for name in s.split():
                need(re.fullmatch(r"x\d+",name) is not None,"unsupported_domain_syntax")
                i=int(name[1:]);mark(i);bit=1 if section=="Binaries" else 2
                need(domains[i] in (0,bit),"inconsistent_domain_declaration")
                if not domains[i]:
                    domains[i]=bit
                    if bit==1:binary+=1
                    else:general+=1
            continue
        if section=="Bounds":
            bounds_lines+=1
            continue  # Count only; bounds are not independently validated here.
        relation=None
        if section=="Subject To":
            label=re.match(r"[A-Za-z_][A-Za-z_0-9]*:\s*",s)
            if label:
                need(not row_open,"overlapping_rows");rows+=1;row_open=True;s=s[label.end():]
                need(rows<=50000,"row_count_budget")
            need(row_open,"term_outside_row")
            relation=RELATION.search(s)
            if relation:s=s[:relation.start()].rstrip()
        elif section in ("Maximize","Minimize"):
            if ":" in s:s=s.split(":",1)[1].lstrip()
        else:raise ValueError("unsupported_lp_section")
        cursor=0
        while cursor<len(s):
            match=TERM.match(s,cursor);need(match is not None,"unsupported_linear_term")
            sign,coefficient,index=match.groups();need(cursor==0 or bool(sign),"missing_term_separator")
            value=float(coefficient or "1");need(math.isfinite(value),"nonfinite_coefficient")
            mark(int(index));value=abs(value)
            if section=="Subject To":
                if value:matrix_terms+=1;matrix_min=min(matrix_min,value);matrix_max=max(matrix_max,value)
                need(matrix_terms<=10000000,"matrix_term_budget")
            else:
                objective_terms+=1
                if value:objective_min=min(objective_min,value);objective_max=max(objective_max,value)
            cursor=match.end()
        if relation:row_open=False
    else:raise ValueError("line_count_budget")
    need(ended and not row_open and original_sense is not None,"incomplete_lp")
    return {"original_objective_sense":original_sense,"future_effective_objective_policy":"MINIMIZE_without_other_model_changes",
        "variables_observed":variables,"binary_variables_declared":binary,"general_integer_variables_declared":general,
        "continuous_variables_by_difference":variables-binary-general,"linear_rows_observed":rows,
        "linear_nonzero_terms_observed":matrix_terms,"objective_terms_observed":objective_terms,"bounds_lines_observed":bounds_lines,
        "min_abs_nonzero_matrix_coefficient":None if math.isinf(matrix_min) else matrix_min,"max_abs_matrix_coefficient":matrix_max,
        "min_abs_nonzero_objective_coefficient":None if math.isinf(objective_min) else objective_min,"max_abs_objective_coefficient":objective_max,
        "decoded_bytes":decoded,"bounds_or_feasibility_independently_validated":False,"gurobi_model_instantiated":False,
        "scope":"strict_linear_LP_text_inventory_not_solver_parser_or_semantic_recertification"}

def locate(data_root,parent):
    root=Path(data_root).resolve(strict=True);found=[]
    # Exactly two historical layouts, four filenames per parent; no tree scan.
    for relative in ("cfl-gurobi-gnn/data/raw/MILPBench/CFL","raw/MILPBench/CFL"):
        for suffix in (".lp.gz",".lp"):
            p=root/relative/"CFL_medium_instance/LP"/(parent+suffix)
            if p.exists() or p.is_symlink():
                q=safe(p,root)
                if q not in found:found.append(q)
    return found

def collect(data_root,output_dir,budget,context):
    root=Path(data_root).resolve(strict=True);output=Path(output_dir).resolve(strict=True)
    need(output.is_dir() and output.is_relative_to(root),"existing_output_directory_in_data_required")
    rows=[];private=[]
    for parent in PARENTS:
        row={"parent":parent,"expected_historical_sha256":EXPECTED.get(parent),"issues":[],"execution_admitted":False}
        try:
            budget.tick();candidates=locate(root,parent)
            private.append({"parent":parent,"candidate_paths":[str(p) for p in candidates]})
            if len(candidates)!=1:
                row["issues"].append("original_missing_in_two_layouts" if not candidates else "ambiguous_original_paths")
            else:
                path=candidates[0];before=fingerprint(path)
                need(before[0]<=MAX_COMPRESSED,"compressed_size_budget")
                h=digest(path,budget);row.update({"bytes":before[0],"sha256":h,
                    "historical_digest_match":None if parent not in EXPECTED else h==EXPECTED[parent]})
                if parent in EXPECTED and h!=EXPECTED[parent]:row["issues"].append("historical_original_digest_mismatch")
                else:
                    opener=gzip.open if path.suffix==".gz" else open
                    with opener(path,"rb") as stream:row["structure"]=summarize(stream,budget)
                need(fingerprint(path)==before and digest(path,budget)==h,"original_changed_during_preflight")
        except (ValueError,OSError,UnicodeError,EOFError) as error:
            code=str(error) if isinstance(error,ValueError) and re.fullmatch("[a-z_]+",str(error)) else type(error).__name__
            row["issues"].append(code)
        row["readonly_preflight_complete"]=bool("structure" in row and not row["issues"])
        rows.append(row)
    report={"protocol_id":"pr94_six_medium_readonly_preflight_v1","context":context,"finished_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
        "rows":rows,"historical_cache_inspection_reused":"M13_M26_old_roots_not_admitted_no_cache_rescan",
        "hash_bytes_read":budget.hashed_bytes,"decoded_bytes_processed":budget.decoded_bytes,
        "wall_seconds":time.monotonic()-budget.started,"limits":{"wall_seconds":SECONDS,"compressed_bytes_per_model":MAX_COMPRESSED,
            "decoded_bytes_per_model":MAX_DECODED,"max_variable_id":MAX_VARIABLE_ID},
        "optimization_calls_added":0,"training_calls_added":0,"inference_calls_added":0,"scheduler_mutations":0,
        "pr89_modified":False,"model_bytes_modified":False,"scientific_reporting_eligible":False,"execution_admitted":False,
        "private_paths_in_report":False,"absence_proven":False,"shared_host_CPU_IO_activity_is_not_zero_overhead":True}
    out=output/("pr94-preflight-six-medium-"+uuid.uuid4().hex+".private.zip")
    payload={"preflight.json":(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n").encode(),
        "input-paths.private.json":(json.dumps(private,sort_keys=True,indent=2)+"\n").encode()}
    manifest={"sha256":{k:hashlib.sha256(v).hexdigest() for k,v in payload.items()},"private_not_for_github":True}
    with zipfile.ZipFile(out,"x",compression=zipfile.ZIP_DEFLATED) as z:
        for name,raw in payload.items():z.writestr(name,raw)
        z.writestr("manifest.json",json.dumps(manifest,sort_keys=True,indent=2)+"\n")
    with zipfile.ZipFile(out) as z:
        need(all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in manifest["sha256"].items()),"archive_member_hash")
    return out,report

def main():
    import pwd
    import resource
    need(socket.gethostname().split(".")[0]=="dgx-dasci","host_mismatch")
    need(pwd.getpwuid(os.getuid()).pw_name=="vrcelestino","user_mismatch")
    need(os.environ.get("CONDA_DEFAULT_ENV")=="tfm_env","environment_mismatch")
    data=Path("/raid/vrcelestino/data").resolve(strict=True)
    evidence=data/"cfl-mvp2-evidence"
    need(evidence.is_dir(),"existing_evidence_directory_missing")
    priority=os.nice(19)  # Only this metadata process; never another job.
    soft,hard=resource.getrlimit(resource.RLIMIT_AS)
    limit=1024**3 if hard==resource.RLIM_INFINITY else min(1024**3,hard)
    if soft!=resource.RLIM_INFINITY:limit=min(limit,soft)
    resource.setrlimit(resource.RLIMIT_AS,(limit,hard))
    source=data/"cfl-mvp2-evidence/pr89/cpu12h-9ab7823c6886/source"
    head=subprocess.check_output(["git","-C",str(source),"rev-parse","HEAD"],text=True,timeout=15).strip()
    need(head=="9ab7823c6886d19e9ec865141a1cd35b3c3c16e5","pr89_source_identity_mismatch")
    versions={}
    for package in ("gurobipy","numpy","torch"):
        try:versions[package]=importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:versions[package]=None
    context={"host":"dgx-dasci","user":"vrcelestino","environment":"tfm_env","python":sys.version.split()[0],
        "package_metadata_versions":versions,"packages_imported_for_model_execution":False,"pr89_source_head_observed":head,
        "started_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"metadata_process_nice":priority,"own_address_space_limit_bytes":limit,
        "campaign_queue_not_queried_or_changed":True}
    out,report=collect(data,evidence,Budget(),context)
    print("ARQUIVO_HPC="+str(out));print("SHA256="+digest(out,Budget()))
    print("INSTANCIAS_LOCALIZADAS="+str(sum("sha256" in r for r in report["rows"])))
    print("PREFLIGHTS_LEITURA_COMPLETOS="+str(sum(r["readonly_preflight_complete"] for r in report["rows"])))
    print("PENDENCIAS="+str(sum(len(r["issues"]) for r in report["rows"])))
    print("OTIMIZACOES_NOVAS=0");print("BYTES_ZIP="+str(out.stat().st_size))

if __name__=="__main__":
    try:main()
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        raise SystemExit("PREFLIGHT_ABORTADO="+str(error)+"\nPreserve a saida e qualquer ZIP criado.")
