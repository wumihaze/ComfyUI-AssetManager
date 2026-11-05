#!/usr/bin/env python3
"""发版前的自检: 逐条对照 Comfy Registry 的安全策略 + 本仓库的硬性约束。

零依赖, 不启动 ComfyUI, 不联网。发版前跑一次, 全绿再推。

    python tools/policy_check.py            # 静态检查 + 单元测试
    python tools/policy_check.py --static   # 只做静态检查(CI 里跑得快)

退出码 0 = 全过, 1 = 有问题(会逐条列出)。
"""

import argparse
import ast
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY_FILES = [p for p in ROOT.rglob("*.py")
            if "tests" not in p.parts and ".git" not in p.parts and "tools" not in p.parts]
JS_FILES = list((ROOT / "web").rglob("*.js"))

results = []   # (ok, 标题, 详情)


def configure_stdio():
    """控制台编码装不下中文时切到 UTF-8。

    Windows 的 CI runner 默认编码是 cp1252, `print("发版前自检 ✔ …")` 会直接
    UnicodeEncodeError, 整个检查还没开始就退出码 1。GitHub 的日志本身是 UTF-8,
    切过去反而显示正常; 编码本来就够用(utf-8/gbk)时不动。
    """
    for stream in (sys.stdout, sys.stderr):
        enc = getattr(stream, "encoding", None) or "ascii"
        try:
            "发版前自检 ✔ ✘".encode(enc)
        except (UnicodeEncodeError, LookupError):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


configure_stdio()


def check(ok, title, detail=""):
    results.append((bool(ok), title, detail))


def read(p):
    return p.read_text(encoding="utf-8", errors="replace")


def scannable_lines(path):
    """返回 [(行号, 原文)]，跳过注释行与文档字符串。

    不用 ast.unparse 重写源码: 那样行号会和真实文件对不上, 报错定位不到地方。
    """
    try:
        src = read(path)
        tree = ast.parse(src)
    except SyntaxError:
        return list(enumerate(read(path).splitlines(), 1))
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None) or []
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                skip.update(range(body[0].lineno, (body[0].end_lineno or body[0].lineno) + 1))
    out = []
    for i, line in enumerate(src.splitlines(), 1):
        if i in skip or line.lstrip().startswith("#"):
            continue
        out.append((i, line))
    return out


# ---------------------------------------------------------------------------
# 1. 命令注入 / 任意文件执行 —— 这两条正是 1.0.0~1.0.4 被 Flagged 的原因
# ---------------------------------------------------------------------------
FORBIDDEN = {
    "subprocess": r"\bsubprocess\b",
    "os.system": r"\bos\.system\s*\(",
    "os.popen": r"\bos\.popen\s*\(",
    "os.exec*": r"\bos\.exec[a-z]*\s*\(",
    "os.spawn*": r"\bos\.spawn[a-z]*\s*\(",
    "pty": r"\bpty\.spawn\s*\(",
    "commands": r"\bcommands\.getoutput\s*\(",
    "shell=True": r"shell\s*=\s*True",
    "eval(": r"\beval\s*\(",
    "exec(": r"\bexec\s*\(",
    "compile(": r"\bcompile\s*\(",
    "__import__": r"\b__import__\s*\(",
    "importlib.import_module": r"\bimportlib\.import_module\s*\(",
    "pickle": r"\bpickle\.",
    "marshal": r"\bmarshal\.",
    "ctypes": r"\bctypes\b",
}


def check_forbidden_calls():
    hits = []
    for p in PY_FILES:
        for lineno, line in scannable_lines(p):
            for name, pat in FORBIDDEN.items():
                if re.search(pat, line):
                    hits.append("%s:%d %s" % (p.relative_to(ROOT).as_posix(), lineno, name))
    check(not hits,
          "命令注入 / 任意文件执行面 (policy-v0.5 / policy-v0.2)",
          "; ".join(hits) if hits else "%d 个 .py 文件里没有 subprocess/eval/exec/pickle/ctypes 等调用"
          % len(PY_FILES))


# ---------------------------------------------------------------------------
# 2. 出站网络 —— 插件只应服务回环, 不应主动连外部
# ---------------------------------------------------------------------------
NETWORK = {
    "urllib.request": r"\burllib\.request\b",
    "urlopen": r"\burlopen\s*\(",
    "requests.": r"\brequests\.(get|post|put|delete|Session|request)\b",
    "httpx": r"\bhttpx\.",
    "socket": r"\bsocket\.(socket|create_connection)\b",
    "http.client": r"\bhttp\.client\b",
    "aiohttp.ClientSession": r"\baiohttp\.ClientSession\b",
}


