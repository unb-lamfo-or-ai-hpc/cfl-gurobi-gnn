import torch
from torch.nn import Linear
from torch.nn.functional import relu

# --------------------------------------------------------------------------- #
# Gasse et al. (NeurIPS 2019)                       #
# --------------------------------------------------------------------------- #


def _scatter_sum(src, idx, n):
    """Accumulate rows of `src` into `n` buckets by `idx` (pure PyTorch)."""
    out = torch.zeros(n, src.size(-1), dtype=src.dtype, device=src.device)
    out.scatter_add_(0, idx.unsqueeze(-1).expand_as(src), src)
    return out


class _MLP2(torch.nn.Module):
    """2-layer perceptron with ReLU hidden activation (Gasse et al. 2019)."""

    def __init__(self, in_dim, hidden_dim, out_dim):
        super().__init__()
        self.fc1 = Linear(in_dim, hidden_dim)
        self.fc2 = Linear(hidden_dim, out_dim)

    def reset_parameters(self):
        self.fc1.reset_parameters()
        self.fc2.reset_parameters()

    def forward(self, x):
        return self.fc2(relu(self.fc1(x)))


class _Prenorm(torch.nn.Module):
    """Fixed affine normalisation x <- (x - Beta) / (sigma) from Gasse et al. (2019).

    Beta and sigma are set once from data via `fit()` and stored as non-trainable
    buffers (not updated during backprop).
    """

    def __init__(self, dim):
        super().__init__()
        self.register_buffer("beta", torch.zeros(dim))
        self.register_buffer("sigma", torch.ones(dim))

    def fit(self, x: torch.Tensor):
        """Set Beta = mean(x) and sigma = std(x) from a representative tensor."""
        self.beta.copy_(x.detach().mean(dim=0))
        self.sigma.copy_(x.detach().std(dim=0).clamp(min=1e-8))

    def forward(self, x):
        return (x - self.beta) / self.sigma


class GasseBipartiteConv(torch.nn.Module):
    """Single bipartite conv layer from Gasse et al. (NeurIPS 2019), eq. (4).

    Performs two alternating half-convolutions:

        c_i <- f_C( c_i,  prenorm( SUM_j g_C(c_i, v_j, e_{ij}) ) )
        v_j <- f_V( v_j,  prenorm( SUM_i g_V(c_i, v_j, e_{ij}) ) )
                         --> uses the freshly updated c_i (alternating)

    g_C, g_V, f_C, f_V are all 2-layer MLPs with ReLU.
    Prenorm layers must be fitted before training via `fit_prenorm()`.

    Parameters
    ----------
    var_dim  : dimension of variable node embeddings.
    cons_dim : dimension of constraint node embeddings.
    edge_dim : dimension of edge features (0 if none).
    hidden_dim : output dimension for both node types.
    """

    def __init__(self, var_dim, cons_dim, edge_dim, hidden_dim):
        super().__init__()
        msg_in = cons_dim + var_dim + edge_dim

        # Message functions  g_C, g_V : (c_i || v_j [|| e_ij]) -> hidden_dim
        self.g_C = _MLP2(msg_in, hidden_dim, hidden_dim)
        self.g_V = _MLP2(msg_in, hidden_dim, hidden_dim)

        # Update functions   f_C, f_V : (node || aggregated_msg) -> hidden_dim
        self.f_C = _MLP2(cons_dim + hidden_dim, hidden_dim, hidden_dim)
        self.f_V = _MLP2(var_dim + hidden_dim, hidden_dim, hidden_dim)

        self.prenorm_C = _Prenorm(hidden_dim)
        self.prenorm_V = _Prenorm(hidden_dim)

    def reset_parameters(self):
        """Re-initialise the message/update MLPs.

        Does not touch the prenorm buffers; refit them via `fit_prenorm()`.
        """
        for m in [self.g_C, self.g_V, self.f_C, self.f_V]:
            m.reset_parameters()

    def _edge_input(self, h_c, h_v, edge_v2c, edge_attr):
        """Build per-edge input: cat(c_i, v_j [, e_ij]) for every edge."""
        var_idx, cons_idx = edge_v2c[0], edge_v2c[1]
        parts = [h_c[cons_idx], h_v[var_idx]]
        if edge_attr is not None:
            parts.append(edge_attr)
        return torch.cat(parts, dim=-1)

    @torch.no_grad()
    def fit_prenorm(self, h_v, h_c, edge_v2c, edge_attr=None):
        """Compute prenorm statistics from representative node embeddings.

        Should be called once per layer, in order, before training starts.
        """
        var_idx, cons_idx = edge_v2c[0], edge_v2c[1]
        n_cons, n_var = h_c.size(0), h_v.size(0)
        msg = self._edge_input(h_c, h_v, edge_v2c, edge_attr)
        self.prenorm_C.fit(_scatter_sum(self.g_C(msg), cons_idx, n_cons))
        self.prenorm_V.fit(_scatter_sum(self.g_V(msg), var_idx, n_var))

    def forward(self, h_v, h_c, edge_v2c, edge_attr=None):
        var_idx, cons_idx = edge_v2c[0], edge_v2c[1]
        n_cons, n_var = h_c.size(0), h_v.size(0)

        # C-side half-convolution (V -> C)
        msg = self._edge_input(h_c, h_v, edge_v2c, edge_attr)
        agg_C = self.prenorm_C(_scatter_sum(self.g_C(msg), cons_idx, n_cons))
        h_c = relu(self.f_C(torch.cat([h_c, agg_C], dim=-1)))

        # V-side half-convolution (C -> V, uses freshly updated h_c)
        msg = self._edge_input(h_c, h_v, edge_v2c, edge_attr)
        agg_V = self.prenorm_V(_scatter_sum(self.g_V(msg), var_idx, n_var))
        h_v = relu(self.f_V(torch.cat([h_v, agg_V], dim=-1)))

        return h_v, h_c


