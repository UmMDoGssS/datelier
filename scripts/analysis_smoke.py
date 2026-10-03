import json

import numpy as np

from datelier.feasibility.analysis import Algorithm, prepare_input, run_probe
from datelier.feasibility.fixtures import make_table


def main() -> None:
    inputs = prepare_input(make_table(64, 3))
    algorithms: tuple[Algorithm, ...] = ("pca", "tsne", "umap", "kmeans")
    report = []
    for algorithm in algorithms:
        result = run_probe(algorithm, inputs)
        if not np.isfinite(result.values).all():
            raise RuntimeError(f"Nonfinite {algorithm} compatibility result")
        report.append(
            {
                "algorithm": algorithm,
                "shape": result.values.shape,
                "dtype": str(result.values.dtype),
                "finite": True,
                "elapsed_seconds": result.elapsed_seconds,
                "parameters": result.parameters,
                "included_row_ids": result.row_ids.tolist(),
                "features": ["feature_0", "feature_1", "feature_2"],
                "source_rows": 64,
            }
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
