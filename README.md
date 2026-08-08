# ocom

<<<<<<< before updating
A unified TUI for managing network/privacy tools: OpenVPN, SpoofDPI/GoodbyeDPI, and Cloudflare WARP.

Cross-platform: macOS, Linux, and Windows.

## Features

- **OpenVPN**: Connect/disconnect using `.ovpn` config files (sudo on Unix, Administrator on Windows)
- **SpoofDPI** (Unix) / **GoodbyeDPI** (Windows): DPI bypass tools
- **Cloudflare WARP**: Toggle WARP VPN connection
- **Tailscale**: Toggle mesh VPN connection (`tailscale up`/`down`)
- **Real-time logs**: Live output from all tools in a dedicated panel
- **Install guidance**: Tools not installed show an Install button that opens documentation
- **Conflict resolution**: Automatically stops conflicting tools (e.g., WARP stops when starting OpenVPN)
- **Extensible**: Easy to add new tools
=======
<!-- TODO @hasansezertasan: Make it work, make it right, make it fast. -->
[![CI](https://github.com/hasansezertasan/ocom/actions/workflows/ci.yml/badge.svg)](https://github.com/hasansezertasan/ocom/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/codecov/c/github/hasansezertasan/ocom)](https://codecov.io/gh/hasansezertasan/ocom)
[![Documentation Status](https://img.shields.io/github/deployments/hasansezertasan/ocom/github-pages?label=docs)](https://hasansezertasan.github.io/ocom)
[![PyPI - Version](https://img.shields.io/pypi/v/ocom.svg)](https://pypi.org/project/ocom)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/ocom.svg)](https://pypi.org/project/ocom)
[![License - MIT](https://img.shields.io/github/license/hasansezertasan/ocom.svg)](https://opensource.org/licenses/MIT)
[![GitHub Stars](https://img.shields.io/github/stars/hasansezertasan/ocom?style=social)](https://github.com/hasansezertasan/ocom/stargazers)
[![Latest Commit](https://img.shields.io/github/last-commit/hasansezertasan/ocom)](https://github.com/hasansezertasan/ocom)

[![Checked with mypy](http://www.mypy-lang.org/static/mypy_badge.svg)](http://mypy-lang.org/)
[![linting - Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/hasansezertasan/ocom/badge)](https://scorecard.dev/viewer/?uri=github.com/hasansezertasan/ocom)
[![GitHub Tag](https://img.shields.io/github/tag/hasansezertasan/ocom?include_prereleases=&sort=semver&color=black)](https://github.com/hasansezertasan/ocom/releases/)

[![Downloads](https://pepy.tech/badge/ocom)](https://pepy.tech/project/ocom)
[![Downloads/Month](https://pepy.tech/badge/ocom/month)](https://pepy.tech/project/ocom)
[![Downloads/Week](https://pepy.tech/badge/ocom/week)](https://pepy.tech/project/ocom)

> A unified TUI for managing network/privacy tools: OpenVPN, SpoofDPI, Cloudflare WARP

-----

## Table of Contents

- [Screenshots](#screenshots)
- [Installation](#installation)
- [Support](#support-heart)
- [Motivation](#motivation)
- [About](#about)
- [Author](#author-person_with_crown)
- [Analysis](#analysis)
- [Contributing](#contributing-heart)
- [Development](#development-toolbox)
- [Releasing](#releasing)
- [Credits](#credits)
- [License](#license-scroll)
- [Changelog](#changelog-memo)

## Screenshots

<!-- TODO @hasansezertasan: Add screenshots or a demo GIF, or remove this section. -->

## Installation

`ocom` is a library. Add it to your project as a dependency:

```console
uv add ocom
```

Or with `pip`:

```console
pip install ocom
```

## Support :heart:

If you have any questions or need help, feel free to open an issue on the [GitHub repository][ocom].

## Motivation

<!-- TODO @hasansezertasan: Explain why this project exists and what problem it solves, or remove this section. -->

## About
>>>>>>> after updating

## Installation

`ocom` is a standalone end-user tool. Install it into an isolated environment
with your preferred installer:

```bash
uv tool install ocom
```

```bash
pipx install ocom
```

Or run it without installing:

```bash
uvx ocom
```

On macOS/Linux, install it from the [Homebrew tap](https://github.com/hasansezertasan/homebrew-tap):

<<<<<<< before updating
```bash
brew install hasansezertasan/tap/ocom
```

On Windows, install it from the [Scoop bucket](https://github.com/hasansezertasan/scoop-bucket):

```bash
scoop bucket add hasansezertasan https://github.com/hasansezertasan/scoop-bucket
scoop install ocom
```

Or install from source — see the [installation docs](https://hasansezertasan.github.io/ocom/installation.html).

## Usage

```bash
ocom
```

### Keyboard Shortcuts

| Key     | Action                 |
| ------- | ---------------------- |
| `q`     | Quit                   |
| `r`     | Refresh status         |
| `c`     | Clear logs             |
| `Tab`   | Navigate between tools |
| `Enter` | Activate button        |
| `Esc`   | Close modal            |

## Configuration

ocom reads a TOML config file at `~/.config/ocom/config.toml` (the same path on
Linux and macOS). If the file doesn't exist, the defaults below are used.

```toml
[general]
refresh_interval = 2
auto_connect = false

[openvpn]
enabled = true
config_dirs = ["~/.openvpn", "~/vpn-configs"]
default_config = ""

[spoofdpi]
enabled = true
dns_addr = "8.8.8.8:53"
dns_mode = "https"
port = 8080
system_proxy = false

[warp]
enabled = true
mode = "warp"

[tailscale]
enabled = true

[goodbyedpi] # Windows only
enabled = true
mode = 9
block_quic = true
```

### Options

**`[general]`**

| Option             | Type | Default | Description                                               |
| ------------------ | ---- | ------- | --------------------------------------------------------- |
| `refresh_interval` | int  | `2`     | Status check interval in seconds (min: 1)                 |
| `auto_connect`     | bool | `false` | Auto-connect to OpenVPN using `default_config` on startup |

**`[openvpn]`**

| Option           | Type   | Default                           | Description                           |
| ---------------- | ------ | --------------------------------- | ------------------------------------- |
| `enabled`        | bool   | `true`                            | Show OpenVPN in the TUI               |
| `config_dirs`    | list   | `["~/.openvpn", "~/vpn-configs"]` | Directories scanned for `.ovpn` files |
| `default_config` | string | `""`                              | `.ovpn` file used for auto-connect    |

**`[spoofdpi]`** (Unix)

| Option         | Type   | Default        | Description                     |
| -------------- | ------ | -------------- | ------------------------------- |
| `enabled`      | bool   | `true`         | Show SpoofDPI in the TUI        |
| `dns_addr`     | string | `"8.8.8.8:53"` | DNS server address (`ip:port`)  |
| `dns_mode`     | string | `"https"`      | One of `udp`, `https`, `system` |
| `port`         | int    | `8080`         | Local proxy port (1–65535)      |
| `system_proxy` | bool   | `false`        | Set system proxy on start       |

**`[warp]`**

| Option    | Type   | Default  | Description                     |
| --------- | ------ | -------- | ------------------------------- |
| `enabled` | bool   | `true`   | Show Cloudflare WARP in the TUI |
| `mode`    | string | `"warp"` | One of `warp`, `doh`, `proxy`   |

**`[tailscale]`**

| Option    | Type | Default | Description               |
| --------- | ---- | ------- | ------------------------- |
| `enabled` | bool | `true`  | Show Tailscale in the TUI |

Mesh mode only: ocom runs `tailscale up`/`down` and reads `tailscale status --json`.
It does not configure an exit node, so Tailscale coexists with OpenVPN/WARP rather
than conflicting. On Linux, controlling Tailscale without `sudo` requires setting the
operator once: `sudo tailscale set --operator=$USER`.

**`[goodbyedpi]`** (Windows)

| Option       | Type | Default | Description                                 |
| ------------ | ---- | ------- | ------------------------------------------- |
| `enabled`    | bool | `true`  | Show GoodbyeDPI in the TUI                  |
| `mode`       | int  | `9`     | Preset mode (1–9), higher = more aggressive |
| `block_quic` | bool | `true`  | Block QUIC/HTTP/3                           |

GoodbyeDPI must be run with Administrator privileges; ocom checks for them and
reports a clear error if they are missing.
=======
## Development :toolbox:

See the [Contributing Guidelines](./.github/CONTRIBUTING.md#your-first-code-contribution)
for local setup, the common development tasks (exposed via [mise](https://mise.jdx.dev)),
building and previewing the documentation, and the VS Code debugging configurations.
>>>>>>> after updating

### Auto-connect

When `auto_connect = true`, ocom attempts to connect to OpenVPN on startup using
`openvpn.default_config` (which must point to a valid `.ovpn` file). On Unix a sudo
password prompt appears immediately; on Windows the connection starts automatically
(run as Administrator).

```toml
[general]
auto_connect = true

[openvpn]
default_config = "~/.openvpn/my-server.ovpn"
```

Configuration is validated with Pydantic, so out-of-range values (e.g. an invalid
`dns_mode` or a `port` outside 1–65535) are rejected at load time. Settings come from
the TOML file only — environment variables are not read.

## Requirements

- Python 3.14+
- OpenVPN (for OpenVPN support)
- warp-cli (for WARP support)
- spoofdpi (Unix) or goodbyedpi (Windows) for DPI bypass

## License

MIT
