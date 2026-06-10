import torch
from torch.nn import Linear
from torch.nn.functional import relu
from torch_geometric.utils import to_dense_batch

from .gasse import GasseBipartiteConv, _Prenorm

# --------------------------------------------------------------------------- #
# Liang et al. (2024) - BiGNN / BiGNN+ATT                                    #
# --------------------------------------------------------------------------- #


class _SelfAttention(torch.nn.Module):
    """Scaled dot-product self-attention (Liang et al. 2024, Section 3.4).

    Att = softmax( Q K^T / sqrt(d) ) V
    where Q, K, V = Y W_Q, Y W_K, Y W_V.

    When a `batch` vector is supplied (node -> graph index, as produced by PyG
    when several graphs are batched together), each graph attends only to
    itself. The nodes are regrouped into a dense (num_graphs, max_nodes, d)
    tensor so attention runs per graph: this keeps memory at O(max_nodes^2)
    per graph instead of O(total_nodes^2) over the whole batch, which matters
    once instances are large. Without `batch`, a single graph is assumed.
    """

    def __init__(self, dim):
        super().__init__()
        self.W_Q = Linear(dim, dim, bias=False)
        self.W_K = Linear(dim, dim, bias=False)
        self.W_V = Linear(dim, dim, bias=False)
        self.scale = dim**0.5

    def reset_parameters(self):
        for w in [self.W_Q, self.W_K, self.W_V]:
            w.reset_parameters()

    def forward(self, x, batch=None):
        Q = self.W_Q(x)  # (n, d)
        K = self.W_K(x)  # (n, d)
        V = self.W_V(x)  # (n, d)

        if batch is None:
            # Single graph: plain full attention over all n nodes.
            scores = (Q @ K.T) / self.scale  # (n, n)
            attn = torch.softmax(scores, dim=-1)
            return attn @ V  # (n, d)

        # Several graphs batched together: regroup into (B, max_n, d) so each
        # graph attends only within itself. `mask` marks real (non-padded) nodes.
        Q, mask = to_dense_batch(Q, batch)  # (B, max_n, d), (B, max_n)
        K, _ = to_dense_batch(K, batch)
        V, _ = to_dense_batch(V, batch)

        scores = (Q @ K.transpose(-1, -2)) / self.scale  # (B, max_n, max_n)
        # Stop real queries from attending to padded key positions.
        scores = scores.masked_fill(~mask.unsqueeze(1), float("-inf"))
        attn = torch.softmax(scores, dim=-1)
        out = attn @ V  # (B, max_n, d)
        return out[mask]  # back to (n, d), original node order


