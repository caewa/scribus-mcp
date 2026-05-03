"""The Scribus-side bridge.

`scribus_mcp_bridge.spy` runs inside Scribus's embedded Python and exposes the
Scripter API over TCP loopback so the MCP server can drive a live Scribus
session. Drop the file in Scribus's autoload directory or run it manually
via Script > Execute Script... in Scribus.

Use :func:`bridge_path` to locate the file after `pip install`.
"""

from importlib.resources import as_file, files
from pathlib import Path


def bridge_path() -> Path:
    """Return the on-disk path to scribus_mcp_bridge.spy.

    Works whether the package is installed normally, in editable mode, in
    a source checkout, or shipped inside a zipapp / pex bundle (in which
    case ``importlib.resources.as_file`` extracts the file to a temp
    location for Scribus's ``-py`` flag to find).

    Returns an absolute path. Note: for zipapp installs, the temp file
    is cleaned up when the process exits — long-lived bridge launches
    should be fine since Scribus reads the .spy at startup, but if the
    server process exits while Scribus is still loading the script,
    behaviour is undefined.
    """
    resource = files(__package__).joinpath("scribus_mcp_bridge.spy")
    # Try the simple Path round-trip first (works for normal installs +
    # editable + source checkout). If that path doesn't exist on disk
    # (zipapp / pex), extract via as_file().
    direct = Path(str(resource))
    if direct.is_file():
        return direct
    with as_file(resource) as extracted:
        return Path(extracted)
