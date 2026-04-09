# Vite(Node.js 빌드 도구) 사용 안내서

본 프로젝트의 프론트엔드(`web-ui`)는 현대적이고 빠른 빌드 도구인 **Vite**를 사용하여 개발 및 빌드됩니다. Vite는 개발 시에는 압도적인 속도의 개발 서버를 제공하고, 배포 시에는 최적화된 정적 자산(Static Assets)을 생성합니다.

## 1. Vite의 역할

1.  **개발 서버 (Development Server)**: 로컬 개발 시 코드를 수정하면 즉시 브라우저에 반영되는 **HMR(Hot Module Replacement)** 기능을 제공합니다.
2.  **번들링 (Bundling)**: React, 모듈형 CSS, 이미지 등을 하나의 최적화된 JavaScript 및 CSS 파일로 묶어줍니다.
3.  **프록시 (Proxy)**: 개발 환경에서 백엔드 API 서버(`:8000`)와의 통신을 원활하게 하기 위해 자체적인 프록시 기능을 수행합니다.

## 2. 개발 모드 (`npm run dev`)

개발 시에는 Node.js 환경에서 Vite 개발 서버를 실행합니다.

-   **실행 명령어**: `npm run dev` (내부적으로 `vite` 실행)
-   **기본 포트**: `5173`
-   **작동 원리**:
    -   브라우저에서 `http://localhost:5173`으로 접속합니다.
    -   코드 수정 시 전체 페이지 새로고침 없이 변경된 모듈만 즉시 업데이트됩니다.
-   **개발용 프록시 설정 (`vite.config.js`)**:
    ```javascript
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      }
    }
    ```
    *참고: 개발 중에는 아파치를 거치지 않고 Vite 서버가 직접 `/api` 요청을 FastAPI로 전달합니다.*

## 3. 빌드 모드 (`npm run build`) 및 배포

실제 운영 환경(Apache)에서는 Node.js를 실행하지 않고, Vite를 통해 미리 구워진(Pre-built) 정적 파일만을 사용합니다.

1.  **빌드 실행**: `npm run build` (내부적으로 `vite build` 실행)
2.  **결과물 생성**: `web-ui/dist/` 폴더에 `index.html`, `js`, `css` 파일들이 생성됩니다.
3.  **아파치 연동**: 아파치의 `DocumentRoot`가 이 `dist/` 폴더를 바라보도록 설정됩니다.
    -   관련 설정: `/etc/apache2/sites-enabled/gilbot.conf`
    -   자세한 아파치 연동 방식은 [아파치-FastAPI 연동 가이드](./apache_fastapi_proxy.md)를 참고하세요.

## 4. 왜 Vite(Node.js)를 사용하는가?

-   **생산성**: 복잡한 React 컴포넌트 구조를 브라우저가 이해할 수 있는 형태로 자동 변환해 줍니다.
-   **최적화**: 코드 스플리팅(Code Splitting), 트리 쉐이킹(Tree Shaking) 등을 통해 실제 사용자에게 전달되는 파일 크기를 최소화합니다.
-   **유연성**: 개발 환경에서는 편리한 개발 도구를 사용하고, 운영 환경에서는 가볍고 빠른 정적 파일로 서빙할 수 있는 하이브리드 구조를 가능하게 합니다.
