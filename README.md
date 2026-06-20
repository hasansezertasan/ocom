# ocom

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

## Installation

```bash
uv tool install ocom
```

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
