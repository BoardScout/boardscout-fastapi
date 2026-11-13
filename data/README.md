# Recommendation dataset

`games.csv`는 `/Users/hanhalam/temp/ML_RecSys/data/experiment_10k/games.csv`에서 가져온
BoardGameGeek Reviews v3 기반 1,500개 게임 카탈로그입니다.

- 런타임 모델에는 게임 메타데이터만 포함합니다.
- 사용자 평점 `train/validation/test.csv`는 약 90만 행이며 오프라인 Item CF 및
  Matrix Factorization 실험용이므로 API 이미지에 넣지 않습니다.
- `item_id`는 프런트의 `likedGameIds`와 동일한 0부터 시작하는 ID입니다.
- 원본 데이터의 재배포 및 운영 사용 전에는 BoardGameGeek API 약관과 Kaggle 데이터셋
  라이선스를 다시 확인해야 합니다.

현재 모델은 서버 시작 시 카테고리와 메커니즘의 TF-IDF 통계를 계산합니다. `MY TASTE`는
평점 학습 결과인 `models/item_neighbors.json`도 함께 사용합니다. 이 파일은 다음 명령으로
다시 만들 수 있습니다.

```bash
python scripts/build_item_neighbors.py \
  /path/to/ML_RecSys/data/experiment_10k/train.csv \
  data/models/item_neighbors.json
```

MySQL 기본 카탈로그는 다음처럼 반복 실행해도 안전하게 적재할 수 있습니다. 한국어 이름·설명과
이미지 URL은 BGG API 승인 뒤 별도 보강하며, 이 명령은 기존 현지화 필드를 덮어쓰지 않습니다.

```bash
python scripts/export_mysql_catalog.py \
  | docker exec -i boardscout-mysql sh -lc \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
```
