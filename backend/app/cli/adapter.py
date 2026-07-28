import subprocess
import json
import logging
import shutil
import os
from typing import Optional
from app.cli.exceptions import CLIError, CLITimeoutError, CLIParseError, CLINotFoundError
from app.cli.schemas import CLIScanResponse, CLIScanResult

logger = logging.getLogger(__name__)


class CLIAdapter:
    def __init__(self, command: str = "lte-discovery", mock_mode: bool = False):
        self.command = command
        self.mock_mode = mock_mode or os.getenv("LTE_DISCOVERY MOCK", "false").lower() == "true"

    def _find_command(self) -> str:
        if shutil.which(self.command):
            return self.command
        raise CLINotFoundError(self.command)

    def execute(self, port: str, timeout: int = 30) -> CLIScanResponse:
        if self.mock_mode:
            # Return simulated scan results for development/testing
            logger.info("Mock mode: Returning simulated scan results")
            simulated_results = [
                CLIScanResult(
                    operator_name="Telkomsel",
                    mcc="525",
                    mnc="01",
                    rat="LTE",
                    status="connected",
                ),
                CLIScanResult(
                    operator_name="Indosat",
                    mcc="525",
                    mnc="06",
                    rat="LTE",
                    status="available",
                ),
                CLIScanResult(
                    operator_name="XL Axiata",
                    mcc="525",
                    mnc="08",
                    rat="LTE",
                    status="available",
                ),
            ]
            return CLIScanResponse(
                results=simulated_results,
                raw_output='{"results": simulated_results, "timestamp": "now"}'
            )

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
            # In non-mock mode on timeout, return empty results to avoid hanging frontend
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
