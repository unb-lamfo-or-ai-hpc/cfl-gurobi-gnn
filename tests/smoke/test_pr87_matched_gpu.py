"""Actual CPU tensor/DDP gradient checks; synthetic data, NOT research training."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

try:
    import torch
    import torch.distributed as dist
    import torch.multiprocessing as mp
    from torch.nn.parallel import DistributedDataParallel
except ImportError:
    torch = None

from cfl_gnn.training.matched_gpu import ddp_step, serial_step  # noqa: E402


def items():
    generator = torch.Generator().manual_seed(42)
    return [
        (
            torch.randn(n, 3, dtype=torch.float64, generator=generator) * 5,
            torch.randint(0, 2, (n,), generator=generator).double(),
        )
        for n in (2, 3, 7, 11)
    ]


def network():
    torch.manual_seed(42)
    return torch.nn.Linear(3, 1, dtype=torch.float64)


def loss(model, item):
    x, y = item
    return torch.nn.functional.binary_cross_entropy_with_logits(
        model(x).squeeze(-1), y, pos_weight=torch.tensor([3.0], dtype=torch.float64)
    )


def ddp_worker(rank, rendezvous, output):
    torch.set_num_threads(1)
    dist.init_process_group("gloo", init_method=rendezvous, rank=rank, world_size=4)
    model = DistributedDataParallel(network())
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    for _ in range(3):
        ddp_step(model, items()[rank], optimizer, loss)
    if rank == 0:
        Path(output).write_text(
            json.dumps([p.detach().tolist() for p in model.module.parameters()]),
            encoding="utf-8",
        )
    dist.destroy_process_group()


@unittest.skipIf(
    torch is None, "torch unavailable locally; pinned CPU tensor CI covers this"
)
class MatchedTensorTests(unittest.TestCase):
    def test_serial_accumulation_is_global_mean_then_one_clip_update(self):
        torch.set_num_threads(1)
        a, b = network(), network()
        opt_a = torch.optim.Adam(a.parameters(), lr=0.001)
        opt_b = torch.optim.Adam(b.parameters(), lr=0.001)
        for _ in range(3):
            serial_step(a, items(), opt_a, loss)
            opt_b.zero_grad(set_to_none=True)
            torch.stack([loss(b, item) for item in items()]).mean().backward()
            torch.nn.utils.clip_grad_norm_(b.parameters(), 1.0)
            opt_b.step()
        for x, y in zip(a.parameters(), b.parameters()):
            torch.testing.assert_close(x, y, rtol=1e-12, atol=1e-12)

    @unittest.skipIf(sys.platform == "win32", "four-process Gloo covered on Linux")
    def test_four_rank_ddp_matches_serial_for_unequal_graph_sizes(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp).resolve()
            rendezvous = (directory / "rendezvous").as_uri()
            output = directory / "state.json"
            mp.spawn(ddp_worker, args=(rendezvous, str(output)), nprocs=4, join=True)
            a = network()
            optimizer = torch.optim.Adam(a.parameters(), lr=0.001)
            for _ in range(3):
                serial_step(a, items(), optimizer, loss)
            for actual, expected in zip(a.parameters(), json.loads(output.read_text())):
                torch.testing.assert_close(
                    actual,
                    torch.tensor(expected, dtype=torch.float64),
                    rtol=1e-12,
                    atol=1e-12,
                )

    def test_torch_21_graph_layer_forward_backward(self):
        from cfl_gnn.models.gasse_calibrated import GasseGNN

        model = GasseGNN(7, 5, edge_dim=1, hidden_dim=32, num_layers=2)
        xvar, xcons = torch.randn(4, 7), torch.randn(3, 5)
        edges = torch.tensor([[0, 1, 2, 3, 0], [0, 1, 2, 0, 2]])
        attrs = torch.randn(5, 1)
        model.fit_prenorm(xvar, xcons, edges, attrs)
        output = model(
            xvar, xcons, edges, torch.tensor([True, False, True, True]), attrs
        )
        output.square().mean().backward()
        self.assertEqual(tuple(output.shape), (3,))
        self.assertTrue(
            all(
                p.grad is not None and torch.isfinite(p.grad).all()
                for p in model.parameters()
            )
        )


if __name__ == "__main__":
    unittest.main()
