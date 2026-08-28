"""
Step 4: GNN Inference and Variable Hints Generation (.hnt)
==========================================================
Reads a .lp or .lp.gz file, solves its LP relaxation to build the input
graph, runs GNN inference on CPU, and exports ALL discrete variable
predictions as a Gurobi Variable Hints file (.hnt).

Key differences from generate_mip_start.py (v3):
  - Output format: .hnt (VarHintVal + VarHintPri) instead of .mst (Start)
  - Coverage: ALL discrete variables receive a hint (no hard confidence cutoff)
  - Priority: mapped from GNN output probability using a confidence formula
  - Column index: corrected (is_bin=col4, is_int=col5) from the critical v3 bug
  - torch.load: uses weights_only=True (safe for state dicts, PyTorch 2.0+)

Variable feature layout (must match build_pyg_dataset):
  col 0 : objective coefficient  (log-scaled)
  col 1 : lower bound            (log-scaled)
  col 2 : upper bound            (log-scaled)
  col 3 : is_continuous          (one-hot)
  col 4 : is_binary              (one-hot)   <-- corrected index
  col 5 : is_integer             (one-hot)   <-- corrected index
  col 6 : LP relaxation value    (raw)

HNT file format (Gurobi 13.0):
  # comment
  variable_name  hint_value  hint_priority
  Each line is a triple; priority is a non-negative integer.
"""

import os
import argparse
import time
import numpy as np
import torch
from torch_geometric.data import HeteroData
import gurobipy as gp
from gurobipy import GRB

from cfl_gnn.models.gasse import GasseGNN
from cfl_gnn.paths import PROJECT_ROOT

