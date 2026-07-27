import pytest
from unittest.mock import patch, MagicMock
from app.cli.adapter import CLIAdapter
from app.cli.exceptions import CLIError, CLITimeoutError, CLIParseError, CLINotFoundError


class TestCLIAdapter:
    def setup_method(self):
        self.adapter = CLIAdapter()

    @patch("app.cli.adapter.shutil.which", return_value="/usr/bin/lte-discovery")
    def test_find_command_success(self, mock_which):
        result = self.adapter._find_command()
        assert result == "lte-discovery"

    @patch("app.cli.adapter.shutil.which", return_value=None)
    def test_find_command_not_found(self, mock_which):
        with pytest.raises(CLINotFoundError):
            self.adapter._find_command()

    @patch("app.cli.adapter.subprocess.run")
    @patch("app.cli.adapter.shutil.which", return_value="/usr/bin/lte-discovery")
    def test_execute_success(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"results": [{"operator_name": "Telkomsel", "mcc": "510", "mnc": "10", "rat": "4G", "status": "active"}]}',
            stderr="",
        )

        result = self.adapter.execute(port="/dev/ttyUSB0", timeout=30)

        assert len(result.results) == 1
        assert result.results[0].operator_name == "Telkomsel"
        assert result.results[0].mcc == "510"

    @patch("app.cli.adapter.subprocess.run")
    @patch("app.cli.adapter.shutil.which", return_value="/usr/bin/lte-discovery")
    def test_execute_timeout(self, mock_which, mock_run):
        mock_run.side_effect = Exception("timed out")

        with pytest.raises(Exception):
            self.adapter.execute(port="/dev/ttyUSB0", timeout=30)

    @patch("app.cli.adapter.subprocess.run")
    @patch("app.cli.adapter.shutil.which", return_value="/usr/bin/lte-discovery")
    def test_execute_non_zero_exit(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error message",
        )

        with pytest.raises(CLIError):
            self.adapter.execute(port="/dev/ttyUSB0", timeout=30)

    def test_parse_output_valid_json(self):
        stdout = '{"results": [{"operator_name": "Telkomsel", "mcc": "510", "mnc": "10"}]}'
        result = self.adapter._parse_output(stdout)

        assert len(result.results) == 1
        assert result.results[0].operator_name == "Telkomsel"

    def test_parse_output_invalid_json(self):
        stdout = "not json"

        with pytest.raises(CLIParseError):
            self.adapter._parse_output(stdout)

    def test_parse_output_networks_key(self):
        stdout = '{"networks": [{"operator_name": "XL", "mcc": "510", "mnc": "11"}]}'
        result = self.adapter._parse_output(stdout)

        assert len(result.results) == 1
        assert result.results[0].operator_name == "XL"

    def test_parse_output_empty_results(self):
        stdout = '{"results": []}'
        result = self.adapter._parse_output(stdout)

        assert len(result.results) == 0
