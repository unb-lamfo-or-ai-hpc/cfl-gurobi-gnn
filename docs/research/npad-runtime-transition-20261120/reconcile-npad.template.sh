# NPAD: reconciliar metadados autorizados do Agrologistic, reparar pydantic e adicionar GNN.
# Nao altera pyproject/codigo; build editavel pode regenerar metadados do pacote.
# Execute uma vez em service0. Sem Gurobi/Torch imports, solves, treinamento ou Slurm.
# Se houver erro, preserve a saida/estagio. Nao repetir, remover claims ou limpar o env.
(
set -euo pipefail
test "$(id -un)" = __NPAD_USER__
case "$(hostname -s)" in service[0-9]*) ;; *) echo HOST_NPAD_NAO_CONFIRMADO; exit 1;; esac
umask 077
O=/home/__NPAD_USER__/venv313
T=/home/__NPAD_USER__/venv313_g14
G=/scratch/global/__NPAD_USER__
D="$G/cfl-mvp3-evidence"
P="$D/__PARENT_STAGE_BASENAME__"
test -x "$O/bin/python"
test -x "$T/bin/python"
test -d "$G"
test -w "$G"
for cmd in curl tar sha256sum timeout nice; do command -v "$cmd" >/dev/null; done
mkdir -p "$D"
S=$(mktemp -d "$D/npad-gnn-reconcile.XXXXXXXX")
printf 'NPAD_ETAPA=%s\nAMBIENTE_ALVO=%s\n' "$S" "$T"
mkdir "$S/tmp" "$S/cache" "$S/tool"
show_failure() {
  npad_install_rc=$?
  if test "$npad_install_rc" -ne 0; then
    printf 'NPAD_FALHA_PRESERVAR_ETAPA=%s\n' "$S"
    for log in metadata-refresh.log dependency-check-before.txt resolution.log installation.log dependency-check-after.txt; do
      if test -f "$S/$log"; then
        printf '\nLOG=%s\n' "$log"
        tail -n 15 "$S/$log"
      fi
    done
  fi
  return "$npad_install_rc"
}
trap show_failure EXIT
export TMPDIR="$S/tmp"
export XDG_CACHE_HOME="$S/cache"
export XDG_CONFIG_HOME="$S/config"
export UV_CACHE_DIR="$S/cache/uv"
export UV_NO_CONFIG=1
export UV_LINK_MODE=copy
export UV_PYTHON_DOWNLOADS=never
export UV_CONCURRENT_INSTALLS=1
export UV_CONCURRENT_DOWNLOADS=2
export UV_CONCURRENT_BUILDS=1
export UV_HTTP_RETRIES=0
export RAYON_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
export PIP_DISABLE_PIP_VERSION_CHECK=1
export NO_COLOR=1
inventory() {
  env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH "$1/bin/python" -I -B -c 'import importlib.metadata as m,json;print(json.dumps(sorted((d.metadata.get("Name",""),d.version) for d in m.distributions()),ensure_ascii=True,separators=(",",":")))'
}
inventory "$O" > "$S/original-before.json"
inventory "$T" > "$S/target-before-reconcile.json"
env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH "$T/bin/python" -I -B - "$S" "$D" "$P" <<'FREEZE'
import hashlib,json,shutil,sys
from pathlib import Path
from packaging.utils import canonicalize_name
s,d,parent=map(Path,sys.argv[1:])
assert sys.version_info[:3]==(3,13,15),'PYTHON_CHANGED_STOP'
assert Path(sys.prefix)==Path('/home/__NPAD_USER__/venv313_g14'),'PREFIX_MISMATCH'
values=json.loads((s/'original-before.json').read_text())
assert hashlib.sha256(json.dumps(values,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()=='94e163438088c2e35743c3858e35c60dbfd3b1c8fd05ec1b7ff6a54dce3bc750','ORIGINAL_INVENTORY_CHANGED_STOP'
values=json.loads((s/'target-before-reconcile.json').read_text())
pins={canonicalize_name(name):version for name,version in values}
assert len(pins)==len(values),'DUPLICATE_DISTRIBUTIONS_STOP'
assert pins.get('gurobipy')=='14.0.0' and pins.get('numpy')=='2.5.2' and pins.get('scipy')=='1.18.1','CORE_VERSIONS_CHANGED_STOP'
assert 'torch' not in pins and 'torch-geometric' not in pins,'GNN_ALREADY_PRESENT_STOP'
oldclaim=json.loads((d/'npad-gnn-additions-20261120.claim.json').read_text())
assert Path(oldclaim['stage'])==parent and oldclaim['target']==sys.prefix,'PARENT_CLAIM_MISMATCH'
assert not (parent/'installation.log').exists() and not (parent/'complete-additions.lock.txt').exists(),'PARENT_MAY_HAVE_REACHED_INSTALL_STOP'
report=(parent/'dependency-check-before.txt').read_text()
assert all(x in report for x in ('model-agrologistic','gurobipy','dash','pydantic')),'PARENT_DIAGNOSTIC_MISMATCH'
assert shutil.disk_usage(s).free>=30*1024**3,'SCRATCH_FREE_SPACE_BELOW_30GIB'
assert shutil.disk_usage(sys.prefix).free>=12*1024**3,'ENV_FILESYSTEM_FREE_SPACE_BELOW_12GIB'
with (d/'npad-gnn-reconcile-20261120.claim.json').open('x') as f:
    f.write(json.dumps({'scope':'author_requested_metadata_reconcile_pydantic_repair_and_GNN_additions','stage':str(s),'parent':str(parent),'target':sys.prefix,'original_venv313_untouched':True,'automatic_retry':False},indent=2)+'\n')
print('NPAD_INVENTARIO_ORIGINAL_E_TENTATIVA_ANTERIOR_CONFERIDOS')
FREEZE
A="$P/uv-0.13.9-x86_64-linux.tar.gz"
printf '%s  %s\n' a7fbaff2b9a271d85c1bdb540941090fd1ce011797b4abeb48e4dcd39c2471d5 "$A" | sha256sum -c -
tar --extract --gzip --file "$A" --directory "$S/tool" --no-same-owner
U="$S/tool/uv-x86_64-unknown-linux-gnu/uv"
test -x "$U"
run_uv() { env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH -u VIRTUAL_ENV -u CONDA_PREFIX "$U" --no-config "$@"; }
run_uv --version
cat > "$S/metadata_reconcile.py" <<'META'
import ast,hashlib,importlib.metadata as md,json,re,sys,tomllib
from pathlib import Path
from urllib.parse import unquote,urlparse
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name as canon
from packaging.version import Version
PROJECT=Path('/home/__NPAD_USER__/model-agrologistic')
NAME='model-agrologistic'

def source_info(project):
    raw=(project/'pyproject.toml').read_bytes()
    backup=project/'__AGRO_BACKUP_BASENAME__'
    prior=backup.read_bytes().decode('utf-8')
    authorized=''.join(re.sub(r'<\s*14(?![\d.])','<15',line) if 'gurobipy' in line.lower() else line for line in prior.splitlines(keepends=True))
    assert raw.decode('utf-8')==authorized,'SOURCE_DIFFERS_FROM_AUTHORIZED_G14_CHANGE'
    cfg=tomllib.loads(raw.decode('utf-8')); p=cfg['project']; build=cfg['build-system']
    assert canon(p['name'])==NAME and isinstance(p.get('version'),str),'PROJECT_IDENTITY_OR_DYNAMIC_VERSION_STOP'
    assert not any(x in p.get('dynamic',[]) for x in ('version','dependencies','optional-dependencies')),'DYNAMIC_METADATA_NOT_REVIEWED'
    assert Version('.'.join(map(str,sys.version_info[:3]))) in SpecifierSet(p.get('requires-python','')),'PROJECT_PYTHON_CONFLICT'
    assert build.get('build-backend')=='setuptools.build_meta' and not build.get('backend-path') and not cfg.get('tool',{}).get('setuptools',{}).get('cmdclass'),'UNREVIEWED_BUILD_BACKEND'
    for raw_req in build['requires']:
        req=Requirement(raw_req)
        assert not req.url and (req.marker is None or req.marker.evaluate()),'UNREVIEWED_BUILD_REQUIREMENT'
        assert Version(md.version(req.name)) in req.specifier,'BUILD_REQUIREMENT_NOT_PRESENT:'+req.name
    setup=project/'setup.py'
    if setup.is_file():
        tree=ast.parse(setup.read_text())
        allowed=all((isinstance(n,ast.ImportFrom) and n.module=='setuptools' and all(x.name in ('setup','find_packages','find_namespace_packages') and x.asname is None for x in n.names)) or (isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str)) or (isinstance(n,ast.Expr) and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name) and n.value.func.id=='setup' and not n.value.args and not n.value.keywords) for n in tree.body)
        assert allowed,'CUSTOM_SETUP_CODE_NOT_REVIEWED'
    groups=[p.get('dependencies',[])]+list(p.get('optional-dependencies',{}).values())
    gurobi=[str(Requirement(x)) for group in groups for x in group if canon(Requirement(x).name)=='gurobipy']
    assert gurobi and all(Version('14.0.0') in Requirement(x).specifier and Version('15.0.0') not in Requirement(x).specifier for x in gurobi),'SOURCE_GUROBI_RANGE_NOT_G14_APPROVED'
    return {'version':p['version'],'pyproject_sha256':hashlib.sha256(raw).hexdigest(),'backup_sha256':hashlib.sha256(backup.read_bytes()).hexdigest(),'gurobi_requirements':gurobi}