class LiangBiGNN(torch.nn.Module):
    """BiGNN (optionally BiGNN+ATT) from Liang et al. (2024).

    Differences from GasseGNN:
        1. Encoder: 2 x (Linear + PreNorm + ReLU) per node type instead of
           a single Linear, giving richer initial embeddings.
        2. Optional self-attention block on variable embeddings after the BGN
           (set `use_attention=True` for the BiGNN+ATT variant).

    The BGN core is the same `GasseBipartiteConv` as in `GasseGNN`, so
    `fit_prenorm()` works identically. The forward signature is also
    compatible with `GasseGNN` (both accept an optional `var_batch`).

    When `use_attention=True` and several graphs are batched together, pass
    `var_batch` (the variable-node -> graph index, i.e. `batch['var'].batch`
    in PyG) so the self-attention stays block-diagonal per graph.

    Parameters
    ----------
    var_in_dim    : number of variable node input features.
    cons_in_dim   : number of constraint node input features.
    edge_dim      : number of edge features (0 = no edge features).
    hidden_dim    : embedding size.
    num_layers    : number of GasseBipartiteConv (BGN) layers.
    use_attention : if True, adds self-attention after the BGN (BiGNN+ATT).
    output_activation : applied to the final scalar output. Default None -> the
        model returns raw logits, the right input for `BCEWithLogitsLoss`. Set
        to `torch.sigmoid` only if you need probabilities straight out of forward.
    """

    def __init__(
        self,
        var_in_dim,
        cons_in_dim,
        edge_dim=0,
        hidden_dim=64,
        num_layers=1,
        use_attention=False,
        output_activation=None,
    ):
        super().__init__()
        self.use_attention = use_attention

        # 2-layer encoder with fixed prenorm between the two steps
        self.var_enc1 = Linear(var_in_dim, hidden_dim)
        self.var_pn1 = _Prenorm(hidden_dim)
        self.var_enc2 = Linear(hidden_dim, hidden_dim)
        self.var_pn2 = _Prenorm(hidden_dim)

        self.cons_enc1 = Linear(cons_in_dim, hidden_dim)
        self.cons_pn1 = _Prenorm(hidden_dim)
        self.cons_enc2 = Linear(hidden_dim, hidden_dim)
        self.cons_pn2 = _Prenorm(hidden_dim)

        self.convs = torch.nn.ModuleList(
            [
                GasseBipartiteConv(hidden_dim, hidden_dim, edge_dim, hidden_dim)
                for _ in range(num_layers)
            ]
        )

        self.attention = _SelfAttention(hidden_dim) if use_attention else None

        self.head = Linear(hidden_dim, 1)
        self.output_activation = output_activation

    def reset_parameters(self):
        """Re-initialise all trainable weights.

        Does not touch the prenorm buffers, so `fit_prenorm()` must be called
        again afterwards before training.
        """
        for m in [
            self.var_enc1,
            self.var_enc2,
            self.cons_enc1,
            self.cons_enc2,
            self.head,
        ]:
            m.reset_parameters()
        for conv in self.convs:
            conv.reset_parameters()
        if self.attention is not None:
            self.attention.reset_parameters()

    def _encode(self, x_var, x_cons):
        h_v = relu(self.var_pn1(self.var_enc1(x_var)))
        h_v = relu(self.var_pn2(self.var_enc2(h_v)))
        h_c = relu(self.cons_pn1(self.cons_enc1(x_cons)))
        h_c = relu(self.cons_pn2(self.cons_enc2(h_c)))
        return h_v, h_c

    def fit_prenorm(self, x_var, x_cons, edge_v2c, edge_attr=None):
        """Fit prenorm statistics for encoder and BGN layers.

        Must be called once with a representative batch before training.
        """
        with torch.no_grad():
            # Encoder prenorms: fitted from raw projected activations
            h_v0 = self.var_enc1(x_var)
            self.var_pn1.fit(h_v0)
            h_v1 = relu(self.var_pn1(h_v0))
            h_v1 = self.var_enc2(h_v1)
            self.var_pn2.fit(h_v1)
            h_v = relu(self.var_pn2(h_v1))

            h_c0 = self.cons_enc1(x_cons)
            self.cons_pn1.fit(h_c0)
            h_c1 = relu(self.cons_pn1(h_c0))
            h_c1 = self.cons_enc2(h_c1)
            self.cons_pn2.fit(h_c1)
            h_c = relu(self.cons_pn2(h_c1))

            # BGN prenorms
            for conv in self.convs:
                conv.fit_prenorm(h_v, h_c, edge_v2c, edge_attr)
                h_v, h_c = conv(h_v, h_c, edge_v2c, edge_attr)

    def forward(
        self, x_var, x_cons, edge_v2c, binary_mask, edge_attr=None, var_batch=None
    ):
        h_v, h_c = self._encode(x_var, x_cons)

        for conv in self.convs:
            h_v, h_c = conv(h_v, h_c, edge_v2c, edge_attr)

        if self.attention is not None:
            h_v = self.attention(h_v, var_batch)

        out = torch.squeeze(self.head(h_v[binary_mask]), -1)
        if self.output_activation is not None:
            out = self.output_activation(out)
        return out
