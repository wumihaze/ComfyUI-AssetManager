const app = window.comfyAPI.app.app;
const $el = window.comfyAPI.ui.$el;
const ComfyButton = window.comfyAPI.button.ComfyButton;

const STYLE = `
.asm-overlay { position:fixed; inset:0; z-index:9999; background:rgba(0,0,0,.55); display:none; align-items:center; justify-content:center; }
.asm-panel { width:94vw; height:92vh; max-width:1600px; background:var(--comfy-menu-bg, #202020); border:1px solid var(--border-color, #444); border-radius:10px; display:flex; flex-direction:column; overflow:hidden; color:var(--fg-color, #eee); font-family:var(--font-family, sans-serif); }
.asm-header { display:flex; align-items:center; gap:10px; padding:10px 14px; border-bottom:1px solid var(--border-color,#444); }
.asm-header h2 { font-size:15px; margin:0; font-weight:600; }
.asm-header .sp { flex:1; }
.asm-x { background:none; border:none; color:var(--fg-color,#eee); font-size:20px; cursor:pointer; }
.asm-toolbar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; padding:10px 14px; border-bottom:1px solid var(--border-color,#444); }
.asm-search { flex:1; min-width:180px; background:var(--comfy-input-bg,#333); border:1px solid var(--border-color,#444); color:var(--input-text,#eee); border-radius:6px; padding:6px 10px; font-size:13px; }
.asm-btn { background:var(--comfy-input-bg,#333); border:1px solid var(--border-color,#444); color:var(--fg-color,#eee); border-radius:6px; padding:6px 12px; cursor:pointer; font-size:13px; }
.asm-btn.on { border-color:var(--comfy-menu-bg, #5b8cff); color:#5b8cff; }
.asm-btn.primary { background:#2368b0; border-color:#2368b0; color:#fff; }
.asm-btn.danger { background:#b3372f; border-color:#b3372f; color:#fff; }
.asm-body { flex:1; overflow:auto; padding:14px; }
.asm-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); gap:12px; }
.asm-card { background:var(--comfy-input-bg,#2a2a2a); border:1px solid var(--border-color,#444); border-radius:8px; overflow:hidden; cursor:pointer; }
.asm-card:hover { border-color:#5b8cff; }
.asm-card.selected { border-color:#5b8cff; box-shadow:0 0 0 2px rgba(91,140,255,.45); }
.asm-card .m { position:relative; aspect-ratio:1/1; background:#000; }
.asm-card .selmark { position:absolute; top:6px; right:6px; width:22px; height:22px; border-radius:50%; background:#5b8cff; color:#fff; font-size:13px; display:flex; align-items:center; justify-content:center; z-index:2; }
.asm-card img { width:100%; height:100%; object-fit:cover; display:block; }
.asm-card .play { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); width:42px; height:42px; border-radius:50%; background:rgba(0,0,0,.6); border:2px solid rgba(255,255,255,.7); color:#fff; display:flex; align-items:center; justify-content:center; font-size:16px; pointer-events:none; }
.asm-card .badge { position:absolute; top:6px; left:6px; background:rgba(0,0,0,.65); color:#fff; font-size:10px; padding:1px 7px; border-radius:10px; }
.asm-card .meta { padding:7px 9px; }
.asm-card .nm { font-size:11px; color:var(--descrip-text,#aaa); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.asm-card .pr { font-size:11px; color:var(--fg-color,#eee); height:2.2em; overflow:hidden; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; }
.asm-card .mo { font-size:10px; color:#5b8cff; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.asm-empty { color:var(--descrip-text,#aaa); text-align:center; padding:50px 0; }
/* 日历 */
.asm-cal { display:grid; grid-template-columns:minmax(400px,540px) 1fr; gap:28px; align-items:start; }
.asm-calbar { display:flex; gap:8px; align-items:center; margin-bottom:16px; }
.asm-caltitle { font-size:17px; font-weight:700; min-width:130px; text-align:center; letter-spacing:.5px; }
.asm-calnav { background:var(--comfy-input-bg,#2a2a2a); border:1px solid var(--border-color,#3a3a3a); color:var(--fg-color,#eee); border-radius:8px; padding:6px 13px; cursor:pointer; font-size:13px; transition:border-color .15s, background .15s; }
.asm-calnav:hover { border-color:#5b8cff; background:rgba(91,140,255,.1); }
.asm-calnav.latest { color:#5b8cff; border-color:rgba(91,140,255,.45); }
.asm-week, .asm-calgrid { display:grid; grid-template-columns:repeat(7,1fr); gap:6px; }
.asm-week span { text-align:center; color:var(--descrip-text,#8a8a8a); font-size:11px; padding:5px 0 7px; font-weight:600; letter-spacing:1px; }
.asm-week span.we { color:#e88; }
.asm-day { position:relative; min-height:66px; background:var(--comfy-input-bg,#242424); border:1px solid var(--border-color,#3a3a3a); border-radius:10px; padding:7px 8px; font-size:11px; color:var(--descrip-text,#aaa); cursor:pointer; transition:border-color .15s, transform .12s, box-shadow .15s, background .15s; }
.asm-day.blank { background:transparent; border-color:transparent; box-shadow:none; cursor:default; }
.asm-day.has { color:var(--fg-color,#eee); }
.asm-day:hover { border-color:#5b8cff; transform:translateY(-1px); box-shadow:0 3px 10px rgba(0,0,0,.35); }
.asm-day.blank:hover { transform:none; box-shadow:none; border-color:transparent; }
.asm-day.today { background:rgba(91,140,255,.10); }
.asm-day.today .num { color:#5b8cff; }
.asm-day.sel { border-color:#5b8cff; background:linear-gradient(160deg, rgba(91,140,255,.20), rgba(91,140,255,.05)); box-shadow:0 0 0 1px rgba(91,140,255,.5); }
.asm-day .num { font-size:13px; font-weight:700; line-height:1.1; }
.asm-day .cnt { display:flex; flex-wrap:wrap; gap:4px; margin-top:7px; }
.asm-day .tag { font-size:9px; padding:1px 6px; border-radius:10px; line-height:1.5; font-weight:600; }
.asm-day .tag-img { background:rgba(91,140,255,.20); color:#8fb0ff; }
.asm-day .tag-vid { background:rgba(255,150,60,.18); color:#ffa05e; }
.asm-callist h3 { font-size:15px; font-weight:600; margin:0 0 14px; padding-bottom:10px; border-bottom:1px solid var(--border-color,#3a3a3a); }
.asm-callist h3 .sub { font-size:12px; color:var(--descrip-text,#aaa); font-weight:400; margin-left:4px; }
.asm-callist .cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(168px,1fr)); gap:12px; }
@media (max-width: 1000px){ .asm-cal { grid-template-columns:1fr; gap:20px; } }
/* 弹窗预览 */
.asm-modal { position:fixed; inset:0; z-index:10001; display:none; align-items:center; justify-content:center; }
.asm-modal .bk { position:absolute; inset:0; background:rgba(0,0,0,.72); }
.asm-modal .pn { position:relative; background:var(--comfy-menu-bg,#202020); border:1px solid var(--border-color,#444); border-radius:12px; width:min(900px,94vw); max-height:92vh; overflow:auto; padding:18px; }
.asm-modal video, .asm-modal img { max-width:100%; border-radius:8px; display:block; margin:0 auto; }
.asm-modal video { max-height:55vh; }
.asm-modal .rows { margin-top:12px; font-size:12px; color:var(--descrip-text,#aaa); }
.asm-modal textarea { width:100%; height:130px; background:var(--comfy-input-bg,#333); border:1px solid var(--border-color,#444); color:var(--input-text,#eee); border-radius:6px; padding:8px; font-size:12px; margin-top:6px; }
.asm-modal .btns { display:flex; gap:8px; margin-top:10px; flex-wrap:wrap; }
.asm-modal .x { position:absolute; top:8px; right:12px; background:none; border:none; color:var(--fg-color,#eee); font-size:20px; cursor:pointer; z-index:2; }
/* 设置 */
.asm-set { margin:4px 0; }
.asm-set .row { display:flex; gap:8px; align-items:center; margin:8px 0; font-size:13px; }
.asm-set .row label { min-width:110px; color:var(--descrip-text,#bbb); }
.asm-set input { flex:1; background:var(--comfy-input-bg,#333); border:1px solid var(--border-color,#444); color:var(--input-text,#eee); border-radius:6px; padding:6px 10px; font-size:13px; }
.asm-set input[type="checkbox"] { flex:0 0 auto; width:auto; cursor:pointer; }
.asm-set input[type="number"] { flex:0 0 auto; width:110px; }
.asm-set .chk { display:flex; gap:8px; align-items:center; margin:8px 0; font-size:13px; }
.asm-status { padding:8px 14px; border-top:1px solid var(--border-color,#444); font-size:12px; color:var(--descrip-text,#aaa); min-height:18px; }
`;