def dist_info():
    dist=md.distribution(NAME)
    direct=json.loads(dist.read_text('direct_url.json') or '{}')
    parsed=urlparse(direct.get('url',''))
    assert parsed.scheme=='file' and Path(unquote(parsed.path)).resolve()==PROJECT.resolve() and direct.get('dir_info',{}).get('editable') is True,'EDITABLE_PROJECT_LOCATION_MISMATCH'
    reqs=[str(Requirement(x)) for x in dist.requires or [] if canon(Requirement(x).name)=='gurobipy']
    return {'version':dist.version,'gurobi_requirements':reqs,'requires_dist':dist.requires or []}

def inspect(stage):
    source=source_info(PROJECT); before=dist_info()
    needs=before['version']!=source['version'] or not before['gurobi_requirements'] or any(Version('14.0.0') not in Requirement(x).specifier for x in before['gurobi_requirements'])
    info={'source':source,'installed_before':before,'metadata_refresh_needed':needs,'project':str(PROJECT)}
    (stage/'agro-metadata-before.json').write_text(json.dumps(info,indent=2)+'\n')
    (stage/'refresh-needed.txt').write_text('1\n' if needs else '0\n')
    print('NPAD_AGRO_METADATA_REFRESH_NEEDED='+str(needs))

def verify(stage):
    initial=json.loads((stage/'agro-metadata-before.json').read_text())
    source=source_info(PROJECT); after=dist_info()
    assert source==initial['source'],'SOURCE_CHANGED_DURING_METADATA_REFRESH'
    assert after['version']==source['version'] and after['gurobi_requirements'] and all(Version('14.0.0') in Requirement(x).specifier and Version('15.0.0') not in Requirement(x).specifier for x in after['gurobi_requirements']),'INSTALLED_AGRO_METADATA_STILL_INCOMPATIBLE'
    old={canon(n):v for n,v in json.loads((stage/'target-before-reconcile.json').read_text())}
    vals=sorted((d.metadata.get('Name',''),d.version) for d in md.distributions())
    current={canon(n):v for n,v in vals}
    assert len(current)==len(vals) and set(current)==set(old),'DISTRIBUTIONS_CHANGED_DURING_METADATA_REFRESH'
    assert all(current[n]==v for n,v in old.items() if n!=NAME),'OTHER_VERSIONS_CHANGED_DURING_METADATA_REFRESH'
    assert current.get('gurobipy')=='14.0.0','GUROBI_VERSION_CHANGED'
    pydantic=current.get('pydantic','2.13.4')
    assert Version(pydantic)>=Version('2.10') and Version(pydantic)<Version('3'),'EXISTING_PYDANTIC_VERSION_REQUIRES_SEPARATE_DECISION'
    info={'source':source,'installed_after':after,'pydantic_version_for_plan':pydantic,'project_metadata_version_before':old[NAME],'project_metadata_version_after':current[NAME],'existing_packages_to_preserve':len(current)}
    (stage/'agro-metadata-after.json').write_text(json.dumps(info,indent=2)+'\n')
    (stage/'target-before.json').write_text(json.dumps(vals,ensure_ascii=True,separators=(',',':'))+'\n')
    (stage/'existing.constraints.txt').write_text(''.join(n+'=='+v+'\n' for n,v in sorted(current.items())))
    print('NPAD_AGRO_METADATA_GUROBI14_OK')

