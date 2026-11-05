# Security · 安全说明

本插件是跑在你本机 ComfyUI 里的回环服务，这里说明它怎么处理外部输入、路径和写操作。
如果你要审计或报告问题，看这一页就够了。

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
- **跨站写请求拦截**（v1.0.12 起）：所有会改动磁盘的接口（改配置 / 改输出目录 / 删除 /
  批量删除 / 建改分类 / 移分类 / 扫描 / 备份）都会校验 `Origin`。带 `http(s)` 来源且与
  `Host` 不一致的请求直接 **403**，挡住"随便打开一个网页就能让你的本机 ComfyUI 删文件"
  这一类 CSRF；不带 `Origin`（curl、脚本、同源导航）和 `Origin: null` 照常放行。
- **报错不回显绝对路径**（v1.0.12 起）：所有接口的异常文本都换成固定文案
  （`Category operation failed` / `Assign failed` / `Cannot create <key>` /
  `Cannot read directory` / `Scan failed`），不再把 `OSError` 的原始字符串
  （里面通常带完整盘符路径）返回给前端。
- **媒体路径按字面形状校验**（v1.0.12 起）：`/asset/file` 在 `resolve()` 之前先按字面
  检查是不是恰好三段 `<日期>/<任务>/<文件名>`，任何一段为空、`.` 或 `..` 直接拒绝。
  这样 `2026-10-31/run-1/../run-1/a.png` 这类"解析后仍在目录内"的路径也进不来。
- **扫描不会因为一个坏目录整批失败**（v1.0.12 起）：归档时日期目录被同名文件占位、
  磁盘写满等 I/O 错误只会跳过当前这一个文件（并清理掉写了一半的目录），不再让整次扫描
  抛异常、接口 500。
- **状态文件不当作可信输入**（v1.0.12 起）：去重时从 `archive_state.json` 读到的历史路径
  必须恰好两段且 `resolve()` 后仍在归档目录内、不是软链接，否则丢弃该条记录。
- **分类顺序参数同样走校验**：`direction` 只接受 `up` / `down`，`pinned` 必须是真正的
  布尔值（`"yes"`、`1`、`"true"` 一律拒绝）；读取 `categories.json` 时不再按上限截断，
  手工改大的文件不会被下一次保存"静默删掉"。

No external process is ever launched: video metadata and thumbnails are handled in-process with
PyAV, and the codebase contains no `subprocess` / `os.system` / `eval` / `exec`. Configuration keys
are written through a strict allowlist, numeric options are range-checked, and all file/directory
access is confined to the configured output / archive / backup roots. Since v1.0.6 the media route
serves only manifest-listed files, the three roots are mutually non-overlapping, symlinks are
skipped and re-validated after resolution, backups are written atomically to unique files, and
directory browsing only reveals entries on the path to an allowed root. Since v1.0.12 every mutating
route rejects cross-origin `Origin` headers with 403, error responses never echo absolute paths, the
media route validates the literal `<date>/<run>/<file>` shape before resolving, a single unwritable
directory no longer aborts a whole scan, and paths read back from the state file are re-validated
before use.

回归测试：`tests/test_security.py` 覆盖上述全部输入面（47 个用例，含跨站 403、类型混淆、
目录穿越、符号链接、超长路径、损坏状态文件）；完整用例集共 122 个，全部通过。