project_root = str(PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Priority mapping constants
# ---------------------------------------------------------------------------
# Maps |p - 0.5| in [0, 0.5] to an integer priority in [0, MAX_PRIORITY].
# p = 1.0 or p = 0.0  -->  priority = MAX_PRIORITY  (maximum confidence)
# p = 0.5              -->  priority = 0             (complete uncertainty)
MAX_PRIORITY = 100


# ---------------------------------------------------------------------------
# Utility: sanitize and convert numpy arrays to PyTorch tensors
# ---------------------------------------------------------------------------
def sanitize_array(arr: np.ndarray,
                   apply_log_scale: bool = False) -> torch.FloatTensor:
    """
    Clips and optionally log-scales a numpy array, then returns a (N, 1) tensor.

    Args:
        arr             : Input 1-D numpy array.
        apply_log_scale : If True, applies sign(x) * log1p(|x|) transform.

    Returns:
        torch.FloatTensor of shape (N, 1).
    """
    arr = np.nan_to_num(arr, nan=0.0, posinf=60000.0, neginf=-60000.0)
    arr = np.clip(arr, -60000.0, 60000.0)
    if apply_log_scale:
        arr = np.sign(arr) * np.log1p(np.abs(arr))
    return torch.FloatTensor(arr).unsqueeze(-1)


# ---------------------------------------------------------------------------
# Graph construction (identical feature layout to build_pyg_dataset_v3)
# ---------------------------------------------------------------------------
def build_graph_from_gurobi(model_gp: gp.Model,
                             lp_vector: np.ndarray):
    """
    Assembles a HeteroData PyG graph from an original (not presolved) Gurobi model
    and its LP relaxation solution vector.

    Variable feature columns (0-indexed):
        0: obj coeff (log-scaled)
        1: lower bound (log-scaled)
        2: upper bound (log-scaled)
        3: is_continuous (one-hot)
        4: is_binary     (one-hot)   <-- CORRECTED from v3
        5: is_integer    (one-hot)   <-- CORRECTED from v3
        6: lp_value      (raw)

    Constraint feature columns:
        0: RHS (log-scaled)
        1: sense_less_equal    (one-hot)
        2: sense_equal         (one-hot)
        3: sense_greater_equal (one-hot)
        4: dummy constant 1.0

    Args:
        model_gp  : Original (un-presolved) gurobipy Model object.
        lp_vector : LP relaxation solution, aligned to model_gp variables.

    Returns:
        (HeteroData, List[str]) — PyG graph and list of variable names.
    """
    vars_list   = model_gp.getVars()
    constrs     = model_gp.getConstrs()

    # --- Variable raw features ---
    var_types   = np.array([v.VType for v in vars_list])
    var_obj     = np.array([v.Obj   for v in vars_list])
    var_lb      = np.array([v.LB    for v in vars_list])
    var_ub      = np.array([v.UB    for v in vars_list])

    # --- Constraint raw features ---
    constr_senses = np.array([c.Sense for c in constrs])
    constr_rhs    = np.array([c.RHS   for c in constrs])

    # --- Sparse constraint matrix (COO format) ---
    rows, cols, vals = [], [], []
    for i, constr in enumerate(constrs):
        row = model_gp.getRow(constr)
        for j in range(row.size()):
            rows.append(i)
            cols.append(row.getVar(j).index)
            vals.append(row.getCoeff(j))

    # --- Variable node feature matrix (7 columns) ---
    obj_tensor = sanitize_array(var_obj,    apply_log_scale=True)
    lb_tensor  = sanitize_array(var_lb,     apply_log_scale=True)
    ub_tensor  = sanitize_array(var_ub,     apply_log_scale=True)
    lp_tensor  = sanitize_array(lp_vector,  apply_log_scale=False)

    # One-hot type encoding — string comparison, NOT ASCII codes
    is_cont = torch.FloatTensor((var_types == GRB.CONTINUOUS).astype(float)).unsqueeze(-1)
    is_bin  = torch.FloatTensor((var_types == GRB.BINARY).astype(float)).unsqueeze(-1)
    is_int  = torch.FloatTensor((var_types == GRB.INTEGER).astype(float)).unsqueeze(-1)

    # col 0  1    2    3       4      5      6
    v_features = torch.cat([obj_tensor, lb_tensor, ub_tensor,
                             is_cont, is_bin, is_int, lp_tensor], dim=1)

    # --- Constraint node feature matrix (5 columns) ---
    rhs_tensor     = sanitize_array(constr_rhs, apply_log_scale=True)
    # String comparison — robust to bytes vs str storage
    sense_le  = torch.FloatTensor((constr_senses == '<').astype(float)).unsqueeze(-1)
    sense_eq  = torch.FloatTensor((constr_senses == '=').astype(float)).unsqueeze(-1)
    sense_ge  = torch.FloatTensor((constr_senses == '>').astype(float)).unsqueeze(-1)
    c_dummy   = torch.ones_like(rhs_tensor)
    c_features = torch.cat([rhs_tensor, sense_le, sense_eq, sense_ge, c_dummy], dim=1)

    # --- Bipartite edge indices and weights ---
    edge_weight   = sanitize_array(np.array(vals), apply_log_scale=True)
    rows_t        = torch.LongTensor(rows)
    cols_t        = torch.LongTensor(cols)
    edge_index_v2c = torch.stack([cols_t, rows_t], dim=0)  # variable -> constraint
    edge_index_c2v = torch.stack([rows_t, cols_t], dim=0)  # constraint -> variable

    # --- Assemble HeteroData ---
    data = HeteroData()
    data['variable'].x   = v_features
    data['constraint'].x = c_features
    data['variable',   'rev_coef', 'constraint'].edge_index = edge_index_v2c
    data['variable',   'rev_coef', 'constraint'].edge_attr  = edge_weight
    data['constraint', 'coef',     'variable'  ].edge_index = edge_index_c2v
    data['constraint', 'coef',     'variable'  ].edge_attr  = edge_weight

    var_names = [v.VarName for v in vars_list]
    return data, var_names


# ---------------------------------------------------------------------------
# Priority computation
# ---------------------------------------------------------------------------
def compute_hint_priority(probability: float) -> int:
    """
    Maps a GNN output probability to a Gurobi VarHintPri integer.

    The formula measures distance from 0.5 (maximum uncertainty):
        priority = floor(|p - 0.5| * 2 * MAX_PRIORITY)

    Examples:
        p = 1.00  -->  priority = 100  (absolute confidence: assign 1)
        p = 0.00  -->  priority = 100  (absolute confidence: assign 0)
        p = 0.90  -->  priority =  80  (high confidence)
        p = 0.60  -->  priority =  20  (slight preference)
        p = 0.50  -->  priority =   0  (coin flip — Gurobi ignores)

    Args:
        probability : Sigmoid output of GNN in [0.0, 1.0].

    Returns:
        Non-negative integer priority in [0, MAX_PRIORITY].
    """
    return int(abs(probability - 0.5) * 2.0 * MAX_PRIORITY)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="GNN Inference → Gurobi Variable Hints (.hnt) generator"
    )
    parser.add_argument('--lp_file',    type=str, required=True,
                        help="Path to the .lp or .lp.gz instance file.")
    parser.add_argument('--model_path', type=str, required=True,
                        help="Path to the trained GNN weights (.pt state dict).")
    parser.add_argument('--output_dir', type=str, default=None,
                        help="Directory for .hnt output files. "
                             "Defaults to <project_root>/data/mip_hints/.")
    parser.add_argument('--hidden_dim', type=int, default=32,
                        help="GNN hidden dimension (must match training config).")
    parser.add_argument('--num_layers', type=int, default=2,
                        help="Number of GNN message-passing layers.")
    parser.add_argument('--min_priority', type=int, default=0,
                        help="Minimum priority threshold. Variables with computed "
                             "priority below this value are omitted from the .hnt "
                             "file (equivalent to not providing a hint). Default=0 "
                             "means all discrete variables are always included.")
    args = parser.parse_args()

    device = torch.device("cpu")
    print("=" * 70)
    print(f" Variable Hints Generator  |  Device: {device}  |  Gurobi 13.0")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # Step 1: Solve LP relaxation to obtain lp_vector for graph features
    # -----------------------------------------------------------------------
    print("\n[1/4] Solving LP relaxation...")
    t0 = time.time()

    with gp.Env(empty=True) as env:
        env.setParam("OutputFlag",    0)
        env.setParam("LogToConsole",  0)
        env.start()

        # Load original model
        model_gp = gp.read(args.lp_file, env=env)

        # Solve continuous relaxation
        relaxed = model_gp.relax()
        relaxed.optimize()

        if relaxed.Status != GRB.OPTIMAL:
            print(f"  [WARN] LP relaxation status {relaxed.Status} — "
                  f"using zero vector as fallback.")
            lp_vector = np.zeros(model_gp.NumVars)
        else:
            lp_vector = np.array([v.X for v in relaxed.getVars()])

        # LP vector must be aligned to original model (no presolve applied)
        if len(lp_vector) != model_gp.NumVars:
            print(f"  [WARN] LP vector length {len(lp_vector)} != "
                  f"model NumVars {model_gp.NumVars}. Using zero vector.")
            lp_vector = np.zeros(model_gp.NumVars)

        relaxed.dispose()

        # -----------------------------------------------------------------------
        # Step 2: Build bipartite PyG graph from original model
        # -----------------------------------------------------------------------
        print("[2/4] Building bipartite graph from original model...")
        graph, var_names = build_graph_from_gurobi(model_gp, lp_vector)
        model_gp.dispose()

    print(f"      Variables : {graph['variable'].x.shape[0]}")
    print(f"      Constraints: {graph['constraint'].x.shape[0]}")
    print(f"      Edges      : {graph['variable', 'rev_coef', 'constraint'].edge_index.shape[1]}")
    print(f"      LP solve   : {time.time() - t0:.2f}s")

    # -----------------------------------------------------------------------
    # Step 3: Load GNN weights and run inference
    # -----------------------------------------------------------------------
    print(f"\n[3/4] Loading GNN weights and running inference...")
    t1 = time.time()

    gnn = GasseGNN(
        var_in_dim  = 7,
        cons_in_dim = 5,
        edge_dim    = 1,
        hidden_dim  = args.hidden_dim,
        num_layers  = args.num_layers
    )
    # weights_only=True is safe here because we load a pure state dict
    gnn.load_state_dict(
        torch.load(args.model_path, map_location=device, weights_only=True)
    )
    gnn.eval()

    # Discrete variable mask — CORRECTED column indices (4=binary, 5=integer)
    is_bin_mask = graph['variable'].x[:, 4] == 1.0   # col 4: is_binary
    is_int_mask = graph['variable'].x[:, 5] == 1.0   # col 5: is_integer
    target_mask = is_bin_mask | is_int_mask

    with torch.no_grad():
        logits = gnn(
            x_var      = graph['variable'].x,
            x_cons     = graph['constraint'].x,
            edge_v2c   = graph['variable', 'rev_coef', 'constraint'].edge_index,
            binary_mask= target_mask,
            edge_attr  = graph['variable', 'rev_coef', 'constraint'].edge_attr
        )
        probabilities = torch.sigmoid(logits).squeeze(-1).numpy()

    num_discrete = int(target_mask.sum().item())
    print(f"      Discrete variables : {num_discrete}")
    print(f"      Inference time     : {time.time() - t1:.3f}s")

    # -----------------------------------------------------------------------
    # Step 4: Write .hnt file — all discrete variables, priority from confidence
    # -----------------------------------------------------------------------
    print("\n[4/4] Writing Variable Hints (.hnt) file...")

    instance_name = (os.path.basename(args.lp_file)
                     .replace('.lp.gz', '')
                     .replace('.lp',    ''))

    output_dir = args.output_dir or os.path.join(project_root, "data", "mip_hints")
    os.makedirs(output_dir, exist_ok=True)
    hnt_path = os.path.join(output_dir, f"{instance_name}_gnn_hint.hnt")

    discrete_indices = torch.where(target_mask)[0].numpy()

    written      = 0
    high_conf    = 0   # priority >= 80  (|p - 0.5| >= 0.40)
    medium_conf  = 0   # priority in [40, 80)
    low_conf     = 0   # priority < 40

    with open(hnt_path, 'w') as f:
        # Header comment — Gurobi .hnt format requires # for comments
        f.write(f"# MIP hints generated by GNN inference\n")
        f.write(f"# Instance  : {instance_name}\n")
        f.write(f"# Model     : {os.path.basename(args.model_path)}\n")
        f.write(f"# Format    : variable_name  hint_value  hint_priority\n")
        f.write(f"# Priority  : floor(|p - 0.5| * 200),  range [0, {MAX_PRIORITY}]\n")
        f.write("#\n")

        for idx, prob in zip(discrete_indices, probabilities):
            hint_val      = 1 if prob >= 0.5 else 0
            hint_priority = compute_hint_priority(float(prob))

            # Skip variables below the minimum priority threshold if requested
            if hint_priority < args.min_priority:
                continue

            f.write(f"{var_names[idx]}  {hint_val}  {hint_priority}\n")
            written += 1

            if   hint_priority >= 80: high_conf   += 1
            elif hint_priority >= 40: medium_conf += 1
            else:                     low_conf    += 1

    # -----------------------------------------------------------------------
    # Summary report
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"  VARIABLE HINTS FILE GENERATED SUCCESSFULLY")
    print("=" * 70)
    print(f"  Output path          : {hnt_path}")
    print(f"  Total discrete vars  : {num_discrete}")
    print(f"  Hints written        : {written}")
    print(f"  High  conf (pri>=80) : {high_conf}  "
          f"({100*high_conf/max(written,1):.1f}%)")
    print(f"  Med   conf (pri>=40) : {medium_conf}  "
          f"({100*medium_conf/max(written,1):.1f}%)")
    print(f"  Low   conf (pri< 40) : {low_conf}  "
          f"({100*low_conf/max(written,1):.1f}%)")
    print("=" * 70)
    print(f"\n  Usage in Gurobi:")
    print(f"    model.read('{os.path.basename(hnt_path)}')")
    print(f"  This is equivalent to setting VarHintVal and VarHintPri")
    print(f"  attributes for all {written} listed variables.")
    print("=" * 70)


if __name__ == "__main__":
    main()
