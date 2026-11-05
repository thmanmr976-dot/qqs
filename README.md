# qqs — Quick Quick Shell

A multi-backend desktop-shell and rice switcher for Linux / Hyprland. One input, one list, and an animated loading screen, using the supplied blue logo.

## Included rice snapshots

This repository includes the three rices saved in the source installation on November 5, 2026. Their files are stored under [`bundled-rices/`](bundled-rices/) with a portable manifest; no session records, personal application preferences, logs, or API credentials are included.

| Saved name | Type | Upstream |
| --- | --- | --- |
| shell | Quickshell desktop with multiple themes | [dhrruvsharma/shell](https://github.com/dhrruvsharma/shell) |
| persona quickshell | Quickshell desktop | [Persona-Quickshell-](https://github.com/Yujonpradhananga/Persona-Quickshell-) |
| i3-dots | Rofi launcher, squared-nord theme | [sansroot/i3-dots](https://github.com/sansroot/i3-dots/tree/joi-dots-UNMAINTAINED) |

`python3 install.py` copies these snapshots into your own qqs library and adds them to the list. Reinstalling preserves existing copies, edits, names and preferences. You can also run `python3 bundled_rices.py` to add them without changing desktop shortcuts. No rice starts during installation.

Install Quickshell for the two desktops and Rofi for the launcher. Persona also requires its [Qt6 Cava plugin](https://github.com/Yujonpradhananga/Qt6-Cava-plugin), built for your installed Qt version. Follow each included project's README for the remaining dependencies. Machine-specific binaries and plugins are not copied from the original device. See [THIRD_PARTY.md](THIRD_PARTY.md) for attribution and the snapshot preparation notes.

## Run and install

Install Lua 5.2 or newer using your distribution package manager to use the default Lua themes. Rasi-only configurations do not require Lua.

Requires Python 3.10+, PySide6, and the runtime/dependencies of the shell you select. Run inside a Wayland session.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python install.py
./launch.sh
```

If PySide6 is already installed, use `python3 install.py` and `./launch.sh` directly. The installer adds **qqs** to your application menu and **Ctrl+Shift+Q** to an existing Hyprland Lua or traditional configuration. Reload Hyprland after installation, or log in again. Installation is per user and creates a backup before editing the shortcut configuration. Keep the application folder in place; reinstall if you move it.

## Use

- Open **qqs** from your app launcher, or press **Ctrl+Shift+Q**. Pressing the shortcut again toggles the list; it does not open duplicate windows. **Escape** hides the list.
- Paste a GitHub repository URL, a local rice folder, an exact shell entry file or launcher path, or a local ZIP path into the field, then press **Import** or Enter. Paths with spaces do not need quotes.
- Public GitHub repositories and `/tree/branch-or-tag` URLs are supported. A repository containing several `shell.qml` files asks which entry to add.
- A successful addition shows a confirmation and saves the rice to the list. Addition checks for an entry file; it does not start the shell or install dependencies.
- Click a rice once to apply it. The black loading screen animates while qqs stops its managed rice and starts the selected one. It disappears after the backend reports readiness and the minimum display time has elapsed. See **SHELLS.md** for the readiness rules. Restarting the same rice also shows the loading screen.
- Any import or launch failure displays an error and opens a log viewer with the actual log paths, detailed output, a refresh button, and **Open launcher log / Open shell log**. Logs are persistent.
- Closing or hiding the list leaves the rice running. Reopen qqs to switch again. Only run rices from sources you trust: Imported shells and launchers can execute commands with your user permissions.

Right-click a rice for file preview, opening its folder or entry file, opening the import source, changing its source URL, copying its location, renaming it, or removing it from the list. Imported inactive folders can also be moved to the desktop Trash after confirmation; external local folders are never deleted by this action. Older imports recover their source only when the repository URL in their README matches the extracted repository directory. Otherwise use **Edit import source…**. New imports retain their exact source. Right-click the panel background for appearance files, log files, stopping the current rice, login restoration, or quitting qqs. Quitting qqs leaves its rice running.

## Launcher customization

The two active theme files default to `~/.config/qqs/menu.lua` and `~/.config/qqs/loading.lua`. Lua 5.2+ is required for Lua themes. Existing Rasi users retain their active `menu.rasi` / `loading.rasi`; switch formats in **Appearance presets → Appearance file format**. Both formats expose the same customization options and retain settings during conversion.

Control window position and percentage dimensions; transparency and background images; fonts, colors, borders and padding per element; title/input/list/footer order; multi-column grids; normal/hover/selected/alternate row states; icons, labels and source text; search mode and sorting; keyboard shortcuts and mouse behavior; and the loading screen and progress bar. Optional Qt stylesheets extend native widget states. This is qqs-specific theming, rather than complete Rofi or GTK/Wofi compatibility.

```lua
return {
  preset = "qqs-dark",
  width = 600,
  height = 420,
  list_columns = 2,
  row_selected = "#89b4fa",
  row_selected_text_color = "#111111",
  search_mode = "fuzzy",
  mouse_single_click = false,
  live_reload = true,
}
```

Type to filter saved rices; Enter applies the selected result. Paste a path or GitHub URL and Enter imports it; Ctrl+Enter always adds. Up/Down or Ctrl+K/Ctrl+J navigate, Escape hides, Shift+F10 opens the rice menu. All these bindings are configurable.

Right-click the panel for **Open menu appearance file**, **Open loading appearance file**, **Appearance presets**, **Import menu appearance**, **Export menu appearance**, and **Restore previous appearance**. Five presets are included: **Original**, **Liquid Glass**, **qqs-dark**, **qqs-grid**, and **qqs-minimal**. Liquid Glass uses compositor blur with translucent surfaces and specular highlights. Valid changes apply while the list is open; an invalid live edit keeps the previous appearance and writes the error to the footer and log. See [THEMING.md](THEMING.md) for the complete property list and supported Rasi selectors.

## Persistent data and login restoration

Existing imports and saved rices from older versions are retained under `$XDG_DATA_HOME/quickshell-studio` or `~/.local/share/quickshell-studio`.

- `preferences.json`: saved rice list and previous-version preferences.
- `interfaces/`: downloaded / extracted repositories.
- `session.log`: current shell and supervisor output.
- `qqs.log`: import, configuration and launcher errors.
- `session.json`: managed process identity.
- `last-interface.json`: last launched rice.
- `login-restore.json`: whether to restore the last rice at login.
- `module-paths.json`: remembered custom QML module search roots shared by all launch routes.

**Start last-used rice at login** is available in the panel context menu. The existing enabled preference is preserved. This registers an XDG autostart entry and, for Hyprland Lua, a marked login hook. No list window is opened at login. Disabling it removes only the managed restoration entries. A restoration lock prevents duplicate startup. qqs checks process identity and boot identity before controlling a saved process.

## Limits

qqs launches shell configurations and their foreground launchers. It is not a distribution-specific dotfile installer. It does not install dependencies, run repository installation scripts, change wallpapers or other external settings automatically, or stop shell processes launched outside qqs. Read the rice's own README for extra requirements.

`Configuration Loaded` confirms QML initialization; it does not guarantee every external service or visual component is ready. The animation shows startup activity, not a measured percentage. The screen closes on success or an error; the error log remains available.

GitHub imports support public repositories with a 100 MB compressed/extracted-size limit and 12,000 archive entries. Private repository authentication, Git LFS, and submodule fetching are not supported. Unsafe ZIP paths and symbolic links are rejected, but shell execution is not sandboxed. The log viewer shows the tail of large log files; log files themselves can grow while a rice runs.

The runtime preserves existing QML import paths and adds existing user Qt 6 module locations (`~/.local/lib/qt6/qml`, `$XDG_DATA_HOME/qt6/qml`, and `/usr/local/lib/qt6/qml`). This allows locally installed modules to load when qqs is opened from a desktop shortcut or restored at login, without relying on interactive shell initialization.

The old built-in source editor was replaced by the requested minimal list. Use **Open configuration folder** to edit QML in your preferred editor; saved file edits remain on disk.

## Tests

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```

## QML modules across launch methods and releases

All rice launches and login restoration use the same environment builder in `runtime.py`. It preserves explicit module search paths, supports `QML2_IMPORT_PATH`, and checks conventional user Qt 6 installation locations on every launch. It remembers existing custom roots from `QML_IMPORT_PATH` and `QML2_IMPORT_PATH` during installation, app entry, or a rice launch, so they remain available when a later desktop / login launch has no shell exports. User paths take precedence; absent paths are skipped without forgetting remembered roots.

To register an unusual plugin location once, launch qqs from a terminal with its **parent module directory**:

```bash
QML_IMPORT_PATH=/path/to/qml ./launch.sh
```

This also records the path if another qqs instance is already open. For example, a module at `/path/to/qml/CavaMonitor/qmldir` needs `/path/to/qml`, rather than the `CavaMonitor` subdirectory itself. Advanced users can edit `module-paths.json` in the data directory (`qml_import_paths` is a JSON list of absolute directories). Module caches are stored outside the app folder, so updating the app preserves them. Each runtime log records the resolved search roots for diagnosis. An actually absent plugin still needs to be installed according to the rice documentation.

Build future releases using:

```bash
python3 build_release.py --output ../qqs.zip
```

The builder runs the regression tests, creates a temporary ZIP, extracts it, and runs the tests against that packaged copy. It replaces the output archive only after both runs pass. Tests cover empty desktop environments, remembered custom roots, newly installed modules, login restoration, preservation of explicit paths, and damaged cache recovery.

## Supported shell types

Quickshell, AGS/Astal (TypeScript and legacy AGS v1), Astal Python/GJS, Fabric Python, Eww, Waybar, compiled executables, shell/Python launch scripts, desktop launchers and explicit `qqs-shell.json` profiles are supported. Dependencies must be installed for the selected shell. Source-only projects may require a build before launch. See [SHELLS.md](SHELLS.md) for discovery rules, Eww window selection, custom commands and readiness details.

## Rice launcher integrations

Rofi themes/configs, Wofi config/CSS, Fuzzel and Tofi configs can be imported as standalone menus. Opening a menu preserves the running desktop shell. Attached configs and arbitrary declared launcher commands appear under **Launchers for this rice**. Rice-local wrappers forward defaults without modifying global launcher settings, and **Launcher dependencies…** reports missing tools. See [LAUNCHERS.md](LAUNCHERS.md) for script/plugin support, required tools, custom launchers and integration limits.
