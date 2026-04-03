# Signal Flow Live 트러블슈팅

이 문서는 프로젝트를 만들면서 실제로 손봤던 문제와 해결 방식을 정리한 문서입니다.

## 1. Scanner Fallback 후 원래 Provider로 복구되지 않던 문제

### 문제

scanner provider가 한 번 실패하면 synthetic fallback으로 전환되는데, 이후 원래 provider가 복구되어도 계속 synthetic만 사용하는 문제가 있었습니다.

### 원인

fallback 이후 현재 provider 인스턴스만 유지하고, requested provider를 다시 시도하는 경로가 없었습니다.

### 해결

- refresh 시점에 현재 provider가 synthetic이고 requested provider가 다르면 원래 provider를 다시 생성해서 재시도하도록 수정했습니다.
- fallback과 recovery 모두 테스트 케이스로 고정했습니다.

### 배운 점

fallback은 "한 번 내려간다"만 구현하면 끝이 아니라, "언제 어떻게 복구할 것인가"까지 같이 설계해야 합니다.

## 2. Signal Feed가 오래된 유효 신호를 놓치던 문제

### 문제

`recent signals`가 먼저 최신 N개를 잘라온 다음 필터링해서, 조건이 강한 경우 실제로는 더 아래에 있는 유효 신호를 놓칠 수 있었습니다.

### 원인

조회와 필터링의 순서가 잘못되어 있었습니다.

### 해결

- signal feed를 배치 단위로 계속 스캔하도록 변경했습니다.
- 원하는 개수가 찰 때까지 다음 batch를 읽게 만들었습니다.
- 관련 회귀 테스트를 추가했습니다.

### 배운 점

검색/피드 API에서는 "최근 N개"와 "필터 결과 N개"가 다를 수 있다는 점을 분리해서 설계해야 합니다.

## 3. Raw Candles API의 시간 순서가 뒤집혀 있던 문제

### 문제

DB에서 recent candles를 이미 ascending으로 가져오는데, API에서 다시 reverse 처리해서 다른 화면과 순서가 달라지는 문제가 있었습니다.

### 원인

DB contract와 API contract를 동시에 고려하지 않고 중복 정렬을 적용했습니다.

### 해결

- raw candles endpoint에서 불필요한 reverse를 제거했습니다.
- 응답이 항상 ascending인지 검증하는 테스트를 추가했습니다.

### 배운 점

정렬 책임은 DB, service, API 중 어디에 둘지 명확히 정해야 합니다.

## 4. Notification Setting PATCH가 갱신값을 반환하지 않던 문제

### 문제

notification settings를 PATCH해도 API 응답이 갱신된 값을 돌려주지 않아, client가 다시 dashboard를 읽기 전까지 상태를 확신할 수 없었습니다.

### 원인

DB update 함수가 값을 저장만 하고 return 하지 않았습니다.

### 해결

- update 이후 최신 settings를 반환하도록 수정했습니다.
- API test로 갱신값과 저장값을 동시에 검증했습니다.

### 배운 점

설정 API는 side effect만 일으키는 endpoint보다, 바로 반영된 상태를 응답하는 쪽이 클라이언트 설계에 유리합니다.

## 5. 날짜가 바뀌면 깨지는 테스트 문제

### 문제

scanner seed나 provider test가 특정 날짜를 가정하고 있어서, 현재 시간이 바뀌면 테스트가 실패할 수 있었습니다.

### 원인

테스트가 `utc_now()`에 암묵적으로 의존하고 있었습니다.

### 해결

- 테스트에서 `db.utc_now()`를 고정된 시간으로 monkeypatch 했습니다.
- time-sensitive fixture를 명시적으로 freeze해서 재현 가능한 테스트로 만들었습니다.

### 배운 점

시간은 외부 의존성입니다. DB, 네트워크와 마찬가지로 test seam을 통해 고정해야 합니다.

## 6. Signal Delivery Semantics가 사용자에게 충분히 설명되지 않던 문제

### 문제

`no_subscribers`는 있었지만, 왜 알림이 안 나갔는지 구체적이지 않았습니다.

### 원인

delivery 상태를 시스템 내부 이벤트로만 보고, 사용자/운영자 설명 레이어를 충분히 만들지 않았습니다.

### 해결

- audience summary를 추가했습니다.
- `web_notifications_disabled`, `email_only_delivery_not_implemented`, `no_watchlist_subscribers` 같은 구체 이유를 남기도록 바꿨습니다.
- UI에서도 사람이 읽을 수 있는 문구로 변환해 보여주도록 수정했습니다.

### 배운 점

좋은 제품 로직은 "맞게 동작하는 것"에서 끝나지 않고, "왜 그렇게 동작했는지 설명 가능해야" 합니다.