class GasseGNN(torch.nn.Module):
    """Bipartite GCNN from Gasse et al. (NeurIPS 2019).

    Architecture:
        1. Initial embedding — one Linear per node type (V → V^1, C → C^1).
        2. L x GasseBipartiteConv with alternating half-convolutions.
        3. Final 2-layer MLP head on variable nodes.

    Before training, call `fit_prenorm()` once with a representative data
    batch to initialise the prenorm layers inside each conv.

    Edge features are passed via the optional `edge_attr` argument.

    Parameters
    ----------
    var_in_dim  : number of variable node input features.
    cons_in_dim : number of constraint node input features.
    edge_dim    : number of edge features (0 = edges carry no features).
    hidden_dim  : embedding size (64 in the paper).
    num_layers  : number of GasseBipartiteConv layers (1 in the paper).
    output_activation : applied to the final output. Default None -> the model
        returns raw logits, the right input for `BCEWithLogitsLoss`. Set to
        `torch.sigmoid` only if you need probabilities straight out of forward.
    """

    def __init__(
        self,
        var_in_dim,
        cons_in_dim,
        edge_dim=0,
        hidden_dim=64,
        num_layers=1,
        output_activation=None,
    ):
        super().__init__()

        self.var_encoder = Linear(var_in_dim, hidden_dim)
        self.cons_encoder = Linear(cons_in_dim, hidden_dim)

        self.convs = torch.nn.ModuleList(
            [
                GasseBipartiteConv(hidden_dim, hidden_dim, edge_dim, hidden_dim)
                for _ in range(num_layers)
            ]
        )

        self.head = _MLP2(hidden_dim, hidden_dim, 1)
        self.output_activation = output_activation

    def reset_parameters(self):
        """Re-initialise all trainable weights.

        Does not touch the prenorm buffers, so `fit_prenorm()` must be called
        again afterwards before training.
        """
        self.var_encoder.reset_parameters()
        self.cons_encoder.reset_parameters()
        for conv in self.convs:
            conv.reset_parameters()
        self.head.reset_parameters()

    def fit_prenorm(self, x_var, x_cons, edge_v2c, edge_attr=None):
        """Fit prenorm statistics layer by layer from representative data.

        Pass a single representative batch (or the full training set).
        This must be called after model creation and before training.
        """
        with torch.no_grad():
            h_v = relu(self.var_encoder(x_var))
            h_c = relu(self.cons_encoder(x_cons))
            for conv in self.convs:
                conv.fit_prenorm(h_v, h_c, edge_v2c, edge_attr)
                h_v, h_c = conv(h_v, h_c, edge_v2c, edge_attr)

    def forward(
        self, x_var, x_cons, edge_v2c, binary_mask, edge_attr=None, var_batch=None
    ):
        # var_batch is accepted only for a uniform, swappable interface with
        # LiangBiGNN (which needs it to mask attention per graph). GasseGNN is
        # fully edge-driven, so it neither needs nor uses it.
        h_v = relu(self.var_encoder(x_var))
        h_c = relu(self.cons_encoder(x_cons))

        for conv in self.convs:
            h_v, h_c = conv(h_v, h_c, edge_v2c, edge_attr)

        out = torch.squeeze(self.head(h_v[binary_mask]), -1)
        if self.output_activation is not None:
            out = self.output_activation(out)
        return out
