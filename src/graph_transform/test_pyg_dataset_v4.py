"""
Audit Script: PyG Multi-Task Dataset
====================================
Verifies graph topology, metadata propagation, and ensures the LP 
relaxation vector is properly bounded by the variable upper bounds.
"""

import sys
import os
import argparse
import torch
import importlib.util

## Robust path resolution to locate the project root dynamically
#def find_project_root(start: str) -> str:
#    current = start
#    for _ in range(10):  # Max 10 levels up
#        if any(os.path.exists(os.path.join(current, marker))
#               for marker in ('pyproject.toml', 'setup.py', 'setup.cfg')):
#            return current
#        parent = os.path.dirname(current)
#        if parent == current:
#            break
#        current = parent
#    return start

#project_root = find_project_root(os.path.dirname(os.path.abspath(__file__)))
#sys.path.insert(0, project_root)

# Alternate path reolution for src.graph_transform.milp_dataset
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
sys.path.insert(0, project_root)

from src.graph_transform.milp_dataset_v2 import NeuralDivingDataset

def audit_dataset(dataset, category_name):
    """
    Audits the first graph of a category for:
    1. Metadata propagation (Complexity Class)
    2. LP Vector bounds (vs Variable UB tensor)
    3. Graph topology integrity
    """
    print(f"\n--- X-Ray: First graph of {category_name} ---")
    grafo = dataset[0]
    
    # Metadata Propagation Audit
    print(f" -> Complexity Class : {getattr(grafo, 'complexity_class', 'N/A')}")
    print(f" -> Probe Node Count : {getattr(grafo, 'probe_node_count', -1)}")
    
    # LP Vector Validation: Check against UB tensor (Column 2)
    ub_vector = grafo['variable'].x[:, 2]
    lp_vector = grafo['variable'].x[:, 6]
    
    # Correct bound validation: LP vector must be <= UB
    violations = (lp_vector > ub_vector + 1e-6).sum().item()
    
    print(f" -> LP values exceeding variable UB: {violations}")
    if violations > 0:
        print(" [RED ALERT] LP vector exceeds Upper Bound — potential mapping error.")
    else:
        print(" [OK] LP vector is within variable bounds.")
    
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