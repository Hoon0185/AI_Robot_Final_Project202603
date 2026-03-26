# 📑 AWS Lightsail 기반 Gilbot 데이터 관리 시스템 배포 보고서 (Step 3)

## 🏆 배포 개요 (Deployment Summary)
본 문서는 Gilbot 프로젝트의 3단계(Phase 3) 과업인 **"데이터 관리 시스템(Admin Dashboard) 및 phpMyAdmin 구축"**에 대한 최종 전이 및 실전 배포 결과를 기록합니다.

- **배포 서버**: AWS Lightsail (Ubuntu 24.04 Noble)
- **접속 IP**: `16.184.56.119`
- **배포 일시**: 2026년 3월 26일
- **상태**: **[DEPLOYED / OPERATIONAL]**

---

## 🏗️ 시스템 구성 (System Architecture)

### 1. ⚔️ 데이터 통제실 (Admin Dashboard Room)
재조정된 React 프론트엔드를 통해 실시간 상품 마스터 데이터 및 순찰 로그를 관리합니다.
- **접속 경로**: `http://16.184.56.119/` -> 사이드바 '⚙️ DB 관리' 탭
- **주요 기능**:
  - 상품 정보(이름, 바코드, 수량, 카테고리) 실시간 CRUD 연동
  - 순찰 기록 위험 분석 및 개별/전체 로그 삭제 기능
  - FastAPI 백엔드와 MySQL DB의 Schema 동기화 (Column Name 보정 완료)

### 2. 🏥 DB 정비소 (phpMyAdmin)
데이터베이스 로우(Raw) 레벨의 정밀 유지보수를 위한 웹 기반 관리 도구를 설치하였습니다.
- **접속 경로**: `http://16.184.56.119/phpmyadmin/index.php`
- **ID / PW**: `gilbot` / `robot123`
- **기반 기술**: PHP 8.3 & Apache mod_php 활성화

---

## 📡 데이터베이스 보안 및 접속 정보 (Security & Auth)
| 구분 | 내용 | 비고 |
| :--- | :--- | :--- |
| **DB User** | `gilbot` | 로컬/AWS 통합 계정 |
| **DB Password** | `robot123` | 사령부 공용 비밀번호 |
| **DB Name** | `gilbot` | 메인 워크스페이스 |

---

## 🩹 주요 이슈 해결 및 보정 사항 (Fixes)
- **PHP 8.3 활성화**: Apache가 PHP를 텍스트로 노출하던 현상을 `libapache2-mod-php` 설치 및 `php_force.conf` 설정을 통해 해결.
- **Alias 핸들러 충돌**: phpMyAdmin 경로에 대한 PHP 직접 핸들러(`AddType`)를 할당하여 접근성 확보.
- **Front-Back 싱크**: 상품 등록 시 `product_name`, `standard_qty` 등의 스키마 칼럼 불일치를 FastAPI Pydantic 모델 수정을 통해 완벽 보정.

---

## 🔗 노션(Notion) 지휘부 동기화 상태
- **상태**: Connected
- **Master Action DB**: `[Final Project] 편의점 매대 관리 프로젝트` (Step 3 완료)
- **지식 DB**: `📑 Gilbot 데이터 관리 시스템 및 phpMyAdmin 실전 구축 가이드` (발행 완료)
