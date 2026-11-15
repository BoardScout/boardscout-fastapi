"""추천 카탈로그를 반복 실행 가능한 MySQL 시드 SQL로 변환합니다."""

from __future__ import annotations

import argparse
import ast
import csv
import sys
from contextlib import nullcontext
from pathlib import Path
from typing import TextIO


PLACEHOLDER_BASE_PATH = "/assets/placeholders"

CATEGORY_LABELS = {
    "Abstract Strategy": "추상 전략",
    "Adventure": "모험",
    "Animals": "동물",
    "Ancient": "고대 문명",
    "Bluffing": "블러핑",
    "Card Game": "카드",
    "Children's Game": "어린이",
    "City Building": "도시 건설",
    "Civilization": "문명",
    "Deduction": "추리",
    "Economic": "경제",
    "Educational": "교육",
    "Exploration": "탐험",
    "Fantasy": "판타지",
    "Farming": "농장 경영",
    "Fighting": "대결",
    "Horror": "공포",
    "Industry / Manufacturing": "산업",
    "Math": "수리",
    "Medical": "의학",
    "Medieval": "중세",
    "Memory": "기억력",
    "Murder/Mystery": "미스터리",
    "Negotiation": "협상",
    "Party Game": "파티",
    "Political": "정치",
    "Puzzle": "퍼즐",
    "Racing": "경주",
    "Science Fiction": "과학 소설",
    "Space Exploration": "우주 탐사",
    "Territory Building": "영역 건설",
    "Trains": "철도",
    "Transportation": "운송",
    "Travel": "여행",
    "Trivia": "상식 퀴즈",
    "Wargame": "전쟁 전략",
    "Word Game": "단어",
}

MECHANIC_LABELS = {
    "Action Points": "액션 포인트",
    "Area Majority / Influence": "영역 영향력",
    "Area Movement": "영역 이동",
    "Auction/Bidding": "경매",
    "Campaign / Battle Card Driven": "카드 중심 캠페인",
    "Card Drafting": "카드 드래프트",
    "Cooperative Game": "협력",
    "Deck, Bag, and Pool Building": "덱·백 빌딩",
    "Dice Rolling": "주사위",
    "Grid Movement": "격자 이동",
    "Hand Management": "핸드 관리",
    "Hexagon Grid": "육각 타일",
    "Modular Board": "모듈형 보드",
    "Network and Route Building": "노선 건설",
    "Pattern Building": "패턴 만들기",
    "Pattern Recognition": "패턴 인식",
    "Pick-up and Deliver": "운송",
    "Player Elimination": "플레이어 탈락",
    "Point to Point Movement": "지점 이동",
    "Push Your Luck": "운 시험",
    "Role Playing": "역할 수행",
    "Roll / Spin and Move": "주사위 이동",
    "Set Collection": "세트 수집",
    "Simultaneous Action Selection": "동시 행동 선택",
    "Storytelling": "이야기 만들기",
    "Tile Placement": "타일 배치",
    "Trading": "교환",
    "Variable Player Powers": "고유 능력",
    "Voting": "투표",
    "Worker Placement": "일꾼 놓기",
}

THEME_RULES = (
    ("scifi", {"science fiction", "space exploration"}, {"space exploration"}),
    (
        "mystery",
        {"deduction", "horror", "murder/mystery", "spies/secret agents"},
        {"deduction", "hidden roles", "secret unit deployment"},
    ),
    (
        "party",
        {"bluffing", "humor", "negotiation", "party game"},
        {"acting", "singing", "storytelling", "team-based game", "voting"},
    ),
    (
        "family",
        {"animals", "children's game", "educational", "racing", "sports"},
        {"memory", "paper-and-pencil", "roll / spin and move"},
    ),
    (
        "history",
        {
            "american civil war",
            "american revolutionary war",
            "american west",
            "ancient",
            "civil war",
            "medieval",
            "modern warfare",
            "napoleonic",
            "political",
            "prehistoric",
            "renaissance",
            "wargame",
            "world war i",
            "world war ii",
        },
        {"campaign / battle card driven", "chit-pull system"},
    ),
    (
        "building",
        {
            "city building",
            "economic",
            "farming",
            "industry / manufacturing",
            "territory building",
            "trains",
            "transportation",
        },
        {
            "deck, bag, and pool building",
            "network and route building",
            "pick-up and deliver",
            "worker placement",
        },
    ),
    (
        "adventure",
        {"adventure", "exploration", "fantasy", "fighting", "mythology", "zombies"},
        {"role playing", "storytelling"},
    ),
)


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


def choose_placeholder(categories: list[str], mechanics: list[str]) -> str:
    """카테고리와 메커니즘을 이용해 가장 가까운 플레이스홀더를 고릅니다."""

    normalized_categories = {label.casefold() for label in categories}
    normalized_mechanics = {label.casefold() for label in mechanics}
    for theme, category_terms, mechanic_terms in THEME_RULES:
        if normalized_categories & category_terms or normalized_mechanics & mechanic_terms:
            return f"{PLACEHOLDER_BASE_PATH}/{theme}.jpg"
    return f"{PLACEHOLDER_BASE_PATH}/strategy.jpg"


