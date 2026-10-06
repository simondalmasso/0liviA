# Getting the Wolfram Engine

The bundled scripts in this skill require `wolframscript`, the command-line interface to the Wolfram Language. This guide covers installation on each platform.

---

## Check If Already Installed

Run the following in your terminal:

```
wolframscript -code 'Print[$InstallationDirectory]; Print[$Version];'
```

If it prints an installation path and version, you're ready to go — no further setup needed.

---

## macOS

### Via Homebrew (recommended)

If the user has Homebrew, offer to run this command for them:

```bash
brew install --cask wolfram-engine
```

If the user does not have Homebrew, offer to install it first using the instructions at <https://brew.sh>, then run the command above. Always ask the user's permission before running either command.

After installation, `wolframscript` should be available on your PATH automatically.

### Manual Download

1. Download the Wolfram Engine from <https://www.wolfram.com/engine/>.
2. Open the `.dmg` and drag **Wolfram Engine** to Applications.
3. Run the app once to complete activation.
4. `wolframscript` is installed at `/usr/local/bin/wolframscript`.

---

## Linux

Offer to download and run the installer for the user:

```bash
cd ~/Downloads
wget https://files.wolframcdn.com/pub/support/WolframEngine/14.3.0.0/WolframEngine_14.3.0_LIN.sh
chmod a+x WolframEngine_14.3.0_LIN.sh
sudo ./WolframEngine_14.3.0_LIN.sh
```

If you can offer an interactive terminal session, open it and run those commands, letting the user enter the sudo password as needed. Always ask the user's permission before running.

After installation, `wolframscript` is typically at `/usr/bin/wolframscript`.

---

## Windows

### Via winget (recommended)

Offer to run this command for the user (note: it runs at Administrator level and will trigger a UAC prompt):

```
winget install wolframengine
```

Always ask the user's permission before running.

### Manual Download

1. Download the installer from <https://www.wolfram.com/engine/>.
2. Run the `.exe` installer and follow the prompts.
3. Activate when prompted.

After installation, `wolframscript.exe` is added to your PATH. **Important for IDE/editor environments (VSCode, JetBrains, etc.):** the new PATH entry won't be visible in the current session until the editor is restarted. If `wolframscript` is not found immediately after install, ask the user to restart their editor and try again before troubleshooting further.

If `wolframscript` is still not found after restart, the default location is:
```
C:\Program Files\Wolfram Research\WolframScript\wolframscript.exe
```

---

## Activation

The Wolfram Engine is free for development use but requires activation with a Wolfram Account. If you don't have one, create an account at <https://account.wolfram.com>.

Activate with:

```
wolframscript -activate
```

If you can offer an interactive terminal session, run this command interactively so the user can enter their Wolfram ID and password. Otherwise, instruct the user to run it themselves.

After successful activation, verify it works by running:

```bash
wolframscript -code '1 + 1'
```

Expected output: `2`. If this prints `2`, the Engine is installed and activated correctly. Do not proceed to MCP setup until this test passes.

---

## Troubleshooting

- **`wolframscript` not found** — Ensure the install directory is on your PATH. You can check the location with `which wolframscript` (macOS/Linux) or `where wolframscript` (Windows). See also [support article](https://support.wolfram.com/47243).
- **Activation fails** — Check your internet connection and verify your Wolfram Account credentials at <https://account.wolfram.com>.
- **License issues** — The free Wolfram Engine license covers non-production development use. For production or commercial use, see <https://www.wolfram.com/engine/commercial-options/>.

### Advanced configuration

Run `wolframscript -configure` to display the current configuration and available keys:

```
Configuration format: wolframscript -configure KEY=VALUE
Available keys: WOLFRAMSCRIPT_KERNELPATH, WOLFRAMSCRIPT_AUTHENTICATIONPATH, WOLFRAMSCRIPT_CLOUDBASE, WOLFRAMSCRIPT_CLOUDLICENSESERVER
Configuration file location: /Users/<user>/Library/Application Support/Wolfram/WolframScript/WolframScript.conf

Configuration file:
WOLFRAMSCRIPT_KERNELPATH=/Applications/Wolfram Engine.app
WOLFRAMSCRIPT_AUTHENTICATIONPATH=/Users/<user>/Library/Caches/Wolfram/WolframScript/
WOLFRAMSCRIPT_CLOUDBASE=https://www.wolframcloud.com
```

Set a value with `wolframscript -configure KEY=VALUE`:

| Key | Description | When to Set |
|-----|-------------|-------------|
| `WOLFRAMSCRIPT_KERNELPATH` | Path to the Wolfram Engine app or kernel binary | If the kernel is not found automatically (non-default install location) |
| `WOLFRAMSCRIPT_AUTHENTICATIONPATH` | Path to the authentication/license cache directory | If you want to store credentials in a custom location |
| `WOLFRAMSCRIPT_CLOUDBASE` | Wolfram Cloud base URL | Almost always `https://www.wolframcloud.com` |
| `WOLFRAMSCRIPT_CLOUDLICENSESERVER` | Cloud license server URL | If your organization uses a dedicated license server |

---

## More Information

- Wolfram Engine: <https://www.wolfram.com/engine/>
- Wolfram Account: <https://account.wolfram.com>
