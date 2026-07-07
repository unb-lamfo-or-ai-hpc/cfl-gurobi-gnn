"""
Dataset: NeuralDivingDataset
============================
Optimized dataset class for PyG HeteroData, featuring disk I/O caching 
to prevent performance bottlenecks on HPC clusters.
"""

import os
import torch
from torch_geometric.data import Dataset

class NeuralDivingDataset(Dataset):
    """
    NeuralDivingDataset handles the loading of pre-processed HeteroData 
    graph objects from the disk. Implements file caching to ensure efficient 
    data access during multi-epoch training on DGX clusters.
    """
    def __init__(self, root, transform=None, pre_transform=None):
        """
        Args:
            root (str): Base directory containing the processed data.
        """
        super().__init__(root, transform, pre_transform)
        self._file_cache = None

    @property
    def processed_file_names(self):
        """
        Returns a cached list of processed .pt files.
        Avoids redundant disk I/O calls (os.listdir) in the get() method.
        """
        if self._file_cache is None:
            if not os.path.exists(self.processed_dir):
                self._file_cache = []
            else:
                # Filter and sort data files by index to ensure deterministic ordering
                files = [f for f in os.listdir(self.processed_dir) 
                         if f.startswith('data_') and f.endswith('.pt')]
                # Sort numerically based on the integer index in 'data_{idx}.pt'
                files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
                self._file_cache = files
        return self._file_cache

    def len(self):
        """Returns the number of processed graphs in the dataset."""
        return len(self.processed_file_names)

    def get(self, idx):
        """
        Loads a HeteroData object from the disk with lazy loading.
        
        Args:
            idx (int): The index of the graph to load.
            
        Returns:
            data (HeteroData): The loaded graph object.
        """
        actual_file = self.processed_file_names[idx]
        file_path = os.path.join(self.processed_dir, actual_file)
        
        # weights_only=False is required for custom HeteroData/PyG objects.
        # This prevents potential security warnings in PyTorch 2.0+.
        data = torch.load(file_path, weights_only=False)
        return data