app.registerExtension({
  name: "ComfyUI.AssetManager",
  async setup() {
    // ---------- 国际化: 跟随 ComfyUI 语言 ----------
    let LANG = "zh";
    function detectLang() {
      try {
        const loc = window.comfyAPI.app.app.ui.settings.getSettingValue("Comfy.Locale");
        LANG = (loc && String(loc).toLowerCase().startsWith("zh")) ? "zh" : "en";
      } catch (e) { LANG = "zh"; }
    }
    const L10N = {
      "资产管理": "Asset Manager",
      "浏览/搜索/删除产物, 切换输出目录, 备份": "Browse / search / delete assets, switch output directory, backup",
      "搜索提示词 / 模型 / 文件名 / 日期…": "Search prompts / models / filename / date…",
      "🗂 资产管理": "🗂 Asset Manager",
      "‹ 上月": "‹ Prev",
      "下月 ›": "Next ›",
      "回到最新": "Latest",
      "网格": "Grid",
      "日历": "Calendar",
      "全部": "All types",
      "图片": "Images",
      "视频": "Videos",
      "☑ 多选": "☑ Multi-select",
      "🗑 删除选中": "🗑 Delete selected",
      "⚙ 资产设置": "⚙ Settings",
      "💾 备份": "💾 Backup",
      "⟳ 扫描": "⟳ Scan",
      "图": "Img",
      "(未检测到提示词)": "(no prompt detected)",
      "没有匹配的产物": "No matching assets",
      "当天没有归档产物": "No assets on this day",
      "当天没有匹配当前筛选的产物": "No matching assets on this day",
      "点选日期查看当天产物": "Click a date to view its assets",
      "来源: ": "Source: ",
      "时间: ": "Time: ",
      "模型/LoRA: ": "Models/LoRA: ",
      "参数: ": "Params: ",
      "提示词": "Prompt",
      "复制提示词": "Copy prompt",
      "下载 workflow.json": "Download workflow.json",
      "🗑 从硬盘删除": "🗑 Delete from disk",
      "💡 下载 workflow.json 后拖进 ComfyUI 画布, 即可完整还原整套工作流(节点+连线)。": "💡 Drag the downloaded workflow.json onto the ComfyUI canvas to fully restore the workflow (nodes + links).",
      "已复制": "Copied",
      "该产物未携带 workflow 元数据": "This asset has no workflow metadata",
      "下载失败": "Download failed",
      "已从硬盘删除": "Deleted from disk",
      "未知错误": "unknown error",
      "留空=使用 ComfyUI 默认 output": "Leave empty = ComfyUI default output",
      "输出目录": "Output directory",
      "归档库目录": "Archive directory",
      "备份目录": "Backup directory",
      "自动归档新产物": "Auto-archive new assets",
      "缩略图宽度(px)": "Thumbnail width (px)",
      "扫描间隔(秒)": "Scan interval (sec)",
      "浏览…": "Browse…",
      "保存设置": "Save settings",
      "改归档/备份目录后新产物进入新目录, 旧数据保留; 输出目录切换重启 ComfyUI 后仍生效; 自动归档开关和扫描间隔即时生效。": "After changing the archive/backup directory, new assets go to the new directory (old data stays). Output directory changes persist across ComfyUI restarts. Auto-archive and scan interval take effect immediately.",
      "✅ 设置已保存": "✅ Settings saved",
      "📁 选择目录": "📁 Select directory",
      "（请选择磁盘）": "(select a drive)",
      "（无子目录）": "(no subdirectories)",
      "⬆ 上一级": "⬆ Up",
      "✅ 选择此目录": "✅ Select this folder",
      "取消": "Cancel",
      "💾 备份确认": "💾 Backup confirmation",
      "将备份以下内容:": "Will back up:",
      "• 资产库（图片/视频/元数据/工作流）<br>• 工作流文件 (user/default/workflows)<br>• 插件配置": "• Asset library (images / videos / metadata / workflows)<br>• Workflow files (user/default/workflows)<br>• Plugin config",
      "备份目录: ": "Backup directory: ",
      "确定备份": "Back up",
      "备份中…": "Backing up…",
      "✅ 备份完成: ": "✅ Backup done: ",
      " 个文件) → ": " files) → ",
      "扫描中…": "Scanning…",
      "扫描失败": "Scan failed",
      "加载中…": "Loading…",
      "共 ": "Total: ",
      " 条资产": " assets",
      "已自动更新: 共 ": "Auto-updated: ",
    };
    function t(zh) { return LANG === "zh" ? zh : (L10N[zh] !== undefined ? L10N[zh] : zh); }
    const ERR_L10N = {
      "Missing output directory path": "缺少输出目录路径",
      "run_ids must be an array": "run_ids 必须是数组",
      "Directory not found": "目录不存在",
      "Directory is outside the allowed browse scope": "该目录不在允许浏览范围内",
      "Missing run_id": "缺少 run_id",
      "Invalid archive path": "非法的归档路径",
      "Archive entry not found": "未找到该归档条目",
    };
    function terr(en) { return LANG === "zh" ? (ERR_L10N[en] || en) : en; }
    detectLang();

    const styleEl = $el("style", { textContent: STYLE });
    (document.head || document.documentElement).appendChild(styleEl);

    // 自动修复: 连线渲染模式被设成 Hidden(-1) 时改回 Spline(2)
    function fixLinkRenderMode() {
      try {
        const g = window.comfyAPI.app.app.rootGraphInternal;
        if (!g) return;
        const arr = Array.isArray(g.list_of_graphcanvas) ? g.list_of_graphcanvas : Object.values(g.list_of_graphcanvas || {});
        for (const gc of arr) {
          if (gc && gc.links_render_mode === -1) {
            gc.links_render_mode = 2;  // SPLINE_LINK
            if (gc.setDirty) gc.setDirty(false, true);
          }
        }
      } catch (e) {}
    }
    setTimeout(fixLinkRenderMode, 1500);
    setTimeout(fixLinkRenderMode, 6000);

    let runs = [];
    let view = "grid", kind = "all", selDate = null, calYear = 0, calMonth = 0;
    let multi = false;
    const selected = new Set();
    let pollTimer = null;
    let curConfig = {};

    const byDate = {};
    function rebuildByDate() {
      for (const k in byDate) delete byDate[k];
      for (const r of runs) (byDate[r.date] || (byDate[r.date] = [])).push(r);
    }

    function pad(n) { return String(n).padStart(2, "0"); }
    function mediaUrl(dir, f) { return "/asset/file?p=" + encodeURIComponent(dir + "/" + f); }

    function matches(r, kw) {
      kw = kw.toLowerCase();
      return ((r.positive + " " + (r.negative || "") + " " + (r.models || []).join(" ") + " " + r.name + " " + (r.date || "")).toLowerCase()).includes(kw);
    }
    function filtered(list) {
      const kw = q.value.trim();
      return list.filter(r => (kind === "all" || r.kind === kind) && (!kw || matches(r, kw)));
    }

    // ---------- 面板骨架 ----------
    const overlay = $el("div.asm-overlay");
    const body = $el("div.asm-body");
    const status = $el("div.asm-status", { textContent: "" });
    const q = $el("input.asm-search", { type: "text", placeholder: t("搜索提示词 / 模型 / 文件名 / 日期…") });
    const countEl = $el("span", { textContent: "", style: { fontSize: "12px", color: "var(--descrip-text,#aaa)" } });
    const calGrid = $el("div.asm-calgrid");
    const calListTitle = $el("h3");
    const calListCards = $el("div.cards");
    const calTitle = $el("span.asm-caltitle");

    const gridEl = $el("div.asm-grid");
    const calWrap = $el("div.asm-cal", { style: { display: "none" } });
    const weekdays = LANG === "zh" ? ["一", "二", "三", "四", "五", "六", "日"] : ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];
    calWrap.appendChild($el("div", {}, [
      $el("div.asm-calbar", {}, [
        $el("button.asm-calnav", { textContent: t("‹ 上月"), onclick: () => { calMonth--; if (calMonth < 0) { calMonth = 11; calYear--; } selDate = null; renderCal(); } }),
        calTitle,
        $el("button.asm-calnav", { textContent: t("下月 ›"), onclick: () => { calMonth++; if (calMonth > 11) { calMonth = 0; calYear++; } selDate = null; renderCal(); } }),
        $el("button.asm-calnav.latest", { textContent: t("回到最新"), onclick: () => { goLatest(); } }),
      ]),
      $el("div.asm-week", {}, weekdays.map((t2, idx) => $el("span" + (idx >= 5 ? ".we" : ""), { textContent: t2 }))),
      calGrid,
    ]));
    calWrap.appendChild($el("div.asm-callist", {}, [calListTitle, calListCards]));

    function goLatest() {
      if (runs.length) {
        const d = runs[0].date;
        calYear = Number(d.slice(0, 4)); calMonth = Number(d.slice(5, 7)) - 1; selDate = d;
      }
      renderCal();
    }

    // ---------- 视图切换 ----------
    const viewBtns = {};
    function mkViewBtn(label, v) {
      const b = $el("button.asm-btn" + (view === v ? ".on" : ""), { textContent: label });
      b.onclick = () => { view = v; Object.values(viewBtns).forEach(x => x.classList.remove("on")); b.classList.add("on"); refresh(); };
      viewBtns[v] = b;
      return b;
    }
    const kindBtns = {};
    function mkKindBtn(label, k) {
      const b = $el("button.asm-btn" + (kind === k ? ".on" : ""), { textContent: label });
      b.onclick = () => { kind = k; Object.values(kindBtns).forEach(x => x.classList.remove("on")); b.classList.add("on"); refresh(); };
      kindBtns[k] = b;
      return b;
    }

    const multiBtn = $el("button.asm-btn", { textContent: t("☑ 多选"), onclick: toggleMulti });
    const batchBtn = $el("button.asm-btn.danger", { textContent: t("🗑 删除选中"), onclick: batchDelete, style: { display: "none" } });

    const toolbar = $el("div.asm-toolbar", {}, [
      q,
      mkViewBtn(t("网格"), "grid"),
      mkViewBtn(t("日历"), "cal"),
      mkKindBtn(t("全部"), "all"),
      mkKindBtn(t("图片"), "image"),
      mkKindBtn(t("视频"), "video"),
      multiBtn,
      batchBtn,
      $el("button.asm-btn", { textContent: t("⚙ 资产设置"), onclick: openSettings }),
      $el("button.asm-btn", { textContent: t("💾 备份"), onclick: confirmBackup }),
      $el("button.asm-btn", { textContent: t("⟳ 扫描"), onclick: doScan }),
      countEl,
    ]);

    const panel = $el("div.asm-panel", {}, [
      $el("div.asm-header", {}, [
        $el("h2", { textContent: t("🗂 资产管理") }),
        $el("span.sp"),
        $el("button.asm-x", { textContent: "✕", onclick: closePanel }),
      ]),
      toolbar,
      body,
      status,
    ]);
    body.appendChild(gridEl);
    body.appendChild(calWrap);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    // ---------- 渲染 ----------
    function renderCard(r, container) {
      const card = $el("div.asm-card");
      if (selected.has(r.dir)) card.classList.add("selected");
      const thumb = r.thumb ? mediaUrl(r.dir, r.thumb) : mediaUrl(r.dir, r.media);
      const isVid = r.kind === "video";
      card.appendChild($el("div.m", {}, [
        $el("img", { src: thumb, loading: "lazy" }),
        isVid ? $el("div.play", { textContent: "▶" }) : null,
        $el("span.badge", { textContent: isVid ? t("视频") : t("图") }),
        selected.has(r.dir) ? $el("div.selmark", { textContent: "✓" }) : null,
      ].filter(Boolean)));
      card.appendChild($el("div.meta", {}, [
        $el("div.nm", { textContent: r.name }),
        $el("div.pr", { textContent: (r.positive || "").slice(0, 160) || t("(未检测到提示词)") }),
        r.models && r.models.length ? $el("div.mo", { textContent: r.models.join(" · ") }) : null,
      ].filter(Boolean)));
      card.onclick = () => {
        if (multi) {
          if (selected.has(r.dir)) selected.delete(r.dir); else selected.add(r.dir);
          card.classList.toggle("selected", selected.has(r.dir));
          const m = card.querySelector(".m");
          const mark = card.querySelector(".selmark");
          if (selected.has(r.dir) && !mark) m.appendChild($el("div.selmark", { textContent: "✓" }));
          if (!selected.has(r.dir) && mark) mark.remove();
          updateBatchBtn();
        } else {
          openPreview(r);
        }
      };
      container.appendChild(card);
    }

    function renderGrid() {
      const list = filtered(runs);
      gridEl.innerHTML = "";
      countEl.textContent = list.length + " / " + runs.length;
      if (!list.length) { gridEl.appendChild($el("div.asm-empty", { textContent: t("没有匹配的产物") })); return; }
      for (const r of list) renderCard(r, gridEl);
    }

    function countOf(d) {
      const l = byDate[d] || [];
      return { all: l.length, img: l.filter(r => r.kind === "image").length, vid: l.filter(r => r.kind === "video").length };
    }

    function renderCal() {
      calTitle.textContent = LANG === "zh" ? (calYear + "年" + (calMonth + 1) + "月") : (calYear + "-" + pad(calMonth + 1));
      const first = (new Date(calYear, calMonth, 1).getDay() + 6) % 7;
      const days = new Date(calYear, calMonth + 1, 0).getDate();
      const now = new Date();
      const tKey = now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());
      calGrid.innerHTML = "";
      for (let i = 0; i < 42; i++) {
        const d = i - first + 1;
        if (d < 1 || d > days) { calGrid.appendChild($el("div.asm-day.blank")); continue; }
        const dk = calYear + "-" + pad(calMonth + 1) + "-" + pad(d);
        const c = countOf(dk);
        const has = c.all > 0;
        const day = $el("div.asm-day" + (has ? ".has" : "") + (dk === tKey ? ".today" : "") + (dk === selDate ? ".sel" : ""), {}, [
          $el("div.num", { textContent: String(d) }),
        ]);
        if (has) {
          const cnt = $el("div.cnt");
          if (kind === "all") {
            if (c.img) cnt.appendChild($el("span.tag.tag-img", { textContent: c.img + (LANG === "zh" ? " 图" : " img") }));
            if (c.vid) cnt.appendChild($el("span.tag.tag-vid", { textContent: c.vid + (LANG === "zh" ? " 视" : " vid") }));
          } else {
            const n = kind === "image" ? c.img : c.vid;
            const cls = kind === "image" ? "tag-img" : "tag-vid";
            const label = LANG === "zh" ? (kind === "image" ? " 图" : " 视") : (kind === "image" ? " img" : " vid");
            cnt.appendChild($el("span.tag." + cls, { textContent: n + label }));
          }
          day.appendChild(cnt);
        }
        day.onclick = () => { selDate = dk; renderCal(); };
        calGrid.appendChild(day);
      }
      const base = (selDate && byDate[selDate]) ? byDate[selDate].length : 0;
      const list = selDate ? filtered(byDate[selDate] || []) : [];
      let title;
      if (selDate) {
        title = LANG === "zh" ? (selDate + " · 当天归档 " + base + " 条") : (selDate + " · " + base + " assets");
      } else {
        title = t("点选日期查看当天产物");
      }
      if (selDate && (kind !== "all" || q.value.trim())) {
        title += LANG === "zh" ? " <span class='sub'>（当前筛选 " + list.length + " 条）</span>" : " <span class='sub'>(filtered: " + list.length + ")</span>";
      }
      calListTitle.innerHTML = title;
      calListCards.innerHTML = "";
      if (selDate && base === 0) calListCards.appendChild($el("div.asm-empty", { textContent: t("当天没有归档产物") }));
      else if (!list.length && selDate) calListCards.appendChild($el("div.asm-empty", { textContent: t("当天没有匹配当前筛选的产物") }));
      else for (const r of list) renderCard(r, calListCards);
    }

    function refresh() {
      if (view === "grid") { gridEl.style.display = ""; calWrap.style.display = "none"; renderGrid(); }
      else { gridEl.style.display = "none"; calWrap.style.display = ""; renderCal(); }
      updateBatchBtn();
    }

    // ---------- 多选 / 批量删除 ----------
    function updateBatchBtn() {
      if (multi && selected.size > 0) {
        batchBtn.style.display = "";
        batchBtn.textContent = t("🗑 删除选中") + "(" + selected.size + ")";
      } else {
        batchBtn.style.display = "none";
      }
    }
    function toggleMulti() {
      multi = !multi;
      multiBtn.classList.toggle("on", multi);
      selected.clear();
      updateBatchBtn();
      refresh();
    }
    async function batchDelete() {
      if (!selected.size) return;
      const ids = [...selected];
      const msg = LANG === "zh"
        ? ("确定要从硬盘永久删除选中的 " + ids.length + " 项产物吗?\n\n将同时删除归档副本和 output 中的原始文件, 无法恢复。")
        : ("Permanently delete the selected " + ids.length + " items from disk?\n\nThis also deletes the archive copies and the original files in output. This cannot be undone.");
      if (!confirm(msg)) return;
      const res = await fetch("/asset/delete_batch", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_ids: ids }) });
      const d = await res.json();
      if (d.ok) {
        const delSet = new Set(ids);
        runs = runs.filter(x => !delSet.has(x.dir));
        selected.clear();
        rebuildByDate();
        refresh();
        const done = LANG === "zh" ? ("已删除 " + d.deleted + " 项") : ("Deleted " + d.deleted + " items");
        const extra = d.failed && d.failed.length ? (LANG === "zh" ? ("（失败 " + d.failed.length + " 项）") : (" (failed: " + d.failed.length + ")")) : "";
        statusMsg(done + extra);
      } else {
        statusMsg(t("批量删除失败: ") + (terr(d.error) || ""));
      }
    }

    // ---------- 预览 ----------
    function openPreview(r) {
      const m = $el("div.asm-modal");
      m.style.display = "flex";
      const full = mediaUrl(r.dir, r.media);
      const media = r.kind === "video"
        ? $el("video", { src: full, controls: true, autoplay: true, muted: true, playsinline: true })
        : $el("img", { src: full });
      const ta = $el("textarea", { textContent: (r.positive || "") + (r.negative ? "\n\nNegative prompt: " + r.negative : "") });
      const models = (r.models || []).join(", ") || "—";
      const params = Object.keys(r.params || {}).map(k => k + "=" + r.params[k]).join(" · ") || "—";
      const pn = $el("div.pn", {}, [
        $el("button.x", { textContent: "✕", onclick: () => m.remove() }),
        media,
        $el("div.rows", {}, [
          $el("div", { textContent: t("来源: ") + r.name }),
          $el("div", { textContent: t("时间: ") + r.time + " | " + t("模型/LoRA: ") + models }),
          $el("div", { textContent: t("参数: ") + params }),
        ]),
        $el("label", { textContent: t("提示词"), style: { fontSize: "12px" } }),
        ta,
        $el("div.btns", {}, [
          $el("button.asm-btn", { textContent: t("复制提示词"), onclick: () => { ta.select(); navigator.clipboard?.writeText(ta.value).then(() => statusMsg(t("已复制"))); } }),
          $el("button.asm-btn.primary", { textContent: t("下载 workflow.json"), onclick: () => downloadWorkflow(r) }),
          $el("button.asm-btn.danger", { textContent: t("🗑 从硬盘删除"), onclick: () => doDelete(r, m) }),
        ]),
        $el("div", { textContent: t("💡 下载 workflow.json 后拖进 ComfyUI 画布, 即可完整还原整套工作流(节点+连线)。"), style: { fontSize: "11px", color: "var(--descrip-text,#aaa)", marginTop: "8px" } }),
      ]);
      m.appendChild($el("div.bk", { onclick: () => m.remove() }));
      m.appendChild(pn);
      document.body.appendChild(m);
    }

    function downloadWorkflow(r) {
      if (!r.has_workflow) { statusMsg(t("该产物未携带 workflow 元数据")); return; }
      fetch("/asset/file?p=" + encodeURIComponent(r.dir + "/workflow.json"))
        .then(x => x.blob()).then(b => {
          const a = document.createElement("a");
          a.href = URL.createObjectURL(b);
          a.download = r.name.replace(/[\\/:*?"<>|]/g, "_") + ".workflow.json";
          a.click();
        }).catch(() => statusMsg(t("下载失败")));
    }

    async function doDelete(r, modal) {
      const msg = LANG === "zh"
        ? ("确定要从硬盘永久删除该产物吗?\n\n" + r.name + "\n\n将同时删除归档副本和 output 中的原始文件, 无法恢复。")
        : ("Permanently delete this asset from disk?\n\n" + r.name + "\n\nThis also deletes the archive copy and the original file in output. This cannot be undone.");
      if (!confirm(msg)) return;
      const res = await fetch("/asset/delete", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ run_id: r.dir }) });
      const d = await res.json();
      if (d.ok) {
        modal.remove();
        runs = runs.filter(x => x.dir !== r.dir);
        rebuildByDate(); refresh(); statusMsg(t("已从硬盘删除"));
      } else statusMsg(t("删除失败: ") + (terr(d.error) || t("未知错误")));
    }

    // ---------- 设置 ----------
    async function openSettings() {
      try { curConfig = await (await fetch("/asset/config")).json(); } catch (e) {}
      const c = curConfig.config || {};
      const m = $el("div.asm-modal");
      m.style.display = "flex";
      const fOut = $el("input", { value: curConfig.current_output_dir || "", placeholder: t("留空=使用 ComfyUI 默认 output") });
      const fArch = $el("input", { value: curConfig.archive_dir || c.archive_dir || "" });
      const fBak = $el("input", { value: c.backup_dir || "" });
      const fAuto = $el("input", { type: "checkbox" });
      fAuto.checked = c.auto_archive !== false;
      const fThumb = $el("input", { type: "number", min: 100, max: 2000, value: String(c.thumb_width || 480) });
      const fInterval = $el("input", { type: "number", min: 3, max: 3600, value: String(c.interval_sec || 10) });

      const row = (label, input, browse) => $el("div.row", {}, [
        $el("label", { textContent: label }), input,
        browse ? $el("button.asm-btn", { textContent: t("浏览…"), onclick: () => browseDir(input) }) : null,
      ].filter(Boolean));

      const pn = $el("div.pn", {}, [
        $el("button.x", { textContent: "✕", onclick: () => m.remove() }),
        $el("h2", { textContent: t("⚙ 资产设置"), style: { margin: "0 0 10px", fontSize: "15px" } }),
        $el("div.asm-set", {}, [
          row(t("输出目录"), fOut, true),
          row(t("归档库目录"), fArch, true),
          row(t("备份目录"), fBak, true),
          $el("div.chk", {}, [fAuto, $el("span", { textContent: t("自动归档新产物") })]),
          row(t("缩略图宽度(px)"), fThumb),
          row(t("扫描间隔(秒)"), fInterval),
        ]),
        $el("div.btns", {}, [
          $el("button.asm-btn.primary", { textContent: t("保存设置"), onclick: saveSettings }),
        ]),
        $el("div", { textContent: t("改归档/备份目录后新产物进入新目录, 旧数据保留; 输出目录切换重启 ComfyUI 后仍生效; 自动归档开关和扫描间隔即时生效。"), style: { fontSize: "11px", color: "var(--descrip-text,#aaa)", marginTop: "10px" } }),
      ]);
      m.appendChild($el("div.bk", { onclick: () => m.remove() }));
      m.appendChild(pn);
      document.body.appendChild(m);

      async function saveSettings() {
        const payload = {
          output_dir: fOut.value.trim(),
          archive_dir: fArch.value.trim(),
          backup_dir: fBak.value.trim(),
          auto_archive: fAuto.checked,
          thumb_width: Number(fThumb.value),
          interval_sec: Number(fInterval.value),
        };
        const r = await fetch("/asset/set_config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
        const d = await r.json();
        if (d.ok) {
          curConfig = { config: d.config, archive_dir: d.archive_dir, current_output_dir: d.current_output_dir };
          m.remove();
          const extra = (d.errors && d.errors.length) ? (LANG === "zh" ? ("（部分项未生效: " + d.errors.join("; ") + "）") : (" (some failed: " + d.errors.join("; ") + ")")) : "";
          statusMsg(t("✅ 设置已保存") + extra);
          await loadRuns(); refresh();
        } else {
          statusMsg(t("保存失败: ") + (terr(d.error) || ""));
        }
      }
    }

    // ---------- 目录浏览选择器 ----------
    async function browseDir(inputEl) {
      const m = $el("div.asm-modal");
      m.style.display = "flex";
      const pathEl = $el("div", { style: { fontSize: "12px", color: "var(--descrip-text,#aaa)", marginBottom: "8px", wordBreak: "break-all" } });
      const listEl = $el("div", { style: { maxHeight: "320px", overflowY: "auto", border: "1px solid var(--border-color,#444)", borderRadius: "6px" } });
      let curPath = inputEl.value.trim() || "";

      async function load(path) {
        try {
          const res = await fetch("/asset/browse_dir?path=" + encodeURIComponent(path));
          const d = await res.json();
          if (!d.ok) { pathEl.textContent = t("错误: ") + (terr(d.error) || ""); listEl.innerHTML = ""; return; }
          curPath = d.path || "";
          pathEl.textContent = t("当前: ") + (curPath || t("（请选择磁盘）"));
          listEl.innerHTML = "";
          if (!d.dirs.length) {
            listEl.appendChild($el("div", { textContent: t("（无子目录）"), style: { padding: "12px", color: "var(--descrip-text,#aaa)", fontSize: "12px" } }));
          }
          for (const dir of d.dirs) {
            const full = curPath ? curPath.replace(/[\\/]$/, "") + "\\" + dir : dir;
            const item = $el("div", { textContent: "📁 " + dir, style: { padding: "7px 12px", cursor: "pointer", fontSize: "13px", borderBottom: "1px solid rgba(0,0,0,.2)" } });
            item.onmouseenter = () => { item.style.background = "rgba(91,140,255,.18)"; };
            item.onmouseleave = () => { item.style.background = ""; };
            item.onclick = () => load(full);
            listEl.appendChild(item);
          }
        } catch (e) {
          pathEl.textContent = t("加载失败: ") + e;
        }
      }

      const pn = $el("div.pn", {}, [
        $el("button.x", { textContent: "✕", onclick: () => m.remove() }),
        $el("h2", { textContent: t("📁 选择目录"), style: { margin: "0 0 10px", fontSize: "15px" } }),
        pathEl,
        $el("div.btns", { style: { margin: "8px 0" } }, [
          $el("button.asm-btn", { textContent: t("⬆ 上一级"), onclick: async () => {
            try {
              const res = await fetch("/asset/browse_dir?path=" + encodeURIComponent(curPath));
              const d = await res.json();
              if (d.ok) load(d.parent || "");
            } catch (e) {}
          } }),
        ]),
        listEl,
        $el("div.btns", { style: { marginTop: "12px" } }, [
          $el("button.asm-btn.primary", { textContent: t("✅ 选择此目录"), onclick: () => { inputEl.value = curPath; m.remove(); } }),
          $el("button.asm-btn", { textContent: t("取消"), onclick: () => m.remove() }),
        ]),
      ]);
      m.appendChild($el("div.bk", { onclick: () => m.remove() }));
      m.appendChild(pn);
      document.body.appendChild(m);
      await load(curPath);
    }

    // ---------- 备份 / 扫描 ----------
    async function confirmBackup() {
      try { curConfig = await (await fetch("/asset/config")).json(); } catch (e) {}
      const bakDir = (curConfig.config && curConfig.config.backup_dir) || curConfig.default_backup_dir || "";
      const m = $el("div.asm-modal");
      m.style.display = "flex";
      const pn = $el("div.pn", {}, [
        $el("button.x", { textContent: "✕", onclick: () => m.remove() }),
        $el("h2", { textContent: t("💾 备份确认"), style: { margin: "0 0 12px", fontSize: "15px" } }),
        $el("div", { textContent: t("将备份以下内容:"), style: { fontSize: "13px", marginBottom: "6px" } }),
        $el("div", { innerHTML: t("• 资产库（图片/视频/元数据/工作流）<br>• 工作流文件 (user/default/workflows)<br>• 插件配置"), style: { fontSize: "13px", color: "var(--descrip-text,#aaa)", marginBottom: "12px", lineHeight: "1.8" } }),
        $el("div", { textContent: t("备份目录: ") + bakDir, style: { fontSize: "13px", marginBottom: "14px", wordBreak: "break-all" } }),
        $el("div.btns", {}, [
          $el("button.asm-btn.primary", { textContent: t("确定备份"), onclick: () => { m.remove(); doBackup(); } }),
          $el("button.asm-btn", { textContent: t("取消"), onclick: () => m.remove() }),
        ]),
      ]);
      m.appendChild($el("div.bk", { onclick: () => m.remove() }));
      m.appendChild(pn);
      document.body.appendChild(m);
    }
    async function doBackup() {
      statusMsg(t("备份中…"));
      const res = await fetch("/asset/backup", { method: "POST" });
      const d = await res.json();
      if (d.ok) statusMsg(t("✅ 备份完成: ") + d.name + " (" + (d.size / 1048576).toFixed(1) + " MB, " + d.files + t(" 个文件) → ") + d.file);
      else statusMsg(t("备份失败: ") + (terr(d.error) || ""));
    }
    async function doScan() {
      statusMsg(t("扫描中…"));
      const res = await fetch("/asset/scan", { method: "POST" });
      const d = await res.json();
      statusMsg(d.ok ? (LANG === "zh" ? ("扫描完成, 新增 " + d.new + " 条") : ("Scan done, " + d.new + " new")) : t("扫描失败"));
      await loadRuns(); refresh();
    }

    function statusMsg(s) { status.textContent = s; }

    // ---------- 打开/关闭 ----------
    async function loadRuns() {
      const res = await fetch("/asset/list");
      const d = await res.json();
      if (d.ok) { runs = d.runs || []; rebuildByDate(); }
      try { curConfig = await (await fetch("/asset/config")).json(); } catch (e) {}
    }
    async function openPanel() {
      detectLang();
      overlay.style.display = "flex";
      statusMsg(t("加载中…"));
      fixLinkRenderMode();
      await loadRuns();
      if (runs.length) {
        const d = runs[0].date;
        calYear = Number(d.slice(0, 4)); calMonth = Number(d.slice(5, 7)) - 1; selDate = d;
      }
      refresh();
      statusMsg(t("共 ") + runs.length + t(" 条资产"));
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(pollRefresh, 8000);
    }
    function closePanel() {
      overlay.style.display = "none";
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }
    async function pollRefresh() {
      try {
        const res = await fetch("/asset/list");
        const d = await res.json();
        if (!d.ok) return;
        const newDirs = new Set((d.runs || []).map(r => r.dir));
        const oldDirs = new Set(runs.map(r => r.dir));
        const changed = newDirs.size !== oldDirs.size || [...newDirs].some(x => !oldDirs.has(x));
        if (changed) {
          runs = d.runs || [];
          rebuildByDate();
          // 清除已不存在的选中项
          for (const s of [...selected]) if (!newDirs.has(s)) selected.delete(s);
          refresh();
          statusMsg(t("已自动更新: 共 ") + runs.length + t(" 条资产"));
        }
      } catch (e) {}
    }

    q.addEventListener("input", refresh);

    // ---------- 入口 ----------
    // 菜单栏按钮(图标用 archive 以区分「显示图像流」)
    try {
      const btn = new ComfyButton({
        icon: "archive",
        content: t("资产管理"),
        tooltip: t("浏览/搜索/删除产物, 切换输出目录, 备份"),
        action: () => openPanel(),
      });
      if (app.menu && app.menu.settingsGroup) app.menu.settingsGroup.append(btn);
    } catch (e) {
      console.error("AssetManager 菜单按钮注册失败:", e);
    }
  },
});
