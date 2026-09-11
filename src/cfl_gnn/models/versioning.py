"""Explicit model selection without rewriting historical checkpoint identities."""
VERSIONS = ("legacy", "gasse_v2_alternating_prenorm")


def model_class(version="legacy"):
    if version == "legacy":
        from cfl_gnn.models.gasse import GasseGNN
    elif version == VERSIONS[1]:
        from cfl_gnn.models.gasse_calibrated import GasseGNN
    else:
        raise ValueError(f"unsupported model version: {version}")
    return GasseGNN


def fit_versioned_prenorm(model, version, training_dataset, representative, device):
    if version == VERSIONS[1]:
        from cfl_gnn.models.gasse_calibrated import fit_training_prenorm
        return fit_training_prenorm(model, training_dataset, device)
    if version != "legacy":
        raise ValueError("unsupported model version")
    edge = representative["variable", "rev_coef", "constraint"]
    model.fit_prenorm(representative["variable"].x, representative["constraint"].x,
                      edge.edge_index, edge.edge_attr)
    return {"model_version": "legacy", "training_graphs": 1,
            "method": "historical_representative_graph", "validation_or_test_used": False}