def check_network():
    hits = []
    for p in PY_FILES:
        for lineno, line in scannable_lines(p):
            for name, pat in NETWORK.items():
                if re.search(pat, line):
                    hits.append("%s:%d %s" % (p.relative_to(ROOT).as_posix(), lineno, name))
    check(not hits, "无出站网络请求 (SSRF 面)", "; ".join(hits) if hits else "没有 urllib.request/requests/socket 调用")


# ---------------------------------------------------------------------------
# 3. 所有写接口都必须带同源校验
# ---------------------------------------------------------------------------
def parse_routes():
    """返回 [(method, path, 是否有 _same_origin_only)]"""
    src = read(ROOT / "__init__.py").splitlines()
    out = []
    for i, line in enumerate(src):
        m = re.search(r'routes\.(get|post|put|delete)\(\s*["\']([^"\']+)["\']', line)
        if not m:
            continue
        method, path = m.group(1).lower(), m.group(2)
        guarded = False
        for nxt in src[i + 1:i + 5]:
            if "_same_origin_only" in nxt:
                guarded = True
            if nxt.lstrip().startswith(("async def", "def ")):
                break
        out.append((method, path, guarded))
    return out


def check_write_routes():
    routes = parse_routes()
    unguarded = [p for (m, p, g) in routes if m != "get" and not g]
    check(routes, "路由能被解析", "共 %d 个" % len(routes))
    check(not unguarded,
          "所有写接口都带 @_same_origin_only (CSRF)",
          "缺保护: %s" % ", ".join(unguarded) if unguarded
          else "%d 个写接口全部受保护" % len([1 for m, _, _ in routes if m != "get"]))


# ---------------------------------------------------------------------------
# 4. 报错不回显绝对路径
# ---------------------------------------------------------------------------
def check_error_leak():
    hits = []
    for p in PY_FILES:
        for lineno, line in scannable_lines(p):
            if re.search(r'"error"\s*:\s*(str\(|repr\(|f["\'].*\{e\})', line):
                hits.append("%s:%d" % (p.relative_to(ROOT).as_posix(), lineno))
    check(not hits, "报错不回显异常文本(绝对路径)",
          "可疑: %s" % ", ".join(hits) if hits else "所有 error 字段都是固定文案")


# ---------------------------------------------------------------------------
# 5. 前端不把数据当 HTML 插入
# ---------------------------------------------------------------------------
def check_frontend_html():
    hits = []
    for p in JS_FILES:
        for i, line in enumerate(read(p).splitlines(), 1):
            m = re.search(r"\.innerHTML\s*=\s*(.+?);", line)
            if m and m.group(1).strip() not in ('""', "''", "``"):
                hits.append("%s:%d" % (p.relative_to(ROOT).as_posix(), i))
    check(not hits, "前端无带内容的 innerHTML (XSS)",
          "可疑: %s" % ", ".join(hits) if hits else "只用 textContent / 空串清空")


# ---------------------------------------------------------------------------
# 6. 依赖与版本一致性
# ---------------------------------------------------------------------------
def pyproject():
    raw = read(ROOT / "pyproject.toml")
    try:
        import tomllib
        return tomllib.loads(raw), raw
    except Exception:
        return {}, raw


def check_dependencies(cfg, raw):
    req = []
    for line in read(ROOT / "requirements.txt").splitlines():
        line = line.split("#")[0].strip()
        if line:
            req.append(line)
    deps = cfg.get("project", {}).get("dependencies")
    if deps is None:                       # tomllib 不可用时的兜底
        m = re.search(r"dependencies\s*=\s*\[(.*?)\]", raw, re.S)
        deps = re.findall(r'"([^"]+)"', m.group(1)) if m else []
    norm = lambda xs: sorted(x.replace(" ", "").lower() for x in xs)
    check(norm(req) == norm(deps),
          "requirements.txt 与 pyproject 依赖一致",
          "requirements=%s pyproject=%s" % (norm(req), norm(deps)))


def check_version(cfg):
    v_pyproject = cfg.get("project", {}).get("version") or ""
    m = re.search(r'__version__\s*=\s*"([^"]+)"', read(ROOT / "__init__.py"))
    v_init = m.group(1) if m else ""
    check(v_pyproject and v_pyproject == v_init,
          "版本号一致 (__init__.py / pyproject.toml)",
          "pyproject=%s __init__=%s" % (v_pyproject or "?", v_init or "?"))


