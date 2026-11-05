# Included projects and attribution

The snapshots in `bundled-rices/` are third-party projects. Their authors retain ownership; including them does not transfer their copyrights or apply a new license to their files. Original README files, source headers, credits and available license files are retained.

## shell

- Author/upstream: [dhrruvsharma/shell](https://github.com/dhrruvsharma/shell)
- Installed snapshot directory: `dhrruvsharma-shell-cba994f`
- License: GPL-3.0-or-later, as stated in the included README and LICENSE.
- Additional credits, including zesis-shell and shaders, remain in the project's files.
- Snapshot preparation: the embedded `wallhavenApiKey` default in `quickshell/settings/SettingsConfig.qml` was cleared before upload. Supply your own key locally if needed.

## Persona Quickshell

- Author/upstream: [Yujon Pradhananga / Persona-Quickshell-](https://github.com/Yujonpradhananga/Persona-Quickshell-)
- Installed snapshot directory: `Yujonpradhananga-Persona-Quickshell-6bb02aa`
- The included README states MIT License; no separate LICENSE file was present in this installed snapshot. Preserve the author's README and asset credits.
- The custom Cava plugin is a separate dependency, linked from the original README; no machine-specific compiled plugin is bundled.

## i3-dots / Rofi

- Upstream: [sansroot/i3-dots, joi-dots-UNMAINTAINED branch](https://github.com/sansroot/i3-dots/tree/joi-dots-UNMAINTAINED)
- Installed snapshot directory: `sansroot-i3-dots-df94485`
- Selected entry: `Rofi/squared-nord.rasi`.
- No license file was present in this installed snapshot; do not assume a license grant beyond what the original authors provide.
- The complete installed folder is retained for theme assets and references. qqs registers the Rofi entry; it does not install this project's i3 or other desktop configuration.

## Snapshot handling

The library manifest uses paths relative to each included folder. The installer creates paths for the receiving user's account, rather than reusing paths from the source machine. Runtime session files, logs, credentials, virtual environments and Python caches are excluded. Existing third-party code and asset dependencies still apply.
