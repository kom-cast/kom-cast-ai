## OpenAI 프롬프트 테스트

`scripts/check_openai_connection.py`를 실행하면 실제 OpenAI API를 호출하여 현재 설정된 프롬프트와 API 연결 상태를 확인할 수 있습니다.

> 이 테스트는 실제 OpenAI API를 호출하므로 API 사용량과 비용이 발생할 수 있습니다.

### 1. 저장소 복제

```bash
git clone <repository-url>
cd script-service
```

`<repository-url>`에는 이 GitHub 저장소의 주소를 입력합니다.

예시:

```bash
git clone https://github.com/<username>/<repository-name>.git
cd <repository-name>
```

### 2. 가상환경 생성

#### Windows

```powershell
py -m venv .venv
```

#### macOS / Linux

```bash
python3 -m venv .venv
```

### 3. 가상환경 활성화

#### Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

PowerShell 실행 정책 오류가 발생하면 현재 터미널에서 다음 명령어를 먼저 실행합니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

그다음 가상환경을 다시 활성화합니다.

```powershell
.venv\Scripts\Activate.ps1
```

#### Windows 명령 프롬프트

```cmd
.venv\Scripts\activate.bat
```

#### macOS / Linux

```bash
source .venv/bin/activate
```

가상환경이 정상적으로 활성화되면 터미널 앞에 `(.venv)`가 표시됩니다.

### 4. 의존성 설치

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 5. 환경변수 설정

프로젝트 루트에 `.env` 파일을 생성합니다.

```text
script-service/
├── app/
├── scripts/
├── test/
├── .env
└── requirements.txt
```

`.env` 파일에 OpenAI API 키와 필요한 설정을 입력합니다.

```env
OPENAI_API_KEY=your-openai-api-key
```

모델 이름을 환경변수로 관리하고 있다면 함께 입력합니다.

```env
OPENAI_MODEL=gpt-5-mini
```

실제 환경변수 이름은 `app/config.py`의 `OpenAiSettings` 설정과 동일해야 합니다.

보안을 위해 `.env` 파일은 GitHub에 커밋하지 않습니다. `.gitignore`에 다음 항목이 포함되어 있는지 확인합니다.

```gitignore
.env
.venv/
```

### 6. OpenAI 연결 및 프롬프트 테스트 실행

프로젝트 루트에서 다음 명령어를 실행합니다.

```bash
python -m scripts.check_openai_connection
```

Windows에서 `python` 명령어가 인식되지 않는 경우 다음 명령어를 사용할 수 있습니다.

```powershell
py -m scripts.check_openai_connection
```

정상적으로 실행되면 OpenAI API가 생성한 스크립트가 터미널에 출력됩니다.

### 실행 위치 주의

명령어는 반드시 `app`, `scripts` 디렉터리가 존재하는 프로젝트 루트에서 실행해야 합니다.

올바른 위치:

```text
script-service/
├── app/
├── scripts/
└── ...
```

```bash
python -m scripts.check_openai_connection
```

잘못된 예:

```text
script-service/scripts/
```

```bash
python check_openai_connection.py
```

`python -m` 방식은 프로젝트 루트를 Python 모듈 탐색 경로에 포함하므로 다음과 같은 프로젝트 내부 import를 정상적으로 처리할 수 있습니다.

```python
from app.ai_client import create_openai_client
```

### 테스트 종료 후 가상환경 비활성화

```bash
deactivate
```
