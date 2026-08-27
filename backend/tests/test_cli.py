import pytest
from unittest.mock import patch, MagicMock
from app.cli.adapter import CLIAdapter
from app.cli.exceptions import CLIError, CLITimeoutError, CLIParseError, CLINotFoundError


class TestCLIAdapter:
    def setup_method(self):
        self.adapter = CLIAdapter(command="lte-scan")

    @patch("app.cli.adapter.shutil.which", return_value="/usr/bin/lte-scan")
    def test_find_command_success(self, mock_which):
        result = self.adapter._find_command()
        assert result == "lte-scan"

    @patch("app.cli.adapter.shutil.which", return_value=None)
    def test_find_command_not_found(self, mock_which):
        with pytest.raises(CLINotFoundError):
            self.adapter._find_command()

    @patch("app.cli.adapter.subprocess.run")
    @patch("app.cli.adapter.shutil.which", return_value="/usr/bin/lte-scan")
    def test_execute_success(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"cells": [{"operator": "Telkomsel", "mcc": 510, "mnc": 10}]}',
            stderr="",
        )

        result = self.adapter.execute(band=8, timeout=30)

        assert len(result.results) == 1
        assert result.results[0].operator_name == "Telkomsel"
        assert result.results[0].mcc == "510"
        assert result.results[0].rat == "LTE"

    @patch("app.cli.adapter.subprocess.run")
    @patch("app.cli.adapter.shutil.which", return_value="/usr/bin/lte-scan")
    def test_execute_timeout(self, mock_which, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("lte-scan balance 8 --json --gain 43", timeout=30)

        # Should catch exception and return empty results
        result = self.adapter.execute(band=8, timeout=30)
        assert len(result.results) == 0

    @patch("app.cli.adapter.subprocess.run")
    @patch("app.cli.adapter.shutil.which", return_value="/usr/bin/lte-scan")
    def test_execute_non_zero_exit(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error message",
        )

        result = self.adapter.execute(band=8, timeout=30)

        # On non-zero exit, adapter returns empty results instead of raising error
        assert len(result.results) == 0
        assert "Error message" in result.raw_output

    def test_parse_output_valid_json_dict(self):
        stdout = '{"cells": [{"operator": "Telkomsel", "mcc": 510, "mnc": 10}]}'
        result = self.adapter._parse_output(stdout, band=8)

        assert len(result.results) == 1
        assert result.results[0].operator_name == "Telkomsel"
        assert result.results[0].mcc == "510"

    def test_parse_output_valid_json_list(self):
        stdout = '[{"operator": "XL", "mcc": 510, "mnc": 11}]'
        result = self.adapter._parse_output(stdout, band=8)

        assert len(result.results) == 1
        assert result.results[0].operator_name == "XL"

    def test_parse_output_invalid_json(self):
        stdout = "not json"

        with pytest.raises(CLIParseError):
            self.adapter._parse_output(stdout, band=8)

    def test_parse_output_empty_results(self):
        stdout = '{"cells": []}'
        result = self.adapter._parse_output(stdout, band=8)
        assert len(result.results) == 0

    def test_parse_output_raw_list_format(self):
        """Test that raw JSON list format is handled correctly"""
        stdout = '[{"operator": "Telkomsel", "mcc": 510, "mnc": 10}]'
        result = self.adapter._parse_output(stdout, band=8)
        assert len(result.results) == 1
        assert result.results[0].operator_name == "Telkomsel"

    def test_parse_output_raw_empty_list(self):
        """Test that empty raw list is handled correctly"""
        stdout = '[]'
        result = self.adapter._parse_output(stdout, band=8)
        assert len(result.results) == 0

    def test_parse_output_missing_fields(self):
        """Test that missing fields are handled gracefully"""
        stdout = '{"cells": [{"mcc": 510, "mnc": 10}]}'
        result = self.adapter._parse_output(stdout, band=8)
        assert len(result.results) == 1
        assert result.results[0].operator_name is None

    def test_band_to_rat(self):
        assert self.adapter._band_to_rat(8) == "LTE"
        assert self.adapter._band_to_rat(4) == "LTE"
        assert self.adapter._band_to_rat(5) == "LTE"
        assert self.adapter._band_to_rat(20) == "LTE"
        assert self.adapter._band_to_rat(40) == "LTE"
        assert self.adapter._band_to_rat(99) == "LTE"  # Default

    # ------------------------------------------------------------------
    # Mock CLI Fault Injection Tests (S06)
    # ------------------------------------------------------------------

    def test_mock_cli_fail_enabled(self, monkeypatch):
        """Test that CLIError is raised when MOCK_CLI_FAIL is set"""
        import os
        from unittest.mock import patch
        from app.gps import test_management

        monkeypatch.setenv("MOCK_CLI_FAIL", "1")
        monkeypatch.setattr(test_management, "_cli_fail_remaining", 1)

        with patch("app.cli.adapter.subprocess.run"):
            with patch("app.cli.adapter.shutil.which", return_value="/usr/bin/lte-scan"):
                with pytest.raises(CLIError, match="Simulated CLI failure"):
                    self.adapter.execute(band=8, timeout=10)

    def test_mock_cli_fail_disabled(self, monkeypatch):
        """Test that no error when MOCK_CLI_FAIL is not set"""
        import os
        monkeypatch.delenv("MOCK_CLI_FAIL", raising=False)

        with patch("app.cli.adapter.subprocess.run") as mock_run:
            with patch("app.cli.adapter.shutil.which", return_value="/usr/bin/lte-scan"):
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout='{"cells": []}',
                    stderr="",
                )
                result = self.adapter.execute(band=8, timeout=10)
                assert result.results == []

    def test_mock_cli_fail_decrements_counter(self, monkeypatch):
        """Test that remaining counter decrements and stops after N fails"""
        import os
        from app.gps.test_management import _decrement_cli_fail, _cli_fail_remaining

        # Start with remaining=2
        monkeypatch.setenv("MOCK_CLI_FAIL", "1")
        monkeypatch.setattr(
            "app.gps.test_management._cli_fail_remaining", 2
        )

        # First call should return True (fail)
        assert _decrement_cli_fail() is True

        # Second call should return True (fail)
        assert _decrement_cli_fail() is True

        # Third call should return False (no more fails)
        assert _decrement_cli_fail() is False
