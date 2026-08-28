"""
Audit Script: PyG Multi-Task Dataset
====================================
Verifies graph topology, metadata propagation, and ensures the LP 
relaxation vector is properly bounded by the variable upper bounds.
"""

import os
import argparse
import torch

from cfl_gnn.graph.dataset import NeuralDivingDataset

def inverse_log_scale(tensor: torch.Tensor) -> torch.Tensor:
    """
    Reverses the signed log1p transformation applied during Phase 2 ETL.
    Formula: x = sign(x) * (exp(|x|) - 1)
    """
    return torch.sign(tensor) * (torch.exp(torch.abs(tensor)) - 1)

def audit_dataset(dataset, category_name):
    """
    Audits the first graph of a category for:
    1. Metadata propagation (Complexity Class)
    2. LP Vector bounds (vs Variable UB tensor, correctly reversing log-scale)
    3. Graph topology integrity
    """
    print(f"\n--- X-Ray: First graph of {category_name} ---")
    grafo = dataset[0]
    
    # Metadata Propagation Audit
    print(f" -> Complexity Class : {getattr(grafo, 'complexity_class', 'N/A')}")
    print(f" -> Probe Node Count : {getattr(grafo, 'probe_node_count', -1)}")
    
    # LP Vector Validation
    # Column 2 is log-scaled UB. We must reverse the transformation before comparison.
    ub_vector_log_scaled = grafo['variable'].x[:, 2]
    ub_vector_raw = inverse_log_scale(ub_vector_log_scaled)
    
    # Column 6 is the unscaled LP relaxation vector.
    lp_vector = grafo['variable'].x[:, 6]
    
    # Correct bound validation: LP vector must be <= UB (with a small epsilon for floating point errors)
    violations = (lp_vector > ub_vector_raw + 1e-4).sum().item()
    
    print(f" -> LP values exceeding variable UB: {violations}")
    if violations > 0:
        print(" [RED ALERT] LP vector exceeds Upper Bound — scaling or mapping error detected.")
    else:
        print(" [OK] LP vector is strictly within variable bounds.")
    
    # Audit Topology
    num_vars = grafo['variable'].x.shape[0]
    num_cons = grafo['constraint'].x.shape[0]
    print(f" -> Topology: {num_vars} variables, {num_cons} constraints.")

def main():
    parser = argparse.ArgumentParser(description="Audit PyG Multi-Task Dataset")
    parser.add_argument('--categories', nargs='+', 
                        default=["CFL_easy_instance", "CFL_medium_instance", "CFL_hard_instance"])
    args = parser.parse_args()

    base_root = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/bipartite_graphs/pyg_dataset"
    
    print("=== Starting Dataset Audit (Multi-Task) ===")
    
    for cat in args.categories:
        cat_root = os.path.join(base_root, cat)
        if not os.path.exists(cat_root):
            print(f" [WARN] Category directory not found: {cat_root}")
            continue
            
        ds = NeuralDivingDataset(root=cat_root)
        if len(ds) > 0:
            audit_dataset(ds, cat)
        else:
            print(f" [WARN] Dataset {cat} is empty.")

    print("\n=== Audit Finished ===")

if __name__ == "__main__":
    main()
