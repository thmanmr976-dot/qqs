# Shell engines supported by qqs

Import a public GitHub repository, ZIP archive, local configuration folder, or exact entry/launcher path. qqs detects the entry type without running it during import. Repositories containing several entries present a selector with both backend name and path. Existing Quickshell entries remain compatible.

| Type | Entry | Launch method |
| --- | --- | --- |
| Quickshell | `shell.qml` or an explicitly selected QML file | `quickshell --no-color --path FILE` |
| AGS / Astal TypeScript | `app.ts`, `app.tsx`, `main.ts`, etc. with AGS/Astal imports | `ags run FILE` |
| Legacy AGS v1 | JS with legacy resource imports | `ags --config FILE` using AGS v1 |
| Astal GJS | JS importing `gi://Astal…` directly | `gjs -m FILE` |
| Astal Python / Fabric | Python entry with Astal/Fabric imports | `python3 FILE` |
| Eww | `eww.yuck` | A supervised foreground daemon for that config directory, followed by `open-many` for selected windows |
| Waybar | `config`, `config.jsonc`, `config.json` with Waybar settings | `waybar --config FILE --style style.css` when the stylesheet is present |
| Custom | `launch.sh`, `start.sh`, `run.sh`, explicit script/executable or `.desktop` | Foreground launch, using its interpreter/arguments |
| Explicit profile | `qqs-shell.json` | An argument array and working directory supplied by the project |

Compiled ELF executables / AppImages near an archive's top level are recognized when marked executable. Archive executable permissions are preserved without preserving privileged mode bits. Arbitrary Python/JS helper files are not automatically treated as shell entries; select a launcher directly or use a profile. `.git`, dependency directories and build output directories are skipped during recursive discovery. An explicit launch profile takes priority in its subtree, followed by conventional launch scripts.

Modern AGS and legacy AGS require the corresponding AGS runtime version. Native Astal applications require their own libraries and build steps. Installing AGS alone does not install every shell's external dependencies.

## Eww

At import, qqs discovers `defwindow` declarations, including simple local Yuck includes, and asks which window should open. It selects `bar` by default if present. This avoids opening every popup and dialog at once. Configurations needing required window arguments can use a dedicated foreground launcher/profile. Advanced users can set the saved rice's `launch_options.windows` list in `preferences.json` to open several named windows.

qqs refuses to take over an external Eww daemon already serving the same configuration directory. It does not issue a global Eww kill. Config paths are passed explicitly, and the owned daemon is kept in the selected shell's process group.

## Any other installed shell: explicit launch profile

Create a file called `qqs-shell.json` in its project folder:

```json
{
  "command": ["my-shell", "--config", "./config"],
  "working_directory": ".",
  "environment": {"MY_SHELL_THEME": "blue"},
  "require_window": true,
  "startup_grace_ms": 1500
}
```

`command` is an array of arguments, not a shell expression. Relative executable paths and the working directory resolve against the profile/project directory. Environment values must be strings. No shell expansion is applied: semicolons, `$…` and spaces in an argument are passed literally. To use shell syntax deliberately, provide a foreground script or an explicit `bash -c` argument array.

An optional `ready_text` string waits for a literal success message in output. With no marker, `require_window: true` waits for a visible owned surface on Hyprland. Otherwise readiness means the managed process has survived `startup_grace_ms`; it does not prove every visual component/service works. Keep the configured loading timeout longer than your shell's startup time.

For a compiled native Astal application, for example:

```json
{
  "command": ["./build/my-astal-shell"],
  "working_directory": ".",
  "require_window": true
}
```

The `examples/custom` folder contains a working profile and a small native-window demo for testing the launcher. It is not a complete desktop shell.

Build native projects using their documented build process before selecting them. Profiles can also launch installed commands such as project-specific shell wrappers without depending on qqs recognizing their file format.

## Readiness, stopping and persistence

- Quickshell readiness uses its `Configuration Loaded` message.
- AGS/Astal, Fabric and Waybar wait for an owned window/layer on an active Hyprland session. On other compositors they use a startup grace interval.
- Eww readiness requires a responsive owned daemon and successful window-open requests.
- A custom profile uses `ready_text`, owned-window detection, or its grace interval as described above.

Each new shell runs under a small supervisor in its own process group. Foreground processes and background children that remain in this group can be stopped together. The supervisor persists after closing qqs. An exited wrapper is not considered successful unless it left running processes in its group. Scripts using `nohup`/`setsid`, system services, D-Bus activation, or an already running remote instance may escape supervision; use a foreground command instead. A detached process cannot be guaranteed to stop with qqs.

On switching, dependencies and the launch plan are checked before stopping the current rice. qqs then stops its managed group and starts the selected one. Logs include the backend and combined output. Fatal process exits, window-open failures and startup timeouts are shown in the log viewer. Missing dependencies are reported; no dependency manager, repository installer, or package build is run automatically.

The last successful entry and launch options are saved for login restoration. The same backend detection, environment setup and supervisor are used on restoration. Shells launched outside qqs are not adopted or killed. Imported code runs with your user permissions, just as QML configurations did previously.

Support for common engines and custom foreground launchers does not guarantee that every Hyprland dotfile repository runs unchanged. Some repositories need installation into a fixed location, builds, private assets, patched runtimes, distribution-specific services, or other setup from their README.

## CLI references

- [Quickshell configuration paths](https://quickshell.org/docs/v0.3.2/guide/introduction/)
- [AGS quick start](https://aylur.github.io/ags/guide/quick-start.html)
- [Eww window configuration](https://elkowar.github.io/eww/configuration.html)
- [Eww command options](https://github.com/elkowar/eww/blob/master/crates/eww/src/opts.rs)
- Waybar: `waybar --help` on the installed runtime.

## Temporary application launchers

Rofi, Wofi, Fuzzel, Tofi and recognized launcher scripts are handled as temporary menus. They can be imported separately or discovered inside a rice. They never replace the running desktop shell or its login-restoration entry. Any other launcher can use a custom profile with `transient: true`. See [LAUNCHERS.md](LAUNCHERS.md).