def translated_labels(labels: list[str], translations: dict[str, str], limit: int = 2) -> str:
    # 번역이 준비된 용어만 사용해 한국어 설명 안에 영문 분류명이 섞이지 않게 합니다.
    translated = [translations[label] for label in labels if label in translations]
    return "·".join(translated[:limit])


def build_description(row: dict[str, str], categories: list[str], mechanics: list[str]) -> str:
    """원본 메타데이터만 사용해 과장 없는 한국어 카탈로그 설명을 만듭니다."""

    min_players = int(float(row["min_players"]))
    max_players = int(float(row["max_players"]))
    if max_players == 0:
        players = f"{min_players}명 이상이"
    elif min_players == max_players:
        players = f"{min_players}명이"
    else:
        players = f"{min_players}~{max_players}명이"
    max_playtime = int(float(row["max_playtime"]))
    complexity = float(row["complexity"])
    difficulty = "가벼운" if complexity < 1.8 else "적당한" if complexity < 2.8 else "깊이 있는"

    duration = f" 약 {max_playtime}분 동안" if max_playtime > 0 else ""
    sentences = [f"{players}{duration} 즐기는 {difficulty} 난이도의 보드게임입니다."]
    category_text = translated_labels(categories, CATEGORY_LABELS)
    mechanic_text = translated_labels(mechanics, MECHANIC_LABELS)
    if category_text and mechanic_text:
        sentences.append(f"{category_text} 요소와 {mechanic_text} 방식을 중심으로 진행합니다.")
    elif category_text:
        sentences.append(f"{category_text} 요소를 중심으로 진행합니다.")
    elif mechanic_text:
        sentences.append(f"{mechanic_text} 방식을 중심으로 진행합니다.")
    return " ".join(sentences)


def write_catalog_sql(source: Path, output: TextIO) -> int:
    """CSV 전체를 SQL로 쓰고 적재한 게임 수를 반환합니다."""

    print("-- Generated by fastapi-server/scripts/export_mysql_catalog.py", file=output)
    print("-- Source: fastapi-server/data/games.csv", file=output)
    print("SET NAMES utf8mb4;", file=output)
    print("START TRANSACTION;", file=output)
    count = 0
    with source.open(encoding="utf-8", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            categories = parse_labels(row["categories"])
            mechanics = parse_labels(row["mechanics"])
            primary_category = categories[0] if categories else "Board Game"
            description = build_description(row, categories, mechanics)
            placeholder = choose_placeholder(categories, mechanics)
            values = [
                sql_number(row["item_id"], integer=True),
                sql_number(row["bgg_id"], integer=True),
                sql_string(row["name"]),
                "NULL",
                sql_string(description),
                sql_string(placeholder),
                sql_string(placeholder),
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
                "(dataset_item_id, bgg_id, name_en, name_ko, description_ko, image_url, "
                "thumbnail_url, category, min_players, max_players, min_play_time_minutes, "
                "max_play_time_minutes, min_age, year_published, difficulty, average_rating) VALUES "
                f"({', '.join(values)}) AS incoming "
                "ON DUPLICATE KEY UPDATE "
                "bgg_id=incoming.bgg_id, name_en=incoming.name_en, category=incoming.category, "
                "min_players=incoming.min_players, max_players=incoming.max_players, "
                "min_play_time_minutes=incoming.min_play_time_minutes, "
                "max_play_time_minutes=incoming.max_play_time_minutes, min_age=incoming.min_age, "
                "year_published=incoming.year_published, difficulty=incoming.difficulty, "
                "average_rating=incoming.average_rating, "
                "description_ko=COALESCE(board_games.description_ko, incoming.description_ko), "
                "image_url=COALESCE(board_games.image_url, incoming.image_url), "
                "thumbnail_url=COALESCE(board_games.thumbnail_url, incoming.thumbnail_url);",
                file=output,
            )
            for category in categories:
                print(
                    "INSERT IGNORE INTO board_game_categories (board_game_id, category) "
                    f"SELECT id, {sql_string(category)} FROM board_games "
                    f"WHERE dataset_item_id = {values[0]};",
                    file=output,
                )
            for mechanic in mechanics:
                print(
                    "INSERT IGNORE INTO board_game_mechanics (board_game_id, mechanic) "
                    f"SELECT id, {sql_string(mechanic)} FROM board_games "
                    f"WHERE dataset_item_id = {values[0]};",
                    file=output,
                )
            count += 1
    print("COMMIT;", file=output)
    return count


def export(source: Path, destination: Path | None = None) -> int:
    context = destination.open("w", encoding="utf-8", newline="\n") if destination else nullcontext(sys.stdout)
    with context as output:
        return write_catalog_sql(source, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "games.csv",
    )
    parser.add_argument("--output", type=Path, help="생성한 SQL을 저장할 경로")
    arguments = parser.parse_args()
    exported = export(arguments.source, arguments.output)
    if arguments.output:
        print(f"{exported} games exported to {arguments.output}")
