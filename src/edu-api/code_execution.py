import asyncio
import json
from dataclasses import dataclass
from urllib import error, request

LANGUAGE_ALIASES = {
    "python": "python",
    "cpp": "c++",
    "java": "java",
    "javascript": "javascript",
    "go": "go",
}


class CodeExecutionError(RuntimeError):
    """Raised when the configured sandbox cannot execute a submission."""


@dataclass(frozen=True)
class CodeExecutionResult:
    language: str
    version: str
    stdout: str
    stderr: str
    output: str
    exit_code: int | None
    signal: str | None


def _post_execution_request(
    *,
    api_url: str,
    api_token: str,
    language: str,
    code: str,
    stdin: str,
    timeout_seconds: float,
) -> dict:
    payload = json.dumps(
        {
            "language": LANGUAGE_ALIASES[language],
            "version": "*",
            "files": [{"content": code}],
            "stdin": stdin,
            "compile_timeout": 10000,
            "run_timeout": 5000,
            "compile_memory_limit": 256_000_000,
            "run_memory_limit": 256_000_000,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    http_request = request.Request(
        api_url, data=payload, headers=headers, method="POST"
    )
    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            body = response.read(1_000_001)
    except error.HTTPError as exc:
        detail = exc.read(2000).decode("utf-8", errors="replace")
        raise CodeExecutionError(
            f"代码沙箱返回 HTTP {exc.code}: {detail or exc.reason}"
        ) from exc
    except (error.URLError, TimeoutError) as exc:
        raise CodeExecutionError("无法连接代码沙箱服务。") from exc

    if len(body) > 1_000_000:
        raise CodeExecutionError("代码沙箱返回内容过大。")
    try:
        result = json.loads(body)
    except json.JSONDecodeError as exc:
        raise CodeExecutionError("代码沙箱返回了无法识别的数据。") from exc
    if not isinstance(result, dict):
        raise CodeExecutionError("代码沙箱返回了无法识别的数据。")
    return result


async def execute_code(
    *,
    api_url: str,
    api_token: str,
    language: str,
    code: str,
    stdin: str,
    timeout_seconds: float,
) -> CodeExecutionResult:
    payload = await asyncio.to_thread(
        _post_execution_request,
        api_url=api_url,
        api_token=api_token,
        language=language,
        code=code,
        stdin=stdin,
        timeout_seconds=timeout_seconds,
    )
    compile_result = payload.get("compile")
    run_result = payload.get("run")
    if not isinstance(compile_result, dict) and not isinstance(run_result, dict):
        detail = payload.get("message") or payload.get("error")
        if isinstance(detail, dict):
            detail = detail.get("message")
        raise CodeExecutionError(
            str(detail) if detail else "代码沙箱未返回编译或运行结果。"
        )
    compile_result = compile_result if isinstance(compile_result, dict) else {}
    run_result = run_result if isinstance(run_result, dict) else {}

    compile_stdout = str(compile_result.get("stdout") or "")
    compile_stderr = str(compile_result.get("stderr") or "")
    run_stdout = str(run_result.get("stdout") or "")
    run_stderr = str(run_result.get("stderr") or "")
    output = str(run_result.get("output") or "")
    if not output:
        output = "".join(
            part
            for part in (compile_stdout, compile_stderr, run_stdout, run_stderr)
            if part
        )

    raw_code = run_result.get("code", compile_result.get("code"))
    exit_code = raw_code if isinstance(raw_code, int) else None
    raw_signal = run_result.get("signal", compile_result.get("signal"))

    return CodeExecutionResult(
        language=str(payload.get("language") or language),
        version=str(payload.get("version") or ""),
        stdout=f"{compile_stdout}{run_stdout}",
        stderr=f"{compile_stderr}{run_stderr}",
        output=output,
        exit_code=exit_code,
        signal=str(raw_signal) if raw_signal else None,
    )
