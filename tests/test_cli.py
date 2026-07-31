from typer.testing import CliRunner
from itkb.cli import app

runner = CliRunner()


def test_serve_default_host(mocker):
    mock_run = mocker.patch("uvicorn.run")
    result = runner.invoke(app, ["serve"])
    assert result.exit_code == 0
    assert mock_run.call_args.kwargs["host"] == "127.0.0.1"


def test_serve_host_flag(mocker):
    mock_run = mocker.patch("uvicorn.run")
    result = runner.invoke(app, ["serve", "--host", "0.0.0.0"])
    assert result.exit_code == 0
    assert mock_run.call_args.kwargs["host"] == "0.0.0.0"