def check_dependencies(stage,rc):
    text=(stage/'dependency-check-before.txt').read_text(errors='replace')
    if rc:
        tick=chr(96)
        issues=[line for line in text.splitlines() if line.startswith('The package '+tick)]
        pattern='The package '+tick+'dash'+tick+' requires '+tick+'pydantic[^'+tick+']*'+tick+", but it's not installed"
        assert rc==1 and len(issues)==1 and re.fullmatch(pattern,issues[0].rstrip('.')),'UNEXPECTED_BASE_DEPENDENCY_ISSUE_STOP'
    info=json.loads((stage/'agro-metadata-after.json').read_text())
    (stage/'pydantic-repair-needed.txt').write_text('1\n' if rc else '0\n')
    with (stage/'additions.in').open('a') as f:f.write('pydantic=='+info['pydantic_version_for_plan']+'\n')
    print('NPAD_PYDANTIC_PLAN_VERSION='+info['pydantic_version_for_plan'])

if __name__=='__main__':
    stage=Path(sys.argv[2]); action=sys.argv[1]
    if action=='inspect':inspect(stage)
    elif action=='verify':verify(stage)
    elif action=='check':check_dependencies(stage,int(sys.argv[3]))
    else:raise AssertionError('UNKNOWN_ACTION')
META
run_meta() {
  local npad_metadata_action="$1"
  shift
  env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH "$T/bin/python" -I -B "$S/metadata_reconcile.py" "$npad_metadata_action" "$S" "$@"
}
run_meta inspect
if test "$(cat "$S/refresh-needed.txt")" = 1; then
  printf 'NPAD_ATUALIZANDO_SOMENTE_METADADOS_EDITAVEIS_DO_AGROLOGISTIC\n'
  run_uv pip install --python "$T/bin/python" --no-deps --no-build-isolation --reinstall-package model-agrologistic --editable /home/__NPAD_USER__/model-agrologistic > "$S/metadata-refresh.log" 2>&1
