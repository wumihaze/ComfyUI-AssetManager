# 发版前检查 · Release checklist

Registry 的版本一旦被 `Flagged` 就不会推给 Manager，改起来要再发一版。所以**动版本号之前**先把这一页走完，
不要等推送完再看结果。

## 1. 一条命令（必跑）

```bash
python tools/policy_check.py
```

全绿（退出码 0）才能发版；任何一项 `✘` 会列出文件和行号。

覆盖 13 项：危险调用、出站网络、路由同源保护、报错路径回显、前端 XSS、依赖一致性、版本一致性、
Registry 元数据、图标尺寸、发布包排除、单元测试、HTTP 冒烟。`--static` 可跳过后两项快速自查。

## 2. Registry 安全策略对照

| 策略 | 要求 | 本仓库的做法 | 谁在保证 |
|---|---|---|---|
| `policy-v0.5` 命令注入 | 不得把外部输入拼进命令执行 | 全仓无 `subprocess` / `os.system` / `shell=True` / `eval` / `exec` | 自检第 1 项 |
| `policy-v0.2` 任意文件执行 | 不得启动外部程序或执行任意文件 | 视频缩略图、音频元数据由 **PyAV 在进程内**处理，不调用 ffmpeg | 自检第 1 项 |
| 出站网络 / SSRF | 插件只服务回环，不主动外连 | 无 `urllib.request` / `requests` / `socket`；`urllib.parse` 仅解析 `Origin` | 自检第 2 项 |
| CSRF | 写操作不能被第三方页面触发 | 9 个写接口全部 `@_same_origin_only`，跨站 `Origin` 直接 403 | 自检第 4 项 |
| 路径穿越 | 文件读写删都限制在配置根内 | 读：`safe_media_path` 字面三段 + `resolve` + 白名单；写：`_run_dir_for`；删：`delete_run` 双重校验 | 自检第 5 项 + HTTP 冒烟 |
| 报错不泄露路径 | 异常文本不得含绝对路径 | 所有 `error` 字段是固定文案，前端再做中文映射 | 自检第 6 项 |
| 前端注入 | 不把数据当 HTML | 只用 `textContent`，`innerHTML` 仅用于空串清空 | 自检第 7 项 |
| 符号链接 | 不能借链接越界 | 扫描、归档、列表、备份、删除、备注均显式跳过或校验 | 单元测试 |

## 3. 人工确认（脚本查不出来的）

新增接口或改动了文件操作时，逐条过一遍：

- [ ] 新写的 `POST` 路由是否加了 `@_same_origin_only`
- [ ] 新的文件读写是否都限制在 output / archive / backup 三个根内
- [ ] 新的 `info.json` / 配置字段是否有类型与长度校验
- [ ] 新的删除类操作是否先校验「解析后仍在根目录内」且不跟随软链
- [ ] 前端新加的数据展示是否用 `textContent`（不要拼 HTML 字符串）

## 4. 发版流程

1. `python tools/policy_check.py` 全绿
2. `pyproject.toml` 与 `__init__.py` 的 `version` 同步改（自检会卡）
3. README 的功能说明、`SECURITY.md` 的安全条目同步更新
4. 提交并**合并到 `master`**（发布 workflow 只在 `master` + `pyproject.toml` 变化时触发）
5. 打 tag `vX.Y.Z` 并推送
6. 建 GitHub Release（说明可参照上一版）
7. 到 [Registry](https://registry.comfy.org/nodes/comfyui-asset-manager) 确认状态从 `Pending` 变 `Active`

> 推送代码但没改 `pyproject.toml` 时不会重新发布——所以**发版后再修的 bug 要再发一版**才会进 Registry 的包。
