# qqs launcher customization reference

qqs supports **Lua and Rasi** themes with the same layout, appearance and behavior controls. Fresh installs use `~/.config/qqs/menu.lua` and `~/.config/qqs/loading.lua`. Existing Rasi setups remain active. The `theme-format` marker selects which pair to read; choose **Appearance presets → Appearance file format** from the panel menu to convert both active files without losing their values. Inactive files remain on disk. Lua requires a Lua 5.2+ interpreter.

Right-click the panel for **Open menu appearance file**, **Open loading appearance file**, **Appearance presets**, **Import menu appearance**, **Export menu appearance**, and **Customization guide**. Presets: `qqs-dark`, `qqs-grid`, `qqs-minimal`, `qqs-liquid-glass`. Applying a preset backs up the current menu file; **Restore previous appearance** swaps it back. Export writes a self-contained snapshot, including values originally read from imports. Import validates a theme before replacing the current file.

## Lua

The files return a table using underscore-separated keys from the property tables below (for example, Rasi `row-selected` is Lua `row_selected`). Strings, integers, booleans, local variables, arithmetic, and the math/string/table libraries are supported. An optional `preset` establishes base values; your other keys override it.

```lua
local accent = "#8aadf4"
return {
  preset = "qqs-dark",
  width = "45%",
  height = 440,
  window_position = "northeast",
  window_offset_x = -20,
  window_offset_y = 20,
  input_position = "bottom",
  layout_padding = "16 20",
  list_columns = 2,
  row_selected = accent,
  row_selected_text_color = "#111111",
  font = "JetBrains Mono",
  font_size = 11,
  search_mode = "fuzzy",
  mouse_single_click = false,
  hide_on_focus_loss = true,
  keys_accept = "Return;Enter",
  keys_next = "Down;Ctrl+j",
  live_reload = true,
}
```

Lua themes run without file/process command APIs and have a two-second evaluation limit. Unknown keys and invalid values report an error. Loading-screen settings use the same table format with the loading keys below.

## Rasi

Rasi files are `menu.rasi` and `loading.rasi`. qqs implements a documented subset of Rofi selectors and properties, without embedding Rofi. Existing Rofi themes may need adapting: arbitrary widget trees, media queries, all Rofi units/properties, and its run/drun/window modes are not implemented. Wofi GTK stylesheets are not interchangeable with Qt stylesheets.

```rasi
@theme "qqs-dark"
window { width: 50%; height: 440px; location: northeast; x-offset: -20px; y-offset: 20px; }
listview { columns: 2; lines: 4; spacing: 8px; }
element selected { background-color: #88aaff; text-color: #111111; }
configuration { matching: "fuzzy"; hide-on-focus-loss: true; }
```

## Syntax

Use `selector { property: value; }`, UTF-8 strings in double quotes, integers, booleans, pixel values (`12px` or `12 px`), and colors. Width and height additionally accept percentages of the screen. Padding accepts 1–4 pixel values in CSS/Rasi order (top, right, bottom, left). Color formats are names, `#rgb`, `#rgba`, `#rrggbb`, `#rrggbbaa`, `rgb(r,g,b)`, and `rgba(r,g,b,a)` with alpha 0–1. Rasi alpha is last; qqs converts it for Qt.

`* { accent: #89b4fa; }` defines `@accent`. Variables may refer to other variables; cycles are reported. Global `font`, `text-color`, and `background-color` also style the panel. Fonts may use `"Family 12"` or a family plus separate size configuration.

C/C++ comments, nested block comments, comma-separated selectors, and optional `#` selector prefixes are supported. `@import "file.rasi"` merges another file; `@theme "name"` replaces previous theme selectors while retaining configuration. Includes are searched beside the current file, in the active configuration directory, and in bundled presets. Cyclic imports and missing files report errors. Rasi is data and executes no commands. Lua is an alternative active format selectable from the Themes menu.

## Layout and behavior

`mainbox { children: [ title, inputbar, listview, footer ]; }` changes order. Omitting title/footer hides them. The actual widget set is fixed; unknown children are rejected. `configuration { input-position: "bottom"; }` puts input after the list. `listview { columns: 2; }` enables a grid; `lines` limits the list area and leaves remaining items scrollable.

Window locations: `center`, `north`, `south`, `east`, `west`, `northeast`, `northwest`, `southeast`, `southwest`. Offsets can be negative. On the supported Hyprland Lua session qqs uses a dispatcher to position its own popup; other compositors may override placement. The window retains its floating/pinned behavior.

