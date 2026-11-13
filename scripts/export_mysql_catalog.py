"""1,500개 추천 카탈로그를 MySQL에 넣을 수 있는 SQL로 변환합니다."""

from __future__ import annotations

import argparse
import ast
import csv
from pathlib import Path


def sql_string(value: str | None) -> str:
    if value is None or not value.strip():
        return "NULL"
    escaped = value.replace("\\", "\\\\").replace("'", "''")
    return f"'{escaped}'"


def sql_number(value: str | None, *, integer: bool = False) -> str:
    if value is None or not value.strip():
        return "NULL"
    return str(int(float(value))) if integer else str(float(value))


def parse_labels(raw: str) -> list[str]:
    labels = ast.literal_eval(raw) if raw else []
    if not isinstance(labels, list):
        raise ValueError("categories and mechanics must be lists")
    return [str(label).strip() for label in labels if str(label).strip()]


def export(source: Path) -> None:
    print("SET NAMES utf8mb4;")
    print("START TRANSACTION;")
    with source.open(encoding="utf-8", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            categories = parse_labels(row["categories"])
            mechanics = parse_labels(row["mechanics"])
            primary_category = categories[0] if categories else "Board Game"
            values = [
                sql_number(row["item_id"], integer=True),
                sql_number(row["bgg_id"], integer=True),
                sql_string(row["name"]),
                sql_string(primary_category),
                sql_number(row["min_players"], integer=True),
                sql_number(row["max_players"], integer=True),
                sql_number(row["min_playtime"], integer=True),
                sql_number(row["max_playtime"], integer=True),
                sql_number(row["min_age"], integer=True),
                sql_number(row["year_published"], integer=True),
                sql_number(row["complexity"]),
                sql_number(row["average_rating"]),
            ]
            print(
                "INSERT INTO board_games "
                "(dataset_item_id, bgg_id, name_en, category, min_players, max_players, "
                "min_play_time_minutes, max_play_time_minutes, min_age, year_published, "
                "difficulty, average_rating) VALUES "
                f"({', '.join(values)}) AS incoming "
                "ON DUPLICATE KEY UPDATE "
                "bgg_id=incoming.bgg_id, name_en=incoming.name_en, category=incoming.category, "
                "min_players=incoming.min_players, max_players=incoming.max_players, "
                "min_play_time_minutes=incoming.min_play_time_minutes, "
                "max_play_time_minutes=incoming.max_play_time_minutes, min_age=incoming.min_age, "
                "year_published=incoming.year_published, difficulty=incoming.difficulty, "
                "average_rating=incoming.average_rating;"
            )
            for category in categories:
                print(
                    "INSERT IGNORE INTO board_game_categories (board_game_id, category) "
                    f"SELECT id, {sql_string(category)} FROM board_games "
                    f"WHERE dataset_item_id = {values[0]};"
                )
            for mechanic in mechanics:
                print(
                    "INSERT IGNORE INTO board_game_mechanics (board_game_id, mechanic) "
                    f"SELECT id, {sql_string(mechanic)} FROM board_games "
                    f"WHERE dataset_item_id = {values[0]};"
                )
    print("COMMIT;")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "games.csv",
    )
    export(parser.parse_args().source)
