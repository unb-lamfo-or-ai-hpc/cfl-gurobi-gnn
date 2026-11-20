# NPAD: um teste tecnico de runtime, uma V100. Sem treino, modelo neural ou solver.
# Execute uma vez em service0. Se falhar, preserve os arquivos e nao repita.
(
set -euo pipefail
test "$(id -un)" = __NPAD_USER__
case "$(hostname -s)" in service[0-9]*) ;; *) echo HOST_NPAD_NAO_CONFIRMADO; exit 1;; esac
umask 077
S=/scratch/global/__NPAD_USER__/cfl-mvp3-evidence/__INSTALL_STAGE_BASENAME__
R=/scratch/global/__NPAD_USER__/cfl-mvp3-evidence/__INSTALL_STAGE_BASENAME__/runtime-gpu-qualification
T=/home/__NPAD_USER__/venv313_g14
test ! -e "$R"
printf '%s  %s\n' 8dfbedf6e5d26d7d6c9a019cde6ffab051c8c06c008b9dcfbdd1598579c2cca0 "$S/gnn-additions-receipt.json" 0d8e6d33abd340611f5452000f64fe707061880adbc823297c5125d5ab6a514e "$S/complete-additions.lock.txt" | sha256sum -c -
env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH "$T/bin/python" -I -B - "$S" <<'ADMIT'
import hashlib,importlib.metadata as md,json,sys
from pathlib import Path
s=Path(sys.argv[1]);r=json.loads((s/'gnn-additions-receipt.json').read_text())
assert sys.version_info[:3]==(3,13,15) and sys.prefix=='/home/__NPAD_USER__/venv313_g14','RUNTIME_IDENTITY_CHANGED'
values=sorted((d.metadata.get('Name',''),d.version) for d in md.distributions())
actual=hashlib.sha256(json.dumps(values,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()
assert actual==r['target_inventory_sha256']=='dafe3bf6020249096a4b8f31574b7a192cb3f3d45175f893e916aedd605dd82d','INSTALLED_INVENTORY_CHANGED'
assert r['original_venv313_inventory_preserved'] and r['all_preexisting_non_project_versions_preserved'],'INSTALLATION_QUALIFICATION_MISSING'
assert r['solver_calls']==r['training_calls']==r['Slurm_submissions']==0,'UNEXPECTED_PREVIOUS_SCIENTIFIC_ACTIVITY'
print('NPAD_INSTALACAO_CONFERIDA_PARA_TESTE_TECNICO_GPU')
ADMIT
mkdir "$R" "$R/tmp" "$R/cache"
cat > "$R/check_runtime.py" <<'WORKER'
import datetime as dt,hashlib,importlib.metadata as md,json,os,socket,sys
from pathlib import Path
r=Path(sys.argv[1]);s=r.parent
result={'scope':'single_GPU_library_runtime_and_synthetic_serialization_only','cluster':'ufrn','job_id':os.environ['SLURM_JOB_ID'],'host':socket.gethostname(),'started_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'python':sys.version.split()[0],'compatibility':'FAIL','gpu_requested':1,'solver_calls':0,'license_initializations':0,'training_calls':0,'neural_forwards':0,'optimizer_steps':0,'real_instances_loaded':0,'historical_checkpoints_loaded':0}
try:
    assert sys.version_info[:3]==(3,13,15) and sys.prefix=='/home/__NPAD_USER__/venv313_g14','RUNTIME_IDENTITY_CHANGED'
    assert os.environ['SLURM_JOB_PARTITION']=='gpu-8-v100' and os.environ['SLURM_NTASKS']=='1','ALLOCATION_SCOPE_MISMATCH'
    assert os.environ.get('SLURM_RESTART_COUNT','0')=='0','REQUEUED_JOB_NOT_AUTHORIZED'
    values=sorted((d.metadata.get('Name',''),d.version) for d in md.distributions())
    inventory=hashlib.sha256(json.dumps(values,ensure_ascii=True,separators=(',',':')).encode()).hexdigest()
    assert inventory=='dafe3bf6020249096a4b8f31574b7a192cb3f3d45175f893e916aedd605dd82d','QUEUED_ENVIRONMENT_CHANGED'
    assert hashlib.sha256((s/'gnn-additions-receipt.json').read_bytes()).hexdigest()=='8dfbedf6e5d26d7d6c9a019cde6ffab051c8c06c008b9dcfbdd1598579c2cca0','INSTALLATION_RECEIPT_CHANGED'
    result.update(inventory_sha256=inventory,cpu_affinity_logical=sorted(os.sched_getaffinity(0)),slurm_cpus_per_task=os.environ.get('SLURM_CPUS_PER_TASK'),gurobipy_distribution=md.version('gurobipy'))
    import numpy as np
    import pyarrow
    import sklearn
    import torch
    torch.set_num_threads(1)
    import torch_geometric
    from torch_geometric.data import HeteroData
    from torch_geometric.utils import scatter
    result.update(numpy=np.__version__,pyarrow=pyarrow.__version__,sklearn=sklearn.__version__,torch=torch.__version__,pyg=torch_geometric.__version__,torch_cuda_build=torch.version.cuda,cuda_available=torch.cuda.is_available())
    assert torch.__version__=='2.7.1+cu118' and torch_geometric.__version__=='2.7.0','IMPORT_VERSION_MISMATCH'
    assert torch.cuda.is_available() and torch.cuda.device_count()==1,'ONE_ALLOCATED_CUDA_DEVICE_REQUIRED_NO_CPU_FALLBACK'
    props=torch.cuda.get_device_properties(0)
    result.update(gpu_name=props.name,gpu_memory_bytes=props.total_memory,gpu_compute_capability=[props.major,props.minor],compiled_cuda_architectures=torch.cuda.get_arch_list())
    assert 'V100' in props.name,'GPU_FAMILY_CHANGED'
    array=np.array([1.,2.,3.,4.],dtype=np.float32)
    data=torch.from_numpy(array).to('cuda:0')
    index=torch.tensor([0,1,0,1],device='cuda:0')
    total=scatter(data,index,dim=0,dim_size=2,reduce='sum')
    torch.cuda.synchronize()
    assert total.is_cuda and np.array_equal(total.cpu().numpy(),np.array([4.,6.],dtype=np.float32)),'SYNTHETIC_CUDA_NUMPY_SCATTER_MISMATCH'
    graph=HeteroData()
    graph['variable'].x=torch.arange(12,dtype=torch.float32).reshape(4,3)
    graph['constraint'].x=torch.tensor([[1.],[2.]])
    edge=('variable','to','constraint')
    graph[edge].edge_index=torch.tensor([[0,1,2,3],[0,0,1,1]])
    fixture=r/'own-synthetic-heterodata.private.pt'
    torch.save(graph,fixture)
    loaded=torch.load(fixture,map_location='cpu',weights_only=False)
    assert torch.equal(loaded['variable'].x,graph['variable'].x) and torch.equal(loaded[edge].edge_index,graph[edge].edge_index),'OWN_SERIALIZATION_MISMATCH'
    loaded=loaded.to('cuda:0')
    assert loaded['variable'].x.is_cuda and loaded[edge].edge_index.is_cuda,'HETERODATA_TRANSFER_MISMATCH'
    torch.cuda.synchronize()
    result.update(compatibility='PASS',synthetic_cuda_scatter=True,numpy_torch_bridge=True,own_heterodata_serialization=True,own_heterodata_cuda_transfer=True,gurobi_imported='gurobipy' in sys.modules,qualification='library_runtime_only_not_GNN_training_or_performance')
    assert result['gurobi_imported'] is False,'GUROBI_IMPORT_OUTSIDE_SCOPE'
except Exception as error:
    result.update(error_type=type(error).__name__,error_message=str(error)[:1000])
    raise
finally:
    result['ended_utc']=dt.datetime.now(dt.timezone.utc).isoformat()
    (r/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
WORKER
cat > "$R/run.sbatch" <<'BATCH'
#!/usr/bin/env bash
set -euo pipefail
umask 077
R=/scratch/global/__NPAD_USER__/cfl-mvp3-evidence/__INSTALL_STAGE_BASENAME__/runtime-gpu-qualification
T=/home/__NPAD_USER__/venv313_g14
( set -C; : > "$R/batch-start.claim" )
cd "$R"
sha256sum -c "$R/code.sha256"
export TMPDIR="$R/tmp"
export XDG_CACHE_HOME="$R/cache"
export TORCH_HOME="$R/cache/torch"
export TRITON_CACHE_DIR="$R/cache/triton"
export CUDA_CACHE_PATH="$R/cache/cuda"
export MPLCONFIGDIR="$R/cache/matplotlib"
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
srun --ntasks=1 --cpus-per-task=8 --cpu-bind=cores --kill-on-bad-exit=1 timeout --signal=TERM --kill-after=10s 300s env -u PYTHONHOME -u PYTHONPATH -u LD_LIBRARY_PATH -u VIRTUAL_ENV "$T/bin/python" -I -B "$R/check_runtime.py" "$R" > "$R/runtime.private.log" 2>&1
BATCH
sha256sum "$R/check_runtime.py" "$R/run.sbatch" > "$R/code.sha256"
printf 'RECURSOS=1 job|1 V100|1 tarefa|8 CPUs|48G|15 min|0 solves|0 treino\n'
sbatch --parsable --job-name=cfl_runtime_gpu --partition=gpu-8-v100 --account=__NPAD_ACCOUNT__ --qos=preempt --nodes=1 --ntasks=1 --cpus-per-task=8 --mem=48G --gres=gpu:1 --time=00:15:00 --no-requeue --chdir="$R" --output="$R/slurm-%j.private.out" --error="$R/slurm-%j.private.err" --export=ALL "$R/run.sbatch" > "$R/submission.private.txt"
J=$(cut -d';' -f1 "$R/submission.private.txt")
case "$J" in ''|*[!0-9]*) echo SUBMISSAO_AMBIGUA_PRESERVAR_NAO_REPETIR >&2;exit 1;; esac
printf '%s\n' "$J" > "$R/job-id.txt"
printf 'JOB_ID=%s\nETAPA_GPU=%s\n' "$J" "$R"
)
printf 'NPAD_GPU_RUNTIME_SUBMIT_EXIT=%s\n' "$?"
