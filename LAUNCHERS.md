# Rofi, Wofi and rice-specific launchers

qqs treats application launchers as temporary menus, not replacement desktop shells. Opening one does not stop the running rice, replace its session record, or change the rice restored at login.

## Import a launcher package

Use the normal import field for a local folder, ZIP, GitHub repository or exact configuration file:

- **Rofi:** `.rasi` configuration/theme files. qqs uses `rofi -show drun -config config.rasi` for a file named `config.rasi`, and `-theme FILE` for other themes.
- **Wofi:** `wofi/config`, `wofi/config.ini`, or a recognizable Wofi CSS stylesheet. The matching local `style.css`/`config` is included automatically.
- **Fuzzel:** `fuzzel.ini`.
- **Tofi:** `tofi/config`.
- **Launcher scripts:** scripts invoking a recognized launcher without starting a persistent shell.
- **Other launchers:** a `qqs-shell.json` profile with `transient: true` and an explicit argument-array command.

Launcher-only archives are accepted even without QML or another shell entry. Mixed rice repositories prefer the desktop-shell entry; attached launchers remain available from its context menu.

## Launchers attached to a rice

Right-click the saved rice and choose **Launchers for this rice**. Entries identify the discovered configuration path or a launcher declared by the project. **Launcher dependencies…** lists known referenced tools and whether their executable is available on PATH. Scanned references may be optional; the scan is a hint, not a full dependency solver.

When starting a rice with bundled Rofi/Wofi/Fuzzel/Tofi configs, qqs creates a private wrapper directory for that rice and prepends it only to the shell process's PATH. Relative/default launcher calls made by the shell then use the bundled config. Explicit `-config`, `-theme`, `--conf`, and `--style` arguments remain authoritative. Menu modes such as drun or dmenu are preserved, including stdin for script-driven menus.

The wrappers do not change global configuration files or the compositor's environment. Calls using absolute launcher paths, global key bindings run by Hyprland, and scripts hardcoding `~/.config/...` may bypass these integrations. Use the context menu or a portable project launch profile for those cases. Global configuration is never silently overwritten.

## Arbitrary launchers and declared requirements

A shell can declare requirements and named launcher commands in its `qqs-shell.json`:

```json
{
  "command": ["quickshell", "--path", "shell.qml"],
  "ready_text": "Configuration Loaded",
  "requires": ["rofi"],
  "launchers": [
    {
      "name": "Application menu",
      "bind_as": "rice-apps",
      "command": ["rofi", "-show", "drun", "-theme", "./rofi/launcher.rasi"]
    },
    {
      "name": "Another installed launcher",
      "command": ["my-launcher", "--config", "./menus/config"],
      "working_directory": ".",
      "environment": {"MY_LAUNCHER_THEME": "dark"}
    }
  ]
}
```

`requires` contains mandatory executable names checked before switching away from the current rice. This reports missing tools rather than running a package manager. Each launcher has a name and argument array; no shell-string expansion is applied. `bind_as` optionally exposes a rice-local command alias to the shell's child processes; in this example calling `rice-apps` opens the configured menu. Commands may use any installed launcher, rather than only the built-in names. Working directories resolve relative to the profile directory.

For an independent custom menu profile:

```json
{
  "command": ["my-launcher", "--config", "./config"],
  "transient": true,
  "require_window": true
}
```

qqs does not automatically launch all attached menus when a rice starts. They open only when selected or invoked by the shell.

## Plugins and scripts

Rofi script modi and Wofi script/dmenu menus run through their native launcher. Project-relative configuration paths and working directories are retained. A `plugins/` directory next to a Rofi config containing compiled `.so` modules is forwarded using the native Rofi plugin-path option.

Compiled extensions must match the installed launcher/GTK/architecture and may require installation/build steps from their README. Plugin source is not built automatically, and importing a theme does not install its runtime. Other dependencies such as `jq`, clipboard tools or terminal emulators can be declared in `requires`.

Pressing Escape or closing a menu is a normal outcome. Successful application launches are left running when the menu exits. Native launcher errors still go to the per-launcher log and the qqs log viewer. Standalone menus do not become the next login's desktop shell.

## References

- [Rofi CLI and modes](https://davatorium.github.io/rofi/current/rofi.1/)
- [Wofi CLI configuration and styles](https://man.archlinux.org/man/wofi.1.en)
- [Wofi modes and dmenu](https://man.archlinux.org/man/wofi.7.en)
