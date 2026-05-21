# cfl-gurobi-gnn
Research project developed within an international Cooperation of University of Brasilia, University of Jaén and DaSCI Institute.

This repository contains the code and data to solve Capacitated Facility Location (CFL) problem instances using advanced Gurobi techniques, and subsequently train a Graph Neural Network (GNN) on the generated bipartite graph representations.

## Objectives

### Solve CFL Instances with Gurobi:
* Utilize the 90 downloaded CFL instances from MILPBench.
* Solve these instances using Gurobi with advanced features including:
  * Call-backs
  * Solution Pool
  * Partial MIP Starts
  * Variable Hints
* Save intermediate Gurobi solutions as new Linear Programming (LP) instances.

### Graph Representation and GNN Training:
* Transform all generated and original instances into Bipartite Graph representations.
* Train a modified Graph Neural Network (GNN) based on the work of Liang et al., which utilizes baseline architecture and concepts from Gasse et al., 2019 (learn2branch).

## Repository Structure
```text
.
├── README.md                   # Project documentation
├── data/
│   ├── raw/
│   │   └── MILPBench/
│   │       └── CFL/            # The 90 downloaded CFL instances
│   ├── intermediate_lps/       # Saved intermediate LP instances from Gurobi
│   └── bipartite_graphs/       # Transformed bipartite graph data
├── src/
│   ├── gurobi_solver/          # Scripts for solving instances and saving intermediate LPs
│   │   └── solver.py           # Gurobi optimization with callbacks, solution pool, etc.
│   ├── graph_transform/        # Scripts to convert instances to bipartite graphs
│   │   └── bipartite_builder.py
│   └── gnn/                    # Code for training the modified GNN (Liang et al. / Gasse et al.)
│       └── train.py
├── notebooks/                  # Jupyter notebooks for exploratory analysis
├── requirements.txt            # Python dependencies
└── setup.py                    # Project setup
```

## Getting Started

### Prerequisites
* Python 3.8+
* Gurobi Optimizer with a valid license
* PyTorch and PyTorch Geometric (for the GNN)

### Installation
Clone the repository:
```bash
git clone https://github.com/unb-lamfo-or-ai-hpc/cfl-gurobi-gnn.git
cd cfl-gurobi-gnn
```

Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. **Solving Instances:**
Run the Gurobi solver script to process the CFL instances and generate intermediate LPs:
```bash
python src/gurobi_solver/solver.py --input_dir data/raw/MILPBench/CFL --output_dir data/intermediate_lps
```

2. **Graph Transformation:**
Convert the generated LP instances into bipartite graphs:
```bash
python src/graph_transform/bipartite_builder.py --input_dir data/intermediate_lps --output_dir data/bipartite_graphs
```

3. **Training the GNN:**
Train the Graph Neural Network using the processed bipartite graphs:
```bash
python src/gnn/train.py --data_dir data/bipartite_graphs --epochs 100
```

## References
* **MILPBench**: https://github.com/thuiar/MILPBench
* **Liang et al. (Modified GNN)**: https://www.sciencedirect.com/science/article/pii/S1569843224002176
* **Gasse et al., 2019 (learn2branch)**: https://github.com/ds4dm/learn2branch
