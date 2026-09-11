"""Versioned alternating-message prenormalization; legacy gasse.py is immutable."""

from __future__ import annotations

import torch
from torch.nn.functional import relu

from cfl_gnn.models.gasse import GasseGNN as LegacyGasseGNN, _scatter_sum

MODEL_VERSION = "gasse_v2_alternating_prenorm"


class GasseGNN(LegacyGasseGNN):
    """Same trainable architecture, corrected fitting of the V-side messages."""

    @torch.no_grad()
    def fit_prenorm(self, x_var, x_cons, edge_v2c, edge_attr=None):
        h_v, h_c = relu(self.var_encoder(x_var)), relu(self.cons_encoder(x_cons))
        for conv in self.convs:
            v, c = edge_v2c
            msg = conv._edge_input(h_c, h_v, edge_v2c, edge_attr)
            sums = _scatter_sum(conv.g_C(msg), c, len(h_c))
            _fit_buffer(conv.prenorm_C, sums)
            updated_c = relu(conv.f_C(torch.cat([h_c, conv.prenorm_C(sums)], dim=-1)))
            msg = conv._edge_input(updated_c, h_v, edge_v2c, edge_attr)
            _fit_buffer(conv.prenorm_V, _scatter_sum(conv.g_V(msg), v, len(h_v)))
            h_v, h_c = conv(h_v, h_c, edge_v2c, edge_attr)


def _fit_buffer(layer, values):
    layer.beta.copy_(values.mean(0))
    layer.sigma.copy_(values.std(0, correction=0).clamp(min=1e-8))


@torch.no_grad()
def fit_training_prenorm(model, dataset, device):
    """Streaming population moments over every training graph, in index order.

    All ranks must use the same complete training dataset, not a distributed
    shard. Validation/test datasets must never be supplied. No node tensors
    from multiple graphs are retained at once.
    """
    if not len(dataset):
        raise ValueError("prenorm training population is empty")

    def embeddings(graph, layer_index):
        edge = graph["variable", "rev_coef", "constraint"]
        hv = relu(model.var_encoder(graph["variable"].x))
        hc = relu(model.cons_encoder(graph["constraint"].x))
        for previous in model.convs[:layer_index]:
            hv, hc = previous(hv, hc, edge.edge_index, edge.edge_attr)
        return hv, hc, edge.edge_index, edge.edge_attr

    for layer_index, conv in enumerate(model.convs):
        for side in ("C", "V"):
            count, mean, m2 = 0, None, None
            for index in range(len(dataset)):
                graph = dataset[index].to(device)
                hv, hc, edges, attrs = embeddings(graph, layer_index)
                v, c = edges
                msg = conv._edge_input(hc, hv, edges, attrs)
                sums = _scatter_sum(conv.g_C(msg), c, len(hc))
                if side == "V":
                    hc = relu(conv.f_C(torch.cat([hc, conv.prenorm_C(sums)], -1)))
                    msg = conv._edge_input(hc, hv, edges, attrs)
                    sums = _scatter_sum(conv.g_V(msg), v, len(hv))
                values = sums.double()
                n = len(values)
                if not n or not bool(torch.isfinite(values).all()):
                    raise ValueError("invalid training prenorm messages")
                batch_mean = values.mean(0)
                batch_m2 = ((values-batch_mean)**2).sum(0)
                if mean is None:
                    mean, m2, count = batch_mean, batch_m2, n
                else:
                    delta = batch_mean-mean
                    m2 += batch_m2 + delta.square() * count*n/(count+n)
                    mean += delta*n/(count+n)
                    count += n
            buffer = getattr(conv, "prenorm_"+side)
            buffer.beta.copy_(mean)
            buffer.sigma.copy_((m2/count).sqrt().clamp(min=1e-8))
    return {"model_version": MODEL_VERSION, "training_graphs": len(dataset),
            "method": "streaming_population_moments_all_training_graphs",
            "validation_or_test_used": False}