fi
run_meta verify
inventory "$O" > "$S/original-after-metadata.json"
cmp -- "$S/original-before.json" "$S/original-after-metadata.json"
cat > "$S/additions.in" <<'REQ'
torch @ https://download-r2.pytorch.org/whl/cu118/torch-2.7.1%2Bcu118-cp313-cp313-manylinux_2_28_x86_64.whl#sha256=a3f02b2795165eaf6dfe18c963519049a45a9c588488795cebc5015dac77ab46
torch-geometric==2.7.0
pyarrow==24.0.0
scikit-learn==1.7.2
tqdm==4.67.3
REQ
if run_uv pip check --python "$T/bin/python" > "$S/dependency-check-before.txt" 2>&1; then
  base_check_rc=0
else
  base_check_rc=$?
fi
run_meta check "$base_check_rc"
printf 'NPAD_RESOLVENDO_DEPENDENCIAS_COM_AS_VERSOES_EXISTENTES_CONGELADAS\n'
timeout 1800 nice -n 10 env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH -u VIRTUAL_ENV -u CONDA_PREFIX "$U" --no-config pip compile "$S/additions.in" --constraint "$S/existing.constraints.txt" --python "$T/bin/python" --index-url https://pypi.org/simple --only-binary ':all:' --generate-hashes --output-file "$S/complete-additions.lock.txt" > "$S/resolution.log" 2>&1
cat > "$S/validate_plan.py" <<'PLAN'
import hashlib,json,sys
from pathlib import Path
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
s=Path(sys.argv[1])
def frozen(filename):
    vals=json.loads((s/filename).read_text())
    return {canonicalize_name(name):version for name,version in vals}
old=frozen('target-before.json')
expected=dict(old)
url='https://download-r2.pytorch.org/whl/cu118/torch-2.7.1%2Bcu118-cp313-cp313-manylinux_2_28_x86_64.whl'
raw=(s/'complete-additions.lock.txt').read_text()
assert 'a3f02b2795165eaf6dfe18c963519049a45a9c588488795cebc5015dac77ab46' in raw,'TORCH_DIGEST_NOT_LOCKED'
seen=set()
for line in raw.splitlines():
    if not line or line[0].isspace() or line.startswith('#'):continue
    line=line.rstrip().removesuffix('\\').rstrip()
    req=Requirement(line)
    name=canonicalize_name(req.name)
    assert name not in seen,'DUPLICATE_LOCK_ENTRY'
    seen.add(name)
    assert req.marker is None,'CONDITIONAL_LOCK_NOT_REVIEWED'
    if req.url:
        assert name=='torch' and req.url.split('#',1)[0]==url and name not in old,'UNEXPECTED_DIRECT_URL'
        version='2.7.1+cu118'
    else:
        specs=list(req.specifier)
        assert len(specs)==1 and specs[0].operator=='==' and '*' not in specs[0].version,'UNPINNED_ENTRY'
        version=specs[0].version
    assert name not in old or old[name]==version,'EXISTING_PACKAGE_WOULD_CHANGE:'+name
    expected[name]=version
