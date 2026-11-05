# ComfyUI-AssetManager

An in-panel **asset manager** for ComfyUI that auto-archives every image, video, and audio asset you generate — browse, search, preview, batch-delete, and one-click backup.

集成进 ComfyUI 网页的**资产管理面板**，自动归档生成的图片、视频和音频，支持浏览、搜索、预览、批量删除和一键备份。

## ✨ Features · 功能亮点

- **Auto-archive** — a background thread watches the output directory and archives every image, video, and audio asset (on first run it can also import existing files), extracting **prompt / positive-negative / params / models & LoRA / full workflow** where available. It reads image/video container metadata and uses ComfyUI execution history as a fallback; audio metadata and duration are read with PyAV when available.<br>
  **自动归档** — 后台线程监视 output 目录并归档图片、视频和音频（可选择导入已有文件），尽可能提取**提示词 / 正负词 / 参数 / 模型与 LoRA / 完整工作流**。读取图片/视频容器元数据，并可回查 ComfyUI 执行记录；PyAV 可用时也会读取音频元数据和时长。
- **Dual views** — grid view + **calendar view** (grouped by date, with daily image/video/audio count badges; click a day to see that day's assets).<br>
  **双视图浏览** — 网格视图 + **日历视图**（按日期归档，每天显示图片/视频/音频数量徽标，点某天看当天产物）。
- **Search & filter** — full-text search by prompt/model/filename/date; filter by image/video/audio, by **source folder**, or by **your own category**.<br>
  **搜索与过滤** — 按提示词/模型/文件名/日期全文搜索，可按图片/视频/音频、**自建分类**（两级树）过滤，需要时还能按**来源文件夹**筛。
- **Category tree** — date grouping stays, but the sidebar is now a single, folder-like tree: create categories, nest one level of sub-categories under them, and multi-select assets to move them in. Selecting a parent includes everything in its sub-categories. Moving only rewrites archive metadata — original files and the archive layout are untouched, so it is instant and reversible. The source-folder filter is still there, folded away at the bottom.<br>
  **分类树** — 日期分组保留，但左侧只剩一棵像文件夹的树：建分类、在分类下再挂一层子分类、多选产物移进去。选中父分类会把子分类里的产物一并算进来。移动只改归档元数据，不动原始文件、不动归档目录结构，毫秒级且可逆；「来源文件夹」筛选仍在，收在侧栏底部。
- **Preview & reproduce** — view full-size images, play videos and audio, copy prompt, download `workflow.json` (drag it back onto the canvas to restore the whole workflow).<br>
  **预览与复现** — 查看大图、播放视频和音频、复制提示词、下载 workflow.json（拖回画布还原整套工作流）。
- **Batch delete** — multi-select (Ctrl/Shift click or drag a box on empty space) and delete from disk in one click (archive copy + original output file); single delete too.<br>
  **批量删除** — 多选（Ctrl/Shift 点选，或在空白处拖框）后一键从硬盘删除（归档副本 + output 原始文件），单个删除也可。
- **Live refresh** — the panel auto-syncs every 8 seconds; files manually copied into the output directory get archived, and manual deletions disappear automatically.<br>
  **实时刷新** — 面板每 8 秒自动同步，手动复制进输出目录的文件也会被归档、手动删除也会自动消失。
- **Output directory switching** — change the output directory in settings; new assets save there instantly and it's **restored automatically after ComfyUI restarts**.<br>
  **输出目录切换** — 设置里改输出目录，新产物即时改存；**重启 ComfyUI 后自动恢复**。
- **Directory picker** — the output/archive/backup fields each have a "Browse…" button; pick a folder with the mouse, no manual path typing.<br>
  **目录点选** — 输出/归档/备份三个目录都带「浏览…」按钮，鼠标点选目录，无需手输路径。
- **One-click backup** — package "asset library + workflows + plugin config" into a zip.<br>
  **一键备份** — 把「资产库 + 工作流 + 插件配置」打包成 zip。

### Differentiators · 差异化

- Calendar browsing by date (most similar plugins only have a grid list)<br>
  日历按日期归档浏览（多数同类插件只有网格列表）
- Batch delete + live scan refresh (manual drag-in/delete also syncs)<br>
  批量删除 + 实时扫描刷新（手动拖入/删除文件也会同步）
- Output directory switching, auto-restored after restart<br>
  输出目录切换且重启自动恢复
- Directory picker — no absolute path typing required<br>
  目录浏览器点选，不依赖手输绝对路径

## 📸 Screenshots · 界面预览

| Grid · 网格视图 | Calendar · 日历视图 |
|---|---|
| ![Grid](assets/screenshots/01-grid.png) | ![Calendar](assets/screenshots/02-calendar.png) |

| Preview · 预览详情 | Settings · 资产设置 | Browse · 目录点选 |
|---|---|---|
| ![Preview](assets/screenshots/03-preview.png) | ![Settings](assets/screenshots/04-settings.png) | ![Browse](assets/screenshots/05-browse-dir.png) |

## 📦 Installation · 安装

### Method 1: ComfyUI-Manager (recommended) · 方法一：ComfyUI-Manager（推荐）

Search for `AssetManager` in the Manager and install.<br>
在 Manager 里搜索 `AssetManager` 安装。

### Method 2: git clone · 方法二：git clone

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Wumihaze/ComfyUI-AssetManager.git
```

### Method 3: Manual download · 方法三：手动下载

Download the repo zip and extract it into `ComfyUI/custom_nodes/`, keeping the folder name `ComfyUI-AssetManager`.<br>
下载本仓库 zip，解压到 `ComfyUI/custom_nodes/` 下，目录名保持 `ComfyUI-AssetManager`。

> Dependencies: Python ≥ 3.9, `Pillow`, and PyAV (`av>=10.0.0`). Audio archiving and browser playback still work if PyAV is unavailable, but embedded audio metadata/duration and video thumbnails will be unavailable.<br>
> 依赖：Python ≥ 3.9、`Pillow` 和 PyAV（`av>=10.0.0`）。即使 PyAV 不可用，音频仍可归档和在浏览器播放，但无法读取音频容器元数据/时长或生成视频缩略图。

## 🚀 Usage · 使用

1. Start ComfyUI and click "**Asset Manager**" in the top menu bar to open the panel.<br>
   启动 ComfyUI，顶部菜单栏点「**资产管理**」打开面板。
2. Top toolbar: search box, grid/calendar toggle, all/image/video/audio filter, multi-select, backup, scan, settings.<br>
   顶部工具栏：搜索框、网格/日历切换、全部/图片/视频/音频过滤、多选、备份、扫描、资产设置。
3. Left sidebar: one **My categories** tree that takes the full height. Sub-categories are indented with a blue bar, and a parent's count includes its children. Click any row to filter the grid; click "All categories" to clear. **Source folders** sits collapsed at the bottom — click its header to expand (it remembers the active folder filter and shows it as a chip with a ✕ to clear).<br>
   左侧导航：一棵占满高度的 **我的分类** 树。子分类缩进并带蓝色竖条，父分类的条数包含其子分类。点任意一行右侧立刻只剩该范围，点「全部分类」恢复。**来源文件夹** 默认收在底部，点标题展开；已选的文件夹筛选会显示成小标签，点 ✕ 清除。
4. Multi-select: click ☑ Multi-select to enter it, or just **Ctrl/Cmd+click** / **Shift+click** on any asset — both switch to multi-select automatically. **Shift+click** selects the whole range from the last clicked asset, **Ctrl+click** toggles one, and **dragging on empty space** draws a box that selects everything it touches (hold Ctrl/Shift to add to the current selection instead of replacing it).<br>
   多选：点「☑ 多选」进入，也可以直接 **Ctrl/Cmd + 单击** 或 **Shift + 单击**，会自动切进多选。**Shift + 单击** 从上次点击的产物起整段连选，**Ctrl + 单击** 单个加/减，**在空白处拖拽** 拉框选中框到的全部（按住 Ctrl/Shift 是在现有选择上追加，不覆盖）。
5. Select assets → **Move to category** → a dialog lists your categories as radio rows (the one your assets already belong to is marked **current**), with a search box once there are many, a separate **Uncategorized (clear)** action at the bottom, and a create-and-move row. Moving rewrites only archive metadata.<br>
   勾选产物 →「**移到分类**」→ 弹窗把分类列成单选项（这些产物当前所属的分类会标 **当前**），分类多了会显示搜索框，底部单独一条 **未分类（移出分类）**，以及新建并移入。移动只改归档元数据。
6. **⚙ Manage categories** (the gear in the My categories header) → rename (✎), delete (✕), or create. On a top-level row, **＋** adds a sub-category right under it. Deleting a category never deletes files: its assets become uncategorized and its sub-categories move up one level.<br>
   分类区标题旁的 **⚙** → 重命名（✎）/ 删除（✕）/ 新建。一级分类行上的 **＋** 直接在它下面建子分类。删除分类**不会删除文件**：该分类下的产物变回「未分类」，它的子分类上移一层。
7. Click an asset → preview dialog: play audio/video, copy prompt / download workflow.json (drag back to canvas to reproduce) / delete from disk.<br>
   点产物 → 预览弹窗：播放音频/视频、复制提示词 / 下载 workflow.json（拖回画布复现）/ 从硬盘删除。

Audio files are auto-archived for `.wav`, `.mp3`, `.flac`, `.ogg`, `.opus`, `.m4a`, `.aac`, `.aiff`, `.aif`, and `.wma`. Playback uses the browser's native audio player, so actual playback depends on the browser's codec support. Audio metadata and duration are best-effort when PyAV is installed; if metadata is absent, ComfyUI execution history is queried for the prompt/workflow.<br>
音频自动归档支持 `.wav`、`.mp3`、`.flac`、`.ogg`、`.opus`、`.m4a`、`.aac`、`.aiff`、`.aif` 和 `.wma`。预览使用浏览器原生播放器，具体能否播放取决于浏览器支持的编码格式。安装 PyAV 时会尽力读取音频元数据和时长；文件没有提示词时会尝试从 ComfyUI 执行记录回查提示词/工作流。

## ⚙️ Configuration · 配置

A `config.json` is generated on your first settings save (template at [`config.example.json`](config.example.json)). Everything can also be changed in the panel's "⚙ Settings".<br>
首次保存设置时自动生成 `config.json`（模板见 [`config.example.json`](config.example.json)）。所有配置也可在面板「⚙ 资产设置」里直接改：

| Key · 键 | Description · 说明 |
|---|---|
| `output_dir` | Custom output directory (empty = ComfyUI default `output`) / 自定义输出目录（空 = 用 ComfyUI 默认 output） |
| `archive_dir` | Asset archive directory (empty = `<ComfyUI>/asset_archive`) / 资产归档库目录（空 = `<ComfyUI>/asset_archive`） |
| `backup_dir` | Backup zip directory (empty = `<ComfyUI>/asset_backups`) / 备份 zip 存放目录（空 = `<ComfyUI>/asset_backups`） |
| `auto_archive` | Auto-archive new assets (true/false) / 是否自动归档新产物（true/false） |
| `archive_existing` | On first run, also archive assets already in the output directory (false = only new assets after install) / 首次运行时是否也归档 output 里已有的历史产物（false = 只归档安装后的新产物） |
| `thumb_width` | Thumbnail width (px) / 缩略图宽度(px) |
| `interval_sec` | Archive scan interval (seconds) / 归档扫描间隔(秒) |

> ℹ️ 视频元数据/缩略图以及音频元数据读取使用 **PyAV** 在进程内完成，不会启动 ffmpeg/ffprobe 外部进程。
> 如果 PyAV 不可用，仍可归档和播放音频，但无法提取容器元数据/时长或生成视频缩略图。

### 📍 安装位置与盘符 · Install location

代码里**没有任何写死的盘符或绝对路径**，三个目录都在运行时确定：

- 插件位置：`BASE_DIR = dirname(__file__)` —— 装在哪个盘、哪个目录，就以哪里为准；
- 默认归档/备份：`<ComfyUI>/asset_archive`、`<ComfyUI>/asset_backups`（由插件目录 `../..` 推导）；
- 默认输出：`folder_paths.get_output_directory()`，即 ComfyUI 自己探测到的 output。

三个目录都可在面板「⚙ 资产设置」里改成任意位置（**由用户自主选择**）。若 `config.json` 里残留了
另一台机器或已移除盘符的路径，插件启动时会自动回退到上面的默认目录，并通过 `/asset/config` 的
`warnings` 字段说明原因——不会因为一个坏路径导致插件加载失败。

No drive letter or absolute path is hardcoded. `BASE_DIR` comes from `__file__`, the default archive/backup
directories are derived from the plugin location, and the output directory comes from `folder_paths`. All three
are user-configurable in settings; if a configured path is unavailable (e.g. the plugin was copied from another
machine), the plugin falls back to the defaults and reports the reason via `warnings` instead of failing to load.

## 📁 Directory structure · 归档目录结构

```
<archive dir>/
├─ categories.json              # your categories (flat list) / 自建分类清单
└─ 2026-08-12/
   └─ 110358_ComfyUI_00016/
      ├─ ComfyUI_00016_.png       # original asset / 原产物
      ├─ info.json                # full info (prompt/params/models/workflow) / 完整信息(提示词/参数/模型/工作流)
      ├─ prompt.txt               # human-readable prompt / 人类可读提示词
      ├─ workflow.json            # drag back into ComfyUI to rerun / 拖回 ComfyUI 复跑
      └─ thumb.jpg                # thumbnail (first frame for videos) / 缩略图(视频取首帧)
```

`info.json` also carries `folder` (source subdirectory, auto-derived) and `category` (id of your category, or `null`).
Older records without these fields are derived on the fly from `source_rel`, so no migration is needed.<br>
`info.json` 还记录 `folder`（来源子目录，自动派生）与 `category`（自建分类 id，未分类为 `null`）。
老记录缺少这两个字段时由 `source_rel` 即时派生，无需迁移。

## 📝 Notes · 说明

- Archiving is a **copy**; it doesn't affect ComfyUI previews. Files are only touched on disk when you delete them.<br>
  归档是**复制**，不影响 ComfyUI 预览；删除时才真正动硬盘。
- The archive directory can be migrated anytime — just change `archive_dir` in settings (old data stays where it was).<br>
  归档目录可随时迁移，只要在设置里改 `archive_dir` 即可（旧数据保留在原目录）。

### 🔍 为什么有的产物"未检测到提示词"？ · Troubleshooting prompt extraction

提示词优先从**文件内嵌元数据**读取（PNG `tEXt` / WebP `EXIF` / MP4-MKV ffmpeg tag）。
文件里没有元数据时，插件会再从 **ComfyUI 服务端执行记录**里按文件名找回当时那次执行的
提示词与工作流，所以正常情况下跑出来的图都能带上提示词。<br>
Prompts are read from the file's embedded metadata first; if absent, the plugin falls back to
ComfyUI's server-side execution history (matched by output filename), so generated images normally
carry their prompt.

预览弹窗会说明具体原因，常见三种：

| 提示 | 含义 | 怎么办 |
|---|---|---|
| ⚠ 文件本身不带 ComfyUI 元数据 | 图片不是 ComfyUI 直接存的：浏览器另存、手机/微信转存后拖进 output 目录；或 ComfyUI 启动时带了 `--disable-metadata`（隐私模式） | 用「保存图像 / SaveImage」节点跑出来的图会自动归档并带上提示词；若用了 `--disable-metadata`，去掉该参数即可 |
| 这次运行没有文本提示词节点 | 工作流里确实没有 CLIPTextEncode 一类节点（纯图像处理、证件照、放大等工作流） | 正常现象，无需处理 |
| 提示词由 ComfyUI 执行记录找回 | 文件本身没写元数据，但已从服务端历史补回 | 正常现象（说明该文件不带元数据，但提示词已找回） |

> 注：归档是复制原始文件，**不会**给你的图片补写元数据；找回的提示词只写进归档目录的
> `info.json` / `prompt.txt` / `workflow.json`。

## 🔒 Security · 安全说明

本插件从 **v1.0.4** 起按 Comfy Registry 的安全标准收紧了输入面（此前版本因
`policy-v0.5 command-injection` / `policy-v0.2 ARBITRARY_FILE_LAUNCH` 被标记，相关修复见下）：

- **不启动任何外部进程**：视频元数据/缩略图及音频元数据读取由 **PyAV 在进程内**完成，
  代码中**已无 `subprocess` / `os.system` / `eval` / `exec`**，从根上消除了命令注入面。
  音频播放由浏览器原生播放器完成。
- **配置写入白名单**：`/asset/set_config` 只接受固定的可配置键，任何未知字段都会被拒绝
  并在响应 `errors` 中说明，不会再被写进运行时配置。
- **数值与类型校验**：数值项有上下限；布尔项必须是真正的布尔值。
- **路径沙箱**：媒体文件读取、工作流下载、目录浏览都限制在 output / archive / backup 目录范围内；
  删除等写操作会校验目标仍在归档目录内（防目录穿越）。
- **媒体接口只服务登记文件**（v1.0.6 起）：`/asset/file` 不再"凡在归档目录内就返回"，
  而是要求路径形如 `<日期>/<任务>/<文件名>`，且文件名必须出现在该任务的 `info.json`
  （`media` / `thumb` / `workflow.json`）里；`info.json`、状态文件、任意本机绝对路径一律 404。
- **目录互不重叠**：配置与输出目录切换都会校验 output / archive / backup 三者互不包含，
  避免"归档被当成新产物再次归档"的递归增长，也避免备份把自身打进 ZIP。
- **不跟随符号链接**：扫描、归档、列表、备份都会跳过符号链接并校验解析后仍在根目录内，
  防止有人借链接把根目录外的文件复制进归档或备份。
- **备份原子化**：备份先写唯一临时文件再原子改名（时间戳精确到微秒 + 随机后缀），
  同一秒并发备份不会互相覆盖。
- **目录浏览最小化**：在允许根的父级链上只列出"通往允许根"的那一级目录名，
  不泄露同级无关目录；隐藏项与符号链接不列出。
- **分类接口加固**（v1.0.7 起）：`/asset/category` 与 `/asset/assign` 拒绝非对象请求体、
  校验 `action` / `id` / `name` / `run_ids` 的类型与长度上限（名称 ≤40 字符、单次 ≤500 条）；
  分类名只当纯字符串存储，不参与任何路径拼接（写 `../..` 也只会得到一个名字），
  前端一律用 `textContent` 渲染，不存在把分类名当 HTML 执行的路径。
  `run_ids` 会逐个 `resolve()` 并校验解析后仍在归档目录内，`../`、绝对路径、
  软链接目录一律跳过并回报 `invalid path`；删除分类只把记录改回未分类，不删任何文件。

No external process is ever launched: video metadata and thumbnails are handled in-process with
PyAV, and the codebase contains no `subprocess` / `os.system` / `eval` / `exec`. Configuration keys
are written through a strict allowlist, numeric options are range-checked, and all file/directory
access is confined to the configured output / archive / backup roots. Since v1.0.6 the media route
serves only manifest-listed files, the three roots are mutually non-overlapping, symlinks are
skipped and re-validated after resolution, backups are written atomically to unique files, and
directory browsing only reveals entries on the path to an allowed root.

## 📄 License

[MIT](LICENSE) © 2026 Wumihaze