Search modes: `substring`, `prefix`, `fuzzy`, `disabled`. `matching: "normal"` aliases substring. Search fields are a comma-separated subset of `name,source,path`; case sensitivity is configurable. A pasted URL or absolute path leaves the collection visible and Enter imports it. Text queries filter existing rices, and Enter applies the selected result. Ctrl+Enter always adds the input. Sorting: `import`, `name`, `recent` (last successful launch). Single-click or double-click activation is configurable.

Keyboard configuration uses comma- or semicolon-separated Qt key sequences. Rofi aliases `kb-accept-entry`, `kb-row-down`, `kb-row-up`, `kb-cancel`, `matching`, and `case-sensitive` are supported. Default next/previous are Down/Up or Ctrl+J/Ctrl+K (one row at a time in a grid); Enter accepts, Escape hides, Shift+F10 opens the selected rice's menu, Ctrl+R reloads.

`live-reload: true` watches the active files and their imports while the popup is visible, including atomic editor saves. Hidden windows reload on reopening. During a live edit, invalid settings keep the previous appearance and show an error in the footer and log. Correcting the file reloads it again. Runtime selection and the search query are retained across theme reloads. Appearance files remain outside the app folder, preserving customization across upgrades.

## Selector properties

The table maps Rasi properties to the equivalent `configuration` key. `element selected.normal` is an alias for `element selected`.

| Selector | Properties |
| --- | --- |
| `window` | `width` → `width`, `height` → `height`, `background-color` → `background`, `background-image` → `background-image`, `border-color` → `border-color`, `border` → `border-width`, `border-radius` → `corner-radius`, `location` → `window-position`, `x-offset` → `window-offset-x`, `y-offset` → `window-offset-y` |
| `mainbox` | `padding` → `layout-padding`, `spacing` → `layout-spacing`, `children` → `layout-order` |
| `inputbar` | `spacing` → `input-spacing`, `position` → `input-position` |
| `entry` | `font` → `input-font`, `text-color` → `input-text-color`, `background-color` → `input-background`, `border` → `input-border-width`, `border-color` → `input-border`, `border-radius` → `input-radius`, `padding` → `input-padding`, `height` → `input-height`, `placeholder` → `placeholder`, `placeholder-color` → `placeholder-color` |
| `button` | `font` → `button-font`, `width` → `button-width`, `height` → `button-height`, `border-radius` → `button-radius`, `background-color` → `button-color`, `text-color` → `button-text-color`, `text` → `add-text`, `enabled` → `show-add-button` |
| `button hover` | `background-color` → `button-hover-color` |
| `listview` | `columns` → `list-columns`, `lines` → `list-lines`, `spacing` → `list-spacing`, `scrollbar` → `show-scrollbar`, `cycle` → `navigation-wrap` |
| `element` | `height` → `row-height`, `border` → `row-border-width`, `border-color` → `row-border`, `border-radius` → `row-radius`, `padding` → `row-padding`, `background-color` → `row-background`, `text-color` → `row-text-color`, `font` → `row-font` |
| `element-text` | `text-color` → `row-text-color`, `font` → `row-font` |
| `element-icon` | `size` → `icon-size` |
| `element selected` | `background-color` → `row-selected`, `text-color` → `row-selected-text-color`, `border-color` → `row-selected-border`, `border` → `row-selected-border-width` |
| `element alternate` | `background-color` → `row-alternate` |
| `element hover` | `background-color` → `row-hover` |
| `title` | `text` → `title-text`, `enabled` → `show-title`, `font` → `title-font`, `text-color` → `title-color` |
| `footer` | `text` → `footer-text`, `enabled` → `show-footer`, `font` → `footer-font`, `text-color` → `footer-color` |
| `message` | `text` → `message`, `font` → `font`, `text-color` → `text-color` |
| `progressbar` | `background-color` → `bar-color`, `border-color` → `bar-border-color`, `border` → `bar-border-width`, `border-radius` → `bar-radius`, `segments` → `segments`, `width` → `segment-width`, `height` → `segment-height`, `spacing` → `segment-gap` |

`footer` in loading.rasi sets the loading footer text/font, and `message` sets its main text/font. `progressbar` styles segments or a line (`configuration { bar-style: "line"; }`). Set `fullscreen: false` and width/height to use a smaller loading window. The animation is startup activity rather than a measured percentage.

## All menu configuration keys

