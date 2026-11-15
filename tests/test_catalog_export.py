import csv
from io import StringIO
from pathlib import Path

from scripts.export_mysql_catalog import (
    build_description,
    choose_placeholder,
    parse_labels,
    write_catalog_sql,
)


DATASET = Path(__file__).parents[1] / "data" / "games.csv"


def test_build_description_uses_only_catalog_metadata() -> None:
    row = {
        "min_players": "2",
        "max_players": "4",
        "max_playtime": "45",
        "complexity": "2.4",
    }

    description = build_description(row, ["Adventure"], ["Cooperative Game"])

    assert description == (
        "2~4명이 약 45분 동안 즐기는 적당한 난이도의 보드게임입니다. "
        "모험 요소와 협력 방식을 중심으로 진행합니다."
    )


def test_build_description_handles_unknown_player_and_time_limits() -> None:
    row = {
        "min_players": "2",
        "max_players": "0",
        "max_playtime": "0",
        "complexity": "3.5",
    }

    description = build_description(row, [], [])

    assert description == "2명 이상이 즐기는 깊이 있는 난이도의 보드게임입니다."


def test_catalog_uses_all_placeholder_themes() -> None:
    placeholders = set()
    with DATASET.open(encoding="utf-8", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            placeholders.add(
                choose_placeholder(parse_labels(row["categories"]), parse_labels(row["mechanics"]))
            )

    assert placeholders == {
        "/assets/placeholders/adventure.jpg",
        "/assets/placeholders/building.jpg",
        "/assets/placeholders/family.jpg",
        "/assets/placeholders/history.jpg",
        "/assets/placeholders/mystery.jpg",
        "/assets/placeholders/party.jpg",
        "/assets/placeholders/scifi.jpg",
        "/assets/placeholders/strategy.jpg",
    }


def test_full_catalog_exports_1500_repeatable_inserts() -> None:
    output = StringIO()

    count = write_catalog_sql(DATASET, output)
    sql = output.getvalue()

    assert count == 1500
    assert sql.count("INSERT INTO board_games ") == 1500
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert "description_ko" in sql
    assert "COMMIT;" in sql
