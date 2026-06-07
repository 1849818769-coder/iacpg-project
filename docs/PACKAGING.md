# MCP Server Packaging

This project can package `mcp_server.py` as a PyInstaller executable. The packaged server can then be referenced directly in Claude Code MCP configuration.

The package is a deployment convenience for the MCP server. It is not a fully self-contained experiment environment.

## Important Limitation

PyInstaller builds executables for the current operating system only:

- Build on Windows to get `iacpg-mcp.exe`.
- Build on Linux/WSL to get a Linux executable.

For Claude Code running on Windows, build with Windows Python.

Joern and Java are external tools and are not bundled. Any tool that calls Joern, such as `joern_import` or `build_iacpg`, requires Joern and Java to be available in the same runtime environment as the packaged MCP server. If your Joern installation only works inside WSL/Linux, prefer the Linux/WSL workflow rather than the Windows package.

The paper experiments were reproduced with the Linux/WSL script workflow and externally configured Joern. The Windows package under `packaged/iacpg-mcp-windows.zip` is provided for MCP deployment convenience.

## Build On Windows

From the repository root:

```bat
py -3.12 -m pip install pyinstaller
py -3.12 -m PyInstaller --clean --noconfirm packaging\iacpg_mcp.spec
```

The packaged MCP server will be created at:

```text
dist\iacpg-mcp\iacpg-mcp.exe
```

## Build On Linux/WSL

```bash
python3 -m pip install pyinstaller
python3 -m PyInstaller --clean --noconfirm packaging/iacpg_mcp.spec
```

The packaged MCP server will be created at:

```text
dist/iacpg-mcp/iacpg-mcp
```

## Claude Code MCP Configuration

Windows example:

```json
{
  "mcpServers": {
    "iacpg": {
      "command": "D:\\\\path\\\\to\\\\iacpg-project\\\\dist\\\\iacpg-mcp\\\\iacpg-mcp.exe",
      "env": {
        "JOERN_HOME": "D:\\\\path\\\\to\\\\joern-cli",
        "JAVA_HOME": "D:\\\\path\\\\to\\\\jdk-17"
      }
    }
  }
}
```

Linux/WSL example:

```json
{
  "mcpServers": {
    "iacpg": {
      "command": "/path/to/iacpg-project/dist/iacpg-mcp/iacpg-mcp",
      "env": {
        "JOERN_HOME": "/path/to/joern-cli",
        "JAVA_HOME": "/path/to/jdk-17"
      }
    }
  }
}
```

## Notes

- Joern and Java are external tools and are not bundled.
- The executable bundles the MCP server, `ice_core/`, and `scripts/`.
- Generated benchmark outputs are still written under each case directory.
- If you use a custom Python/Conda environment for subprocess compatibility, set `IACPG_PYTHON` or `IACPG_CONDA_ENV`.
- For reviewers who want to reproduce the paper metrics, the recommended path is still `scripts/with_local_env.sh` or an equivalent Linux/WSL environment with Joern configured externally.