Any supported property may also be set directly in `configuration`. Unspecified properties retain defaults. Empty font/color strings inherit the panel font/color; a size of zero inherits its panel size. The following table lists the exact defaults. Geometry is in logical pixels; font size is in points; durations are milliseconds.

| Key | Default |
| --- | --- |
| `row-hover` | `"#deefff"` |
| `add-text` | `"Add"` |
| `row-background` | `"#f3f8ff"` |
| `placeholder-color` | `"#7d91ae"` |
| `row-border` | `"#d4e6ff"` |
| `footer-text` | `"Ctrl + Shift + Q"` |
| `row-radius` | `12` |
| `background` | `"#eaf4ff"` |
| `wave-depth` | `5` |
| `input-border` | `"#70b8ff"` |
| `text-color` | `"#20365c"` |
| `input-background` | `"#f5f9ff"` |
| `corner-radius` | `28` |
| `border-color` | `"#349cff"` |
| `show-logo` | `true` |
| `placeholder` | `"Search rice or paste a URL / path"` |
| `row-height` | `40` |
| `row-selected` | `"#bddfff"` |
| `height` | `400` |
| `button-text-color` | `"#ffffff"` |
| `button-color` | `"#1767dc"` |
| `empty-text` | `"Add your first rice to get started."` |
| `width` | `560` |
| `font-size` | `11` |
| `font` | `"Noto Sans"` |
| `border-width` | `4` |
| `window-position` | `"center"` |
| `window-offset-x` | `0` |
| `window-offset-y` | `0` |
| `background-opacity` | `100` |
| `border-secondary-color` | `"#66d6ff"` |
| `background-gradient` | `true` |
| `layout-padding` | `26` |
| `layout-spacing` | `8` |
| `layout-order` | `"title,input,list,footer"` |
| `input-spacing` | `9` |
| `input-position` | `"top"` |
| `input-height` | `40` |
| `input-padding` | `12` |
| `input-radius` | `12` |
| `input-border-width` | `2` |
| `input-font` | `""` |
| `input-font-size` | `0` |
| `input-text-color` | `""` |
| `input-selection-color` | `"#ffffff"` |
| `input-selection-background` | `"#1767dc"` |
| `button-width` | `70` |
| `button-height` | `40` |
| `button-radius` | `12` |
| `button-hover-color` | `"#2978ed"` |
| `button-font` | `""` |
| `button-font-size` | `0` |
| `show-add-button` | `true` |
| `list-columns` | `1` |
| `list-lines` | `0` |
| `list-spacing` | `5` |
| `show-scrollbar` | `true` |
| `row-padding` | `20` |
| `row-border-width` | `1` |
| `row-selected-border-width` | `2` |
| `row-selected-border` | `"#349cff"` |
| `row-text-color` | `""` |
| `row-selected-text-color` | `""` |
| `row-alternate` | `""` |
| `row-font` | `""` |
| `row-font-size` | `0` |
| `row-alignment` | `"left"` |
| `show-icons` | `false` |
| `icon-size` | `24` |
| `row-show-index` | `false` |
| `row-show-source` | `false` |
| `list-sort` | `"import"` |
| `show-title` | `false` |
| `title-text` | `"qqs"` |
| `title-font` | `""` |
| `title-font-size` | `18` |
| `title-color` | `""` |
| `show-footer` | `true` |
| `footer-font` | `""` |
| `footer-font-size` | `0` |
| `footer-color` | `""` |
| `logo-size` | `36` |
| `search-mode` | `"substring"` |
| `search-case-sensitive` | `false` |
| `search-fields` | `"name,source,path"` |
| `navigation-wrap` | `true` |
| `mouse-single-click` | `true` |
| `hide-on-focus-loss` | `false` |
| `clear-query-on-open` | `true` |
| `live-reload` | `true` |
| `keys-accept` | `"Return;Enter"` |
| `keys-next` | `"Down;Ctrl+j"` |
| `keys-previous` | `"Up;Ctrl+k"` |
| `keys-close` | `"Escape"` |
| `keys-context` | `"Shift+F10"` |
| `keys-add` | `"Ctrl+Return"` |
| `keys-reload` | `"Ctrl+r"` |
| `stylesheet-file` | `""` |
| `stylesheet` | `""` |
| `background-image` | `""` |
| `background-image-opacity` | `100` |

## All loading configuration keys

