# Signal Flow Live 기술적 의사결정

이 문서는 포트폴리오 관점에서 "무엇을 만들었는가"보다 "왜 그렇게 설계했는가"를 설명하기 위해 작성했습니다.

## 1. Shared Client Contract를 먼저 잡은 이유

많은 프로젝트가 REST 리소스를 먼저 쪼개고, 프론트엔드가 화면별로 여러 API를 조합하도록 만듭니다. 이 방식은 초기에는 빠르지만, web과 app client가 늘어날수록 동일한 조합 로직이 여러 곳에 중복됩니다.

이 프로젝트에서는 처음부터 아래 세 endpoint를 product contract로 잡았습니다.

- `GET /api/client/bootstrap`
- `GET /api/client/dashboard`
- `GET /api/client/assets/{symbol}`

이 구조를 택한 이유:

- web, PWA, app-style client가 같은 payload를 그대로 재사용할 수 있습니다.
- 프론트엔드가 "데이터 조합기"가 아니라 "표현 계층"에 가까워집니다.
- 향후 클라이언트가 늘어나도 API shape가 비교적 안정적으로 유지됩니다.

tradeoff:

- endpoint 하나가 다루는 책임이 커질 수 있습니다.
- 단순 CRUD 스타일보다 payload 설계 난도가 높습니다.

그래도 제품 단위 개발에서는 이 쪽이 더 실용적이라고 판단했습니다.

## 2. Fallback을 부가 기능이 아니라 핵심 구조로 둔 이유

시장 데이터 프로젝트는 외부 소스 품질에 크게 의존합니다. 따라서 "정상 상황만 잘 되는 구조"는 실제 사용에서 취약합니다.

이 프로젝트에서는 fallback을 핵심 런타임 정책으로 넣었습니다.

- Upbit live source 실패 시 simulator fallback
- scanner provider 실패 시 synthetic fallback
- fallback 이후 원래 provider 재시도

이렇게 한 이유:

- 서비스가 완전히 멈추는 것보다, 품질을 낮춰서라도 계속 동작하는 편이 실무적으로 낫습니다.
- 사용자와 운영자에게 현재 source 상태를 보여줄 수 있습니다.
- 장애 시나리오를 코드와 UI 양쪽에서 설명할 수 있습니다.

## 3. Scanner Runtime을 별도 계층으로 분리한 이유

실시간 crypto와 watch-only 주식/ETF는 데이터 특성이 다릅니다.

- crypto: 실시간 stream 중심
- stock/ETF: scanner refresh 중심

이를 하나의 동일한 runtime으로 억지로 처리하면 조건 분기가 과도해지고, 정책도 섞입니다. 그래서 scanner runtime을 별도 계층으로 분리했습니다.

장점:

- scanner 전용 metadata를 명확히 관리할 수 있습니다.
- delayed/session 정책을 독립적으로 적용할 수 있습니다.
- provider 추가나 교체가 쉬워집니다.

## 4. Signal Delivery Semantics를 세분화한 이유

알림 시스템에서 "보냈다 / 안 보냈다"만 기록하면 운영과 UX 모두 불친절합니다. 이 프로젝트에서는 signal이 만들어진 뒤 어떤 상태였는지를 의미론적으로 나눴습니다.

- `notified`
- `suppressed`
- `no_subscribers`

그리고 `notification_delivery_reason`으로 이유를 같이 남깁니다.

예시:

- `scanner_delayed_blocked`
- `scanner_session_blocked:pre`
- `web_notifications_disabled`
- `email_only_delivery_not_implemented`

이렇게 한 이유:

- 운영자는 "왜 알림이 안 나갔는지"를 바로 해석할 수 있습니다.
- 사용자는 product behavior를 납득할 수 있습니다.
- 단순 boolean보다 훨씬 디버깅 친화적입니다.

## 5. SQLite 기본 + PostgreSQL 확장 구조를 택한 이유

초기 MVP는 빠른 실행과 단순성이 중요합니다. SQLite는 로컬 개발과 데모 환경에서 생산성이 높습니다. 하지만 포트폴리오에서는 "성장 가능성"도 보여줘야 합니다.

그래서:

- 기본 실행은 SQLite
- 데이터 접근은 SQLAlchemy
- 스키마 진화는 Alembic
- 배포 경로는 PostgreSQL-ready

로 구조를 잡았습니다.

이 선택의 의미:

- 빠른 MVP 개발
- migration discipline 유지
- production 전환 가능성 확보

## 6. 테스트를 기능 검증보다 계약 검증까지 확장한 이유

이 프로젝트는 단순 함수 테스트보다 제품 계약 검증이 중요하다고 봤습니다. 그래서 아래를 테스트 대상으로 삼았습니다.

- client API contract
- scanner runtime behavior
- fallback / recovery behavior
- signal delivery policy
- web shell 정적 구조
- migration / DB behavior

특히 time-dependent bug를 테스트로 고정한 것은 포트폴리오에서 좋은 포인트입니다. "테스트가 있다"보다 "실제 깨졌던 테스트를 안정화했다"가 더 실무적이기 때문입니다.
