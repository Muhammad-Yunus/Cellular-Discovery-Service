import subprocess
import json
import logging
import shutil
import os
import threading
from typing import Optional
from app.cli.exceptions import CLIError, CLITimeoutError, CLIParseError, CLINotFoundError
from app.cli.schemas import CLIScanResponse, CLIScanResult

logger = logging.getLogger(__name__)

# Module-level lock so only one CLI scan invocation runs at a time.
# The LTE modem (e.g., /dev/ttyUSB0) is a shared resource — concurrent scans
# will interfere with each other and may cause SIGTERM or data corruption.
# Serialise all CLIAdapter instances to ensure atomic execution.
_cli_cli_lock = threading.Lock()


class CLIAdapter:
    def __init__(self, command: str = "lte-discovery"):
        self.command = command

    def _find_command(self) -> str:
        if shutil.which(self.command):
            return self.command
        raise CLINotFoundError(self.command)

    def execute(self, port: str, timeout: int = 30) -> CLIScanResponse:
        # Test-only fault injection: MOCK_CLI_FAIL=<truthy> raises a CLIError so
        # the executor exercises the SCAN_ERROR -> SKIPPED branch (S06).
        # Top-level import so the module instance is shared between
        # test_management (PUT endpoint) and adapter (CLI execute) — lazy import
        # was masking the global counter in some test runs.
        MOCK_CLI_FAIL = os.environ.get("MOCK_CLI_FAIL")
        if MOCK_CLI_FAIL:
            from app.gps.test_management import _decrement_cli_fail
            should_fail = _decrement_cli_fail()
            if should_fail:
                raise CLIError(
                    f"Simulated CLI failure (MOCK_CLI_FAIL={MOCK_CLI_FAIL})"
                )

        with _cli_cli_lock:
            cmd = self._find_command()
            args = [cmd, "scan", "--port", port, "--json"]

            logger.info(f"Executing CLI: {' '.join(args)}")

            try:
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as e:
                logger.error(f"CLI timed out after {timeout}s")
                logger.warning("CLI timed out, returning empty results")
                return CLIScanResponse(results=[], raw_output=f"{{\"error\": \"timeout\", \"port\": \"{port}}}")
            except FileNotFoundError as e:
                raise CLINotFoundError(self.command)

            logger.info(f"CLI completed with return code {result.returncode}")

            if result.returncode != 0:
                logger.error(f"CLI error: {result.stderr}")
                # Don't raise error on non-zero return, just log and return empty
                return CLIScanResponse(results=[], raw_output=result.stderr)

            return self._parse_output(result.stdout)

    def _parse_output(self, stdout: str) -> CLIScanResponse:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise CLIParseError(
                f"Failed to parse CLI output as JSON: {e}",
                raw_output=stdout,
            )

        # Handle both formats: raw list [...] or object {"results": [...]}
        if isinstance(data, list):
            scan_results = data
        elif isinstance(data, dict):
            scan_results = data.get("results", data.get("networks", []))
            if not isinstance(scan_results, list):
                raise CLIParseError(
                    "Expected 'results' or 'networks' to be a list",
                    raw_output=stdout,
                )
        else:
            raise CLIParseError(
                f"Unexpected JSON type: {type(data).__name__}, expected list or dict",
                raw_output=stdout,
            )

        results = []
        for item in scan_results:
            results.append(
                CLIScanResult(
                    operator_name=item.get("operator_name", item.get("operator")),
                    mcc=item.get("mcc"),
                    mnc=item.get("mnc"),
                    rat=item.get("rat"),
                    status=item.get("status"),
                )
            )

        return CLIScanResponse(results=results, raw_output=stdout)
