# Auto Astroberry

Use a laptop or desktop to plan and supervise an observing session on a Linux astronomy host running KStars/Ekos. The repository includes an observing skill, an SSH-accessible MCP bridge, and an editable example for a NexStar 127SLT with an SVBONY SC715C camera. The bridge starts in read-only mode.

## Set up the astronomy host

1. Install Git, Python 3.9+, OpenSSH server, and the Secret Service client `secret-tool` (Debian package `libsecret-tools`). Use a KStars build with native MCP support, a desktop session with an unlocked Secret Service keyring, and the INDI drivers for your equipment.
2. In KStars, configure the Ekos profile and optical train for this rig. Enable the native MCP server on the loopback endpoint `http://127.0.0.1:8765/mcp` and configure its read-only token in the desktop keyring. Control mode uses the separate control token. The bridge looks up the KStars entries with attributes `server=kstars`, `type=plaintext` and `user=mcp_readonly_token` or `user=mcp_token`.
3. Run these commands in the astronomy host's home directory.

   ```sh
   cd ~
   git clone https://github.com/awood57/auto-astroberry.git
   cd auto-astroberry
   cp observatory.example.json observatory.local.json
   python3 test-mcp-transport.py
   ```

4. Edit the ignored local JSON file. Match the profile, optical train, equipment, directories and limits to the real rig. Paths belong to the account running KStars and may begin with `~/`. Create the plan and capture directories under that account and select the capture destination in Ekos. The JSON describes the setup to the client. Configure the actual hardware and limits in KStars.

## Connect a client

On any client with OpenSSH, create a local SSH alias called `astro-rig` for your astronomy host and its desktop user. Verify the host fingerprint and set up key-based login so `ssh -o BatchMode=yes astro-rig whoami` succeeds. Keep the alias, key and host fingerprint on that client.

Configure a stdio MCP server with command `ssh` and these arguments in order:

```json
["-T", "-o", "BatchMode=yes", "astro-rig", "python3", "auto-astroberry/astroberry-mcp-stdio.py"]
```

The relative script path assumes the clone is in the remote user's home directory. Open KStars and unlock the desktop keyring before connecting. List tools and call `observatory_setup` and `ekos_status` to check the connection. For supervised observing, append `--control` to the arguments and reconnect. Starting the bridge issues no equipment commands.

Clone the same repository on your client and open it as the project to use the bundled Codex skill. Try “Use $astroberry-observing to check readiness and plan a short imaging session.” The example profile uses a manual focuser and an unguided alt-az mount. Confirm alignment, focus, framing and a saved test exposure before committing observing time to a sequence.

## Keep local data private

Keep site coordinates, network details, keyring contents, images, plans and session logs outside version control. Publish changes to the example profile only when its values apply to other users. Offline tests use mocks and temporary files. Checking your specific drivers, mount clearance and image quality requires a supervised session on the rig.
