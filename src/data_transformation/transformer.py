import argparse
import glob
import logging
import os
import gurobipy as gp
from gurobipy import GRB
import pandas as pd
from tqdm import tqdm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_single_file(file_path):
    """
    Reads a .lp.gz file using Gurobi and extracts some basic information
    about variables and constraints.
    """
    env = None
    model = None
    data = []

    try:
        # Create an environment that suppresses console output
        env = gp.Env(empty=True)
        env.setParam("OutputFlag", 0)
        env.start()

        # Load the model
        model = gp.read(file_path, env=env)

        num_vars = model.NumVars
        num_constrs = model.NumConstrs

        data.append({
            "instance_name": os.path.basename(file_path),
            "num_vars": num_vars,
            "num_constrs": num_constrs,
            "is_mip": model.IsMIP
        })

    except gp.GurobiError as e:
        logger.error(f"Gurobi error while processing {file_path}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error while processing {file_path}: {e}")
    finally:
        if model:
            model.dispose()
        if env:
            env.dispose()

    return data

def main():
    parser = argparse.ArgumentParser(description="Transform CFL .lp.gz instances to Parquet format.")
    parser.add_argument("--input_dir", type=str, required=True, help="Directory containing .lp.gz files")
    parser.add_argument("--output_file", type=str, required=True, help="Path for the output .parquet file")

    args = parser.parse_args()

    input_dir = args.input_dir
    output_file = args.output_file

    if not os.path.exists(input_dir):
        logger.error(f"Input directory does not exist: {input_dir}")
        return

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    search_pattern = os.path.join(input_dir, "*.lp.gz")
    files = glob.glob(search_pattern)

    if not files:
        logger.warning(f"No .lp.gz files found in {input_dir}")
        return

    logger.info(f"Found {len(files)} .lp.gz files. Starting transformation...")

    all_data = []
    for file_path in tqdm(files, desc="Processing instances"):
        file_data = process_single_file(file_path)
        all_data.extend(file_data)

    if all_data:
        df = pd.DataFrame(all_data)
        logger.info(f"Saving data to {output_file}")
        try:
            df.to_parquet(output_file, engine='pyarrow')
            logger.info("Data transformation complete.")
        except Exception as e:
            logger.error(f"Error saving to parquet: {e}")
    else:
        logger.warning("No data extracted. Parquet file not created.")

if __name__ == "__main__":
    main()