for name,version in [('torch','2.7.1+cu118'),('torch-geometric','2.7.0'),('pyarrow','24.0.0'),('scikit-learn','1.7.2'),('tqdm','4.67.3'),('pydantic',json.loads((s/'agro-metadata-after.json').read_text())['pydantic_version_for_plan'])]:
    assert name in seen and expected[name]==version,'DIRECT_REQUIREMENT_NOT_LOCKED:'+name
plan={'scope':'add_only_after_authorized_project_metadata_refresh','target':'/home/__NPAD_USER__/venv313_g14','lock_sha256':hashlib.sha256((s/'complete-additions.lock.txt').read_bytes()).hexdigest(),'existing_count':len(old),'additions':{k:v for k,v in sorted(expected.items()) if k not in old},'expected_versions':expected,'new_solver_calls':0,'new_training_calls':0}
(s/'add-only-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
print('NPAD_PLANO_APENAS_ADICOES_OK')
print('PACOTES_A_ADICIONAR='+str(len(plan['additions'])))
PLAN
env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH "$T/bin/python" -I -B "$S/validate_plan.py" "$S"
inventory "$O" > "$S/original-before-install.json"
inventory "$T" > "$S/target-before-install.json"
cmp -- "$S/original-before.json" "$S/original-before-install.json"
cmp -- "$S/target-before.json" "$S/target-before-install.json"
RP=()
if test "$(cat "$S/pydantic-repair-needed.txt")" = 1; then RP=(--reinstall-package pydantic); fi
printf 'NPAD_INSTALANDO_GNN_E_REPARANDO_PYDANTIC_SE_NECESSARIO\n'
timeout 1800 nice -n 10 env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH -u VIRTUAL_ENV -u CONDA_PREFIX "$U" --no-config pip install --python "$T/bin/python" --index-url https://pypi.org/simple --only-binary ':all:' --require-hashes --no-deps "${RP[@]}" --requirement "$S/complete-additions.lock.txt" > "$S/installation.log" 2>&1
run_uv pip check --python "$T/bin/python" > "$S/dependency-check-after.txt" 2>&1
inventory "$O" > "$S/original-after.json"
inventory "$T" > "$S/target-after.json"
cmp -- "$S/original-before.json" "$S/original-after.json"
env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH "$T/bin/python" -I -B - "$S" <<'RECEIPT'
import hashlib,importlib.metadata as md,json,sys
from pathlib import Path
from packaging.utils import canonicalize_name
s=Path(sys.argv[1]); plan=json.loads((s/'add-only-plan.json').read_text())
values=json.loads((s/'target-after.json').read_text())
actual={canonicalize_name(name):version for name,version in values}
assert actual==plan['expected_versions'],'AFTER_INVENTORY_NOT_EXACT_PRESERVE_AND_STOP'
assert 'torch' not in sys.modules and 'gurobipy' not in sys.modules,'SCIENTIFIC_IMPORT_UNEXPECTED'
receipt={'scope':'metadata_reconcile_and_dependency_additions_not_GPU_solver_or_GNN_qualification','environment':sys.prefix,'python':sys.version.split()[0],'gurobipy':md.version('gurobipy'),'torch_distribution':md.version('torch'),'pyg_distribution':md.version('torch-geometric'),'numpy_preserved':md.version('numpy'),'scipy_preserved':md.version('scipy'),'original_venv313_inventory_preserved':True,'all_preexisting_non_project_versions_preserved':True,'pydantic':md.version('pydantic'),'agro_metadata_reconciliation':json.loads((s/'agro-metadata-after.json').read_text()),'added_packages':plan['additions'],'lock_sha256':plan['lock_sha256'],'target_inventory_sha256':hashlib.sha256(json.dumps(values,ensure_ascii=True,separators=(',',':')).encode()).hexdigest(),'torch_or_gurobi_imported':False,'GPU_initializations':0,'solver_calls':0,'training_calls':0,'Slurm_submissions':0}
f=s/'gnn-additions-receipt.json'; f.write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
print('NPAD_RECIBO_SHA256='+hashlib.sha256(f.read_bytes()).hexdigest())
print('NPAD_LOCK_SHA256='+plan['lock_sha256'])
RECEIPT
printf 'NPAD_ETAPA=%s\nAMBIENTE_ALVO=%s\n' "$S" "$T"
)
printf 'NPAD_GNN_RECONCILE_EXIT=%s\n' "$?"