# ---------------------------------------------------------------------------
# 7. Registry 发布元数据
# ---------------------------------------------------------------------------
def check_registry_meta(cfg):
    project = cfg.get("project", {})
    comfy = cfg.get("tool", {}).get("comfy", {})
    missing = []
    if not project.get("name"):
        missing.append("project.name")
    if not project.get("version"):
        missing.append("project.version")
    if not project.get("description"):
        missing.append("project.description")
    if not project.get("license"):
        missing.append("project.license")
    if not project.get("requires-python"):
        missing.append("project.requires-python")
    if not (project.get("urls") or {}).get("Repository"):
        missing.append("project.urls.Repository")
    if not comfy.get("PublisherId"):
        missing.append("tool.comfy.PublisherId")
    if not comfy.get("DisplayName"):
        missing.append("tool.comfy.DisplayName")
    if not comfy.get("Icon"):
        missing.append("tool.comfy.Icon")
    check(not missing, "Registry 发布元数据齐全",
          "缺: %s" % ", ".join(missing) if missing else "name/version/license/Repository/PublisherId/DisplayName/Icon 都在")

    icon = comfy.get("Icon") or ""
    local = ROOT / "assets" / "icon.png"
    if icon and local.is_file():
        try:
            from PIL import Image
            w, h = Image.open(local).size
            check(w <= 800 and h <= 400 and abs(w - h) <= 1,
                  "图标尺寸符合 Registry 要求",
                  "%dx%d (要求正方形, 最长边 ≤800)" % (w, h))
        except Exception as e:
            check(False, "图标可读", str(e))


# ---------------------------------------------------------------------------
# 8. 发布包不该塞进开发文件
# ---------------------------------------------------------------------------
def check_comfyignore():
    p = ROOT / ".comfyignore"
    if not p.is_file():
        check(False, "存在 .comfyignore", "缺失")
        return
    body = read(p)
    need = ["tests/", "assets/screenshots/"]
    missing = [n for n in need if n not in body]
    check(not missing, ".comfyignore 排除开发文件",
          "缺: %s" % ", ".join(missing) if missing else "tests/ 与 assets/screenshots/ 已排除")


# ---------------------------------------------------------------------------
# 9. 单元测试
# ---------------------------------------------------------------------------
def run_child(args):
    """跑子进程并按 UTF-8 编解码。

    Windows 上子进程写管道时用的是本地编码(cp1252), 里面只要有中文就会崩在
    print 上; 父进程按同样编码解码也会花掉。两边都钉死 UTF-8。
    """
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    r = subprocess.run(args, cwd=str(ROOT), capture_output=True, env=env)
    out = (r.stdout or b"").decode("utf-8", "replace")
    err = (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out, err


def run_tests():
    code, out, err = run_child([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    out = err + out
    if code == 0:
        tail = out.strip().splitlines()
        check(True, "单元测试全过", tail[-1] if tail else "(无输出)")
        return
    # 失败时把用例名点出来, 否则 CI 上只知道"红了"不知道红在哪
    names = [l.split(" (")[0].replace("FAIL: ", "").replace("ERROR: ", "")
             for l in out.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    check(False, "单元测试全过", "失败: " + ", ".join(names[:6]) if names else out.strip()[-300:])


def run_http_smoke():
    """真实 aiohttp 层: 跨站 403、路径穿越、FileResponse。需要 aiohttp。"""
    try:
        import aiohttp  # noqa: F401
    except ImportError:
        check(True, "HTTP 冒烟(已跳过)", "本机没有 aiohttp; ComfyUI 环境里会跑")
        return
    code, out, _err = run_child([sys.executable, str(ROOT / "tests" / "http_smoke.py")])
    out = out.strip().splitlines()
    summary = out[-1] if out else ""
    check(code == 0, "HTTP 冒烟全过", summary or "(无输出)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", action="store_true", help="只做静态检查, 不跑单元测试")
    args = ap.parse_args()

    cfg, raw = pyproject()
    check_forbidden_calls()
    check_network()
    check_write_routes()
    check_error_leak()
    check_frontend_html()
    check_dependencies(cfg, raw)
    check_version(cfg)
    check_registry_meta(cfg)
    check_comfyignore()
    if not args.static:
        run_tests()
        run_http_smoke()

    width = max(len(t) for _, t, _ in results)
    print("\n发版前自检 · Comfy Registry 安全策略\n" + "-" * (width + 30))
    for ok, title, detail in results:
        print("%s  %-*s  %s" % ("✔" if ok else "✘", width, title, detail))
    bad = [r for r in results if not r[0]]
    print("-" * (width + 30))
    if bad:
        print("%d/%d 项未通过, 先修完再发版。" % (len(bad), len(results)))
        return 1
    print("%d 项全部通过。" % len(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
