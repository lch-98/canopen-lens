# 배포 절차 (PyPI)

PyPI 업로드는 GitHub Actions가 대신 합니다. API 토큰을 저장소에 넣지 않는 "Trusted Publishing" 방식이라
처음 한 번만 아래 설정을 해 두면, 이후에는 태그만 올리면 됩니다.

## 처음 한 번

1. GitHub에 `lch-98/canopen-lens` 저장소를 만들고 이 폴더를 push 합니다.
   ```bash
   git remote add origin https://github.com/lch-98/canopen-lens.git
   git push -u origin main
   ```
2. GitHub 저장소 → **Settings → Environments → New environment** 에서 이름을 `pypi` 로 만듭니다.
3. https://pypi.org 에 로그인 → 계정 메뉴 **Your projects → Publishing** →
   **Add a new pending publisher** 에 아래 값을 넣습니다.

   | 항목 | 값 |
   |---|---|
   | PyPI Project Name | `canopen-lens` |
   | Owner | `lch-98` |
   | Repository name | `canopen-lens` |
   | Workflow name | `release.yml` |
   | Environment name | `pypi` |

## (선택) TestPyPI로 먼저 연습하기

PyPI에는 같은 버전 번호를 **한 번만** 올릴 수 있고, 지워도 같은 번호로 다시 올릴 수 없습니다.
그래서 처음에는 연습용 서버인 TestPyPI(https://test.pypi.org, 계정 따로 만들어야 함)에 먼저 올려 보는 것을 권장합니다.

1. GitHub 저장소 → **Settings → Environments** 에서 `testpypi` 환경도 하나 더 만듭니다.
2. https://test.pypi.org → **Your projects → Publishing → Add a new pending publisher** 에 위 표와 같은 값을 넣되,
   Environment name 만 `testpypi` 로 적습니다.
3. GitHub → **Actions → Release → Run workflow** 에서 **testpypi** 칸을 체크하고 실행합니다.
4. 끝나면 아무 PC에서 설치해 봅니다 (의존 패키지는 진짜 PyPI에서 받도록 `--extra-index-url` 을 붙입니다).
   ```bash
   pip install -i https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ "canopen-lens[gui]"
   canopen-lens
   ```

## 매 릴리스

1. `pyproject.toml` 의 `version` 과 `src/canopen_lens/__init__.py` 의 `__version__` 을 같은 값으로 올립니다.
2. 커밋 후 태그를 push 합니다.
   ```bash
   git tag v0.5.0
   git push origin v0.5.0
   ```
3. GitHub → **Actions → Release** 가 자동으로 다음을 합니다.
   - Linux x86_64 / aarch64, Windows x64용 **휠**을 빌드해 PyPI에 올림 → `pip install canopen-lens`가 컴파일 없이 설치됨
   - Python 없이 실행되는 **앱**(Windows `.zip`, Linux x86_64·aarch64 `.tar.gz`)을 PyInstaller로 만들고, 실행 자체 테스트(`--self-test`)를 통과한 것만 GitHub Release에 첨부

태그 없이 빌드만 확인하고 싶으면 **Actions → Release → Run workflow** 를 누르면 됩니다 (업로드는 하지 않음).

## 앱을 직접 만들어 보기

```bash
pip install ".[gui]" pyinstaller        # -e (편집 모드) 설치로는 C++ 모듈이 포함되지 않음
pyinstaller packaging/canopen-lens.spec --noconfirm
dist/CANopenLens/CANopenLens --self-test
```

## 로컬 확인

```bash
pip install -e ".[gui,test,pandas,live]"
pytest
python -m build          # dist/ 에 sdist 와 현재 플랫폼용 휠 생성
```