| Key | Default |
| --- | --- |
| `animation-interval-ms` | `120` |
| `bar-color` | `"#ffffff"` |
| `font-size` | `32` |
| `bar-radius` | `0` |
| `font` | `"DejaVu Sans Mono"` |
| `segment-height` | `24` |
| `segments` | `14` |
| `pixelated-text` | `true` |
| `footer` | `"Please wait while the configuration loads."` |
| `bar-border-color` | `"#ffffff"` |
| `startup-timeout-ms` | `25000` |
| `minimum-display-ms` | `1800` |
| `segment-width` | `38` |
| `segment-gap` | `9` |
| `bar-border-width` | `3` |
| `text-color` | `"#ffffff"` |
| `footer-font-size` | `18` |
| `background` | `"#000000"` |
| `message` | `"Switching to {rice}…"` |
| `fullscreen` | `true` |
| `width` | `800` |
| `height` | `480` |
| `padding` | `50` |
| `spacing` | `65` |
| `message-alignment` | `"center"` |
| `footer-font` | `"DejaVu Sans Mono"` |
| `bar-style` | `"segments"` |
| `show-progress` | `true` |
| `show-footer` | `true` |

## Optional Qt stylesheet extension

For native widget states beyond the Rasi properties, set `stylesheet-file: "custom.qss"` (relative to the config directory) or `stylesheet: "..."`. Available object IDs: `QWidget#qqs`, `QWidget#inputbar`, `QLineEdit#entry`, `QPushButton#add`, `QListWidget#riceList`, `QLabel#title`, `QWidget#footer`, `QLabel#status`. Standard Qt `:hover`, `:focus`, `:selected`, `:disabled` rules can be used. This is an optional Qt extension, rather than Rofi CSS. File changes are watched too.

## Migration and format switching

Existing JSON settings are converted once into the selected active format and retained as backups. Existing Lua settings continue to work without automatic conversion to Rasi. Explicit format switching preserves resolved menu and loading settings and stores the format in `theme-format`. Any imported Rasi variables/imports are flattened when converting to Lua, so the resulting snapshot is self-contained. Rice/session data continues using JSON independently of appearance settings.

## Custom logos, icons and loading backgrounds

Lua `logo_file` selects a custom PNG/SVG/JPEG logo; an empty value retains the supplied logo. `row_icon_file` sets a common rice icon, while `row_icon_name` chooses an installed icon-theme name. Individual rices can override the icon using **Choose list icon…** in their context menu. Enable `show_icons` to display rice icons.

Menu and loading themes both support `background_image` and `background_image_opacity` (0–100). Images are scaled to cover the window. Relative asset paths and `stylesheet_file` resolve inside `~/.config/qqs/`. Menu images, custom logos/icons and external stylesheet files are watched for live changes.

In Rasi, these extended options are available in `configuration` using hyphenated names, for example `logo-file`, `row-icon-file`, and `background-image-opacity`.

## Liquid Glass

Select **Appearance presets → Liquid Glass**, or set `preset = "qqs-liquid-glass"` in `menu.lua`. It uses translucent surfaces, a bright contour, soft reflections, and translucent hover/selection states. `glass_effect`, `glass_highlight_color`, and `glass_strength` (0–100) control the reflection layer. For example:

```lua
return {
  preset = "qqs-liquid-glass",
  glass_strength = 55,
  corner_radius = 32,
}
```

Behind-window blur is supplied by the compositor, rather than painted from a screenshot. On Hyprland it requires `decoration.blur.enabled` and a window that is allowed to blur. qqs preserves your global blur configuration. Without compositor blur the theme still renders translucent surfaces and highlights. **Restore previous appearance** returns to the theme used before selecting Liquid Glass.

## Original theme

Select **Appearance presets → Original**, or set `preset = "qqs-original"` in `menu.lua`, to restore the original pale blue panel, blue borders, rounded rows and supplied logo. The preset resets all menu appearance and behavior settings to the original defaults. Loading-screen settings are independent.

## Context-sensitive instructions

Set `footer_text = "{shortcuts}"` in Lua (or `footer-text: "{shortcuts}";` in Rasi) to show instructions generated from the configured keyboard bindings. The accept-key description changes to **import source** when the field contains an import URL/path; otherwise it says **start selected rice**. A custom footer string stays unchanged.

The loading message supports `{rice}`, replaced by the selected saved rice name. The default is `Switching to {rice}…`. The import confirmation means the rice was saved to the collection; starting it is a separate action. Import-source labels identify the actual destination (GitHub, original folder, QML file or ZIP archive). The log viewer has separate buttons for the launcher log and Quickshell log.
