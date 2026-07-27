import subprocess
import json
import logging
import shutil
from typing import Optional
from app.cli.exceptions import CLIError, CLITimeoutError, CLIParseError, CLINotFoundError
from app.cli.schemas import CLIScanResponse, CLIScanResult

logger = logging.getLogger(__name__)


class CLIAdapter:
    def __init__(self, command: str = "lte-discovery"):
        self.command = command

    def _find_command(self) -> str:
        if shutil.which(self.command):
            return self.command
        raise CLINotFoundError(self.command)

    def execute(self, port: str, timeout: int = 30) -> CLIScanResponse:
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
            raise CLITimeoutError(timeout, str(e))
        except FileNotFoundError as e:
            raise CLINotFoundError(self.command)

        logger.info(f"CLI completed with return code {result.returncode}")

        if result.returncode != 0:
            logger.error(f"CLI error: {result.stderr}")
            raise CLIError(
                f"CLI exited with code {result.returncode}",
                stderr=result.stderr,
            )

        return self._parse_output(result.stdout)

    def _parse_output(self, stdout: str) -> CLIScanResponse:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            raise CLIParseError(
                f"Failed to parse CLI output as JSON: {e}",
                raw_output=stdout,
            )

        results = []
        scan_results = data.get("results", data.get("networks", []))

        if not isinstance(scan_results, list):
            raise CLIParseError(
                "Expected 'results' or 'networks' to be a list",
                raw_output=stdout,
            )

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
