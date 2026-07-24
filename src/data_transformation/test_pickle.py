import gzip
import pickle
from collections import namedtuple

# Las tuplas que definimos en la Fase 1
ModelFeatures = namedtuple('ModelFeatures', [
    'num_vars', 'num_constrs', 'num_binary', 'num_integer', 
    'num_continuous', 'obj_sense', 'obj_offset'
])
VariableFeatures = namedtuple('VariableFeatures', [
    'types', 'lower_bounds', 'upper_bounds', 'obj_coeffs'
])
ConstraintFeatures = namedtuple('ConstraintFeatures', [
    'senses', 'rhs_values', 'row_norms'
])

path = "/raid/vrcelestino/data/cfl-gurobi-gnn/data/intermediate_lps/CFL_easy_instance/CFL_easy_instance_0/original_features.pickle.gz"

print("Abriendo archivo Pickle...")
with gzip.open(path, 'rb') as f:
    data = pickle.load(f)
    print("\nKeys principales del diccionario:")
    print(data.keys())
    print("\nTipos de datos internos:")
    for key, value in data.items():
        print(f"- {key}: {type(value)}")