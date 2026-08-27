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
# The RTL-SDR device is a shared resource — concurrent scans will interfere.
# Serialise all CLIAdapter instances to ensure atomic execution.
_cli_cli_lock = threading.Lock()


class CLIAdapter:
    def __init__(self, command: str = "lte-scan"):
        self.command = command

    def _find_command(self) -> str:
        if shutil.which(self.command):
            return self.command
        raise CLINotFoundError(self.command)

    def execute(self, band: int, timeout: int = 30) -> CLIScanResponse:
        # Test-only fault injection: MOCK_CLI_FAIL=<truthy> raises a CLIError
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
            # lte-scan [mode] [band] --json --gain N
            args = [cmd, "balance", str(band), "--json", "--gain", "43"]

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
                return CLIScanResponse(results=[], raw_output=f'{{"error": "timeout", "band": "{band}"}}')
            except FileNotFoundError as e:
                raise CLINotFoundError(self.command)

            logger.info(f"CLI completed with return code {result.returncode}")

            if result.returncode != 0:
                logger.error(f"CLI error: {result.stderr}")
                return CLIScanResponse(results=[], raw_output=result.stderr)

            return self._parse_output(result.stdout, band)

    def _parse_output(self, stdout: str, band: int) -> CLIScanResponse:
        # lte-scan outputs a status line before JSON and may append text after
        # (e.g. "Running lte_scan_example..." and "Result saved to:...")
        # Find the JSON block by locating the first '{' or '[' and matching the
        # corresponding closing bracket/brace.
        first_brace = stdout.find('{')
        first_bracket = stdout.find('[')
        if first_brace == -1 and first_bracket == -1:
            raise CLIParseError(
                "Failed to parse CLI output as JSON: no JSON object found",
                raw_output=stdout,
            )
        # Prefer '{' if it comes first, otherwise '['
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            start_char, end_char = '{', '}'
            json_start = first_brace
        else:
            start_char, end_char = '[', ']'
            json_start = first_bracket

        json_str = stdout[json_start:]
        depth = 0
        end = 0
        for i, c in enumerate(json_str):
            if c == start_char:
                depth += 1
            elif c == end_char:
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if end == 0:
            raise CLIParseError(
                "Failed to parse CLI output as JSON: unmatched braces",
                raw_output=stdout,
            )
        try:
            data = json.loads(json_str[:end])
        except json.JSONDecodeError as e:
            raise CLIParseError(
                f"Failed to parse CLI output as JSON: {e}",
                raw_output=stdout,
            )

        # Handle lte-scan output format
        if isinstance(data, dict):
            cells = data.get("cells", [])
        elif isinstance(data, list):
            cells = data
        else:
            raise CLIParseError(
                f"Unexpected JSON type: {type(data).__name__}, expected dict or list",
                raw_output=stdout,
            )

        results = []
        for cell in cells:
            # Map lte-scan fields to CLIScanResult
            operator = cell.get("operator") or cell.get("operator_name")
            mcc = str(cell.get("mcc", ""))
            mnc = str(cell.get("mnc", ""))

            # Derive RAT from band
            rat = self._band_to_rat(band)

            results.append(
                CLIScanResult(
                    operator_name=operator,
                    mcc=mcc,
                    mnc=mnc,
                    rat=rat,
                    status="Available",  # RTL-SDR detects available cells
                    frequency_mhz=cell.get("frequency_mhz"),
                    earfcn=cell.get("earfcn"),
                    band=cell.get("band"),
                    pci=cell.get("pci"),
                    rsrp=cell.get("rsrp"),
                    rsrq=cell.get("rsrq"),
                    snr=cell.get("snr"),
                )
            )

        return CLIScanResponse(results=results, raw_output=stdout)

    def _band_to_rat(self, band: int) -> str:
        """Map LTE band to RAT type."""
        rat_map = {
            4: "LTE",
            5: "LTE",
            8: "LTE",
            20: "LTE",
            40: "LTE",
        }
        return rat_map.get(band, "LTE")
