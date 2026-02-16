"""
Model evaluator — computes Precision@K, Recall@K, NDCG@K, and MAP.
"""

from __future__ import annotations

import numpy as np
import structlog

logger = structlog.get_logger()


def precision_at_k(recommended: list[int], relevant: set[int], k: int) -> float:
    """Precision@K — fraction of recommended items that are relevant."""
    if k == 0:
        return 0.0
    rec_at_k = recommended[:k]
    hits = sum(1 for r in rec_at_k if r in relevant)
    return hits / k


def recall_at_k(recommended: list[int], relevant: set[int], k: int) -> float:
    """Recall@K — fraction of relevant items that are recommended."""
    if not relevant:
        return 0.0
    rec_at_k = recommended[:k]
    hits = sum(1 for r in rec_at_k if r in relevant)
    return hits / len(relevant)


def ndcg_at_k(recommended: list[int], relevant: set[int], k: int) -> float:
    """Normalized Discounted Cumulative Gain @K."""
    if not relevant or k == 0:
        return 0.0

    rec_at_k = recommended[:k]
    dcg = sum(1.0 / np.log2(i + 2) for i, r in enumerate(rec_at_k) if r in relevant)
    ideal_dcg = sum(1.0 / np.log2(i + 2) for i in range(min(len(relevant), k)))
    return dcg / ideal_dcg if ideal_dcg > 0 else 0.0


def mean_average_precision(
    recommendations_per_user: dict[int, list[int]],
    relevant_per_user: dict[int, set[int]],
) -> float:
    """Mean Average Precision across all users."""
    aps = []
    for user_id, recommended in recommendations_per_user.items():
        relevant = relevant_per_user.get(user_id, set())
        if not relevant:
            continue

        hits = 0
        precision_sum = 0.0
        for i, item in enumerate(recommended):
            if item in relevant:
                hits += 1
                precision_sum += hits / (i + 1)

        ap = precision_sum / len(relevant) if relevant else 0.0
        aps.append(ap)

    return float(np.mean(aps)) if aps else 0.0


def evaluate_model(
    model,
    user_item_matrix,
    train_interactions: dict[int, set[int]],
    test_interactions: dict[int, set[int]],
    k: int = 10,
) -> dict:
    """
    Evaluate a recommendation model using standard IR metrics.
    Returns dict of aggregated metrics.
    """
    precisions = []
    recalls = []
    ndcgs = []
    recommendations_for_map = {}
    relevant_for_map = {}

    for user_id, relevant_items in test_interactions.items():
        if not relevant_items:
            continue

        # Get recommendations (this is model-agnostic)
        try:
            if hasattr(model, "recommend"):
                # implicit-style model
                item_indices, _ = model.recommend(user_id, user_item_matrix[user_id], N=k)
                recommended = item_indices.tolist()
            else:
                continue
        except Exception:
            continue

        precisions.append(precision_at_k(recommended, relevant_items, k))
        recalls.append(recall_at_k(recommended, relevant_items, k))
        ndcgs.append(ndcg_at_k(recommended, relevant_items, k))
        recommendations_for_map[user_id] = recommended
        relevant_for_map[user_id] = relevant_items

    metrics = {
        f"precision@{k}": float(np.mean(precisions)) if precisions else 0.0,
        f"recall@{k}": float(np.mean(recalls)) if recalls else 0.0,
        f"ndcg@{k}": float(np.mean(ndcgs)) if ndcgs else 0.0,
        "map": mean_average_precision(recommendations_for_map, relevant_for_map),
        "n_users_evaluated": len(precisions),
    }

    logger.info("model_evaluation", **metrics)
    return metrics
