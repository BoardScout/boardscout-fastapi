"""평점 CSV에서 게임별 adjusted-cosine 이웃을 한 번 계산한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import sparse


def build_neighbors(
    train_path: Path,
    output_path: Path,
    users: int = 10_000,
    items: int = 1_500,
    keep: int = 40,
) -> None:
    # 평점이 없는 조합을 0점으로 채우지 않도록 희소 행렬로 보관한다.
    rows = np.loadtxt(train_path, delimiter=",", skiprows=1, dtype=np.float32)
    ratings = sparse.csr_matrix(
        (rows[:, 2], (rows[:, 0].astype(int), rows[:, 1].astype(int))),
        shape=(users, items),
    )
    counts = np.asarray(ratings.getnnz(axis=1)).ravel()
    means = np.divide(
        np.asarray(ratings.sum(axis=1)).ravel(),
        counts,
        out=np.zeros(users),
        where=counts > 0,
    )
    centered = ratings.astype(np.float32, copy=True)
    # 사용자의 후한 평가와 박한 평가 차이를 제거한 뒤 게임끼리 비교한다.
    centered.data -= np.repeat(means, np.diff(centered.indptr))

    gram = (centered.T @ centered).toarray()
    norms = np.sqrt(np.maximum(np.diag(gram), 0))
    similarity = np.divide(
        gram,
        np.outer(norms, norms),
        out=np.zeros_like(gram),
        where=np.outer(norms, norms) > 0,
    )
    binary = ratings.copy()
    binary.data[:] = 1
    overlap = (binary.T @ binary).toarray()
    # 함께 평가한 사용자가 적은 게임 쌍은 우연한 유사도가 커지지 않도록 낮춘다.
    similarity *= overlap / (overlap + 250)
    similarity[overlap < 10] = 0
    similarity[similarity < 0] = 0
    np.fill_diagonal(similarity, 0)

    neighbors = {}
    # API에는 전체 유사도 행렬 대신 게임별 상위 이웃만 전달한다.
    for item_id, scores in enumerate(similarity):
        candidates = np.flatnonzero(scores)
        selected = candidates[np.argsort(scores[candidates])[-keep:]][::-1]
        neighbors[str(item_id)] = [[int(other), round(float(scores[other]), 6)] for other in selected]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"strategy": "adjusted-cosine", "neighbors": neighbors}, separators=(",", ":")),
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BGG 평점으로 게임별 추천 이웃을 계산합니다.")
    parser.add_argument("train", type=Path, help="학습 평점 CSV 경로")
    parser.add_argument("output", type=Path, help="생성할 이웃 JSON 경로")
    args = parser.parse_args()
    build_neighbors(args.train, args.output)
