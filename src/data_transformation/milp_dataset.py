# Archivo: milp_dataset.py
import os
import torch
from torch_geometric.data import Dataset

class NeuralDivingDataset(Dataset):
    def __init__(self, root, transform=None, pre_transform=None):
        """
        root: Directorio base.
        PyG buscará automáticamente dentro de root/processed/
        """
        super().__init__(root, transform, pre_transform)

    @property
    def processed_file_names(self):
        if not os.path.exists(self.processed_dir):
            return []
        files = [f for f in os.listdir(self.processed_dir) if f.startswith('data_') and f.endswith('.pt')]
        return files

    def len(self):
        return len(self.processed_file_names)

    def get(self, idx):
        # Carga perezosa (Lazy Loading) desde el disco
        data = torch.load(os.path.join(self.processed_dir, f'data_{idx}.pt'))
        return data