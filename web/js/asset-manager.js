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
/* 左侧固定导航: 来源文件夹 / 我的分类 (两段各自滚动, 分类常驻底部) */
.asm-main { display:flex; flex:1; min-height:0; }
.asm-side { width:172px; flex:0 0 172px; border-right:1px solid var(--border-color,#444); display:flex; flex-direction:column; min-height:0; }
.asm-side .sec { display:flex; flex-direction:column; min-height:0; }
/* 分类是主视图: 占满剩余高度, 自己滚 */
.asm-side .sec.cats { flex:1 1 0; min-height:0; }
/* 来源文件夹退到底部: 默认收起(只有一行标题), 展开时最多占 46% */
.asm-side .sec.folders { flex:0 0 auto; max-height:46%; border-top:1px solid var(--border-color,#444); }
.asm-side .list { flex:1 1 auto; min-height:0; overflow-y:auto; overflow-x:hidden; padding:0 6px 8px; display:flex; flex-direction:column; gap:1px; }
.asm-side .grp { display:flex; align-items:center; gap:6px; font-size:11px; font-weight:700; letter-spacing:.6px; color:var(--descrip-text,#8a8a8a); padding:9px 8px 5px; }
.asm-side .grp .sp { flex:1; }
.asm-side .grp .asm-mini { padding:1px 7px; font-size:11px; }
.asm-side .grp.toggle { cursor:pointer; user-select:none; border-radius:6px; padding:8px 8px 6px; }
.asm-side .grp.toggle:hover { background:rgba(91,140,255,.10); color:var(--fg-color,#ccc); }
.asm-side .grp .arrow { font-size:9px; opacity:.8; width:9px; }
.asm-side .grp .chip { max-width:74px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:10px; font-weight:400; letter-spacing:0; color:#8fb0ff; background:rgba(91,140,255,.16); border-radius:9px; padding:1px 7px; }
.asm-side .asm-it { display:flex; align-items:center; gap:6px; width:100%; text-align:left; background:none; border:1px solid transparent; color:var(--fg-color,#eee); border-radius:6px; padding:4px 8px; font-size:12px; cursor:pointer; }
.asm-side .asm-it:hover { background:rgba(91,140,255,.12); }
.asm-side .asm-it.on { background:rgba(91,140,255,.20); border-color:rgba(91,140,255,.55); color:#cfe0ff; }
.asm-side .asm-it .tx { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.asm-side .asm-it .n { flex:0 0 auto; font-size:10px; color:var(--descrip-text,#8a8a8a); }
.asm-side .asm-it.on .n { color:#9db8ff; }
.asm-side .asm-it .pinmark { flex:0 0 auto; font-size:9px; line-height:1; opacity:.9; }
/* 子分类: 缩进 + 一条竖线, 一眼看出层级 */
.asm-side .asm-it.child { padding-left:18px; border-left:2px solid rgba(91,140,255,.40); border-radius:4px 6px 6px 4px; margin-left:6px; }
.asm-side .asm-it.child .tx { font-size:11.5px; }
.asm-side .empty { font-size:11px; color:var(--descrip-text,#8a8a8a); padding:2px 8px 6px; line-height:1.6; }
@media (max-width: 860px){ .asm-side { width:134px; flex-basis:134px; } }
@media (max-width: 620px){ .asm-side { width:112px; flex-basis:112px; } .asm-side .asm-it { font-size:11px; padding:4px 6px; } .asm-side .grp { font-size:10px; padding:8px 6px 4px; } }

.asm-body { flex:1; min-width:0; overflow:auto; padding:14px; }
.asm-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:12px; }
.asm-card .cat { font-size:10px; color:#8fb0ff; background:rgba(91,140,255,.16); border-radius:10px; padding:1px 7px; display:inline-block; margin-bottom:3px; max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.asm-catlist { display:flex; flex-direction:column; gap:6px; margin:12px 0; max-height:46vh; overflow:auto; }
.asm-catrow { text-align:left; background:var(--comfy-input-bg,#333); border:1px solid var(--border-color,#444); color:var(--fg-color,#eee); border-radius:8px; padding:9px 12px; font-size:13px; cursor:pointer; }
.asm-catrow:hover { border-color:#5b8cff; }
.asm-newcat { display:flex; gap:8px; align-items:center; }
.asm-newcat input { flex:1; min-width:120px; }
/* 框选 */
.asm-marquee { position:fixed; z-index:10002; display:none; pointer-events:none; border:1px solid #5b8cff; background:rgba(91,140,255,.16); border-radius:3px; }
/* 移到分类: 目标选择 */
.asm-assign-hint { font-size:12px; color:var(--descrip-text,#aaa); margin:-2px 0 12px; line-height:1.7; }
.asm-assign-hint b { color:var(--fg-color,#eee); font-weight:600; }
.asm-catlist.pick { gap:2px; margin:0; max-height:46vh; padding:2px 0; }
.asm-pickrow { display:flex; align-items:center; gap:10px; width:100%; text-align:left; background:none; border:1px solid transparent; color:var(--fg-color,#eee); border-radius:8px; padding:9px 10px; font-size:13px; cursor:pointer; }
.asm-pickrow:hover { background:rgba(91,140,255,.14); border-color:rgba(91,140,255,.45); }
.asm-pickrow .dot { flex:0 0 auto; width:15px; height:15px; border-radius:50%; border:1.5px solid #666; position:relative; }
.asm-pickrow:hover .dot { border-color:#5b8cff; }
.asm-pickrow.cur .dot { border-color:#5b8cff; }
.asm-pickrow.cur .dot::after { content:""; position:absolute; inset:2.5px; border-radius:50%; background:#5b8cff; }
.asm-pickrow .nm { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.asm-pickrow .n { flex:0 0 auto; font-size:11px; color:var(--descrip-text,#8a8a8a); }
.asm-pickrow .tag { flex:0 0 auto; font-size:10px; color:#8fb0ff; background:rgba(91,140,255,.18); border-radius:9px; padding:1px 7px; }
.asm-pickrow.out { color:var(--descrip-text,#bbb); }
.asm-pickrow.out .dot { border-style:dashed; }
.asm-pickrow.child { padding-left: 30px; border-left: 2px solid rgba(91,140,255,.45); border-radius: 4px 8px 8px 4px; }
.asm-pickrow.child .nm { font-size:12.5px; color:var(--descrip-text,#c9c9c9); }
.asm-catrow.manage.child { padding-left: 30px; border-left: 2px solid rgba(91,140,255,.45); border-radius: 4px 8px 8px 4px; }
.asm-sep { display:flex; align-items:center; gap:10px; margin:12px 0 10px; font-size:11px; color:var(--descrip-text,#8a8a8a); }
.asm-sep::before, .asm-sep::after { content:""; flex:1; height:1px; background:var(--border-color,#3a3a3a); }
.asm-modal-foot { display:flex; justify-content:flex-end; gap:8px; margin-top:12px; }
.asm-catrow.manage { display:flex; align-items:center; gap:8px; cursor:default; }
.asm-catrow .catname { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.asm-catrow .catcount { font-size:11px; color:var(--descrip-text,#aaa); }
.asm-mini { background:var(--comfy-input-bg,#333); border:1px solid var(--border-color,#444); color:var(--fg-color,#eee); border-radius:6px; padding:4px 9px; font-size:12px; cursor:pointer; }
.asm-mini:hover { border-color:#5b8cff; }
.asm-mini.danger { color:#ff8b82; border-color:rgba(179,55,47,.6); }
/* 置顶 / 排序按钮 */
.asm-mini.pin { padding:4px 6px; opacity:.45; filter:grayscale(1); }
.asm-mini.pin.on { opacity:1; filter:none; border-color:rgba(255,209,102,.6); background:rgba(255,209,102,.14); }
.asm-mini.pin:hover { opacity:.85; }
.asm-mini.pin.on:hover { opacity:1; }
.asm-mini:disabled { opacity:.25; cursor:default; }
.asm-mini:disabled:hover { border-color:var(--border-color,#444); }
.asm-catrow.manage .asm-mini { padding:4px 7px; }
.asm-mini-input { flex:1; min-width:0; background:var(--comfy-input-bg,#333); border:1px solid var(--border-color,#444); color:var(--input-text,#eee); border-radius:6px; padding:6px 8px; font-size:13px; }
.asm-card { background:var(--comfy-input-bg,#2a2a2a); border:1px solid var(--border-color,#444); border-radius:8px; overflow:hidden; cursor:pointer; }
.asm-card:hover { border-color:#5b8cff; }
.asm-card.selected { border-color:#5b8cff; box-shadow:0 0 0 2px rgba(91,140,255,.45); }
.asm-card .m { position:relative; aspect-ratio:1/1; background:#000; }
.asm-card .selmark { position:absolute; top:6px; right:6px; width:22px; height:22px; border-radius:50%; background:#5b8cff; color:#fff; font-size:13px; display:flex; align-items:center; justify-content:center; z-index:2; }
.asm-card img { width:100%; height:100%; object-fit:cover; display:block; }
.asm-card .audio-art { position:absolute; inset:0; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px; background:radial-gradient(circle at 50% 35%, rgba(91,140,255,.32), rgba(30,35,52,.95) 72%); color:#dbe5ff; }
.asm-card .audio-art .note { font-size:58px; line-height:1; }
.asm-card .audio-art .format { font-size:11px; letter-spacing:1px; opacity:.8; text-transform:uppercase; }
.asm-card .play { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); width:42px; height:42px; border-radius:50%; background:rgba(0,0,0,.6); border:2px solid rgba(255,255,255,.7); color:#fff; display:flex; align-items:center; justify-content:center; font-size:16px; pointer-events:none; }
.asm-card .badge { position:absolute; top:6px; left:6px; background:rgba(0,0,0,.65); color:#fff; font-size:10px; padding:1px 7px; border-radius:10px; }
.asm-card .meta { padding:7px 9px; }
.asm-card .nm { font-size:11px; color:var(--descrip-text,#aaa); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.asm-card .pr { font-size:11px; color:var(--fg-color,#eee); height:2.2em; overflow:hidden; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; }
.asm-card .mo { font-size:10px; color:#5b8cff; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.asm-empty { color:var(--descrip-text,#aaa); text-align:center; padding:50px 0; }
/* 日历 */
.asm-cal { display:grid; grid-template-columns:minmax(260px,520px) 1fr; gap:28px; align-items:start; }
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
.asm-day .tag-aud { background:rgba(170,115,255,.20); color:#c5a2ff; }
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
.asm-modal audio { width:min(560px,100%); display:block; margin:12px auto; }
.asm-modal .rows { margin-top:12px; font-size:12px; color:var(--descrip-text,#aaa); }
.asm-modal textarea { width:100%; height:130px; background:var(--comfy-input-bg,#333); border:1px solid var(--border-color,#444); color:var(--input-text,#eee); border-radius:6px; padding:8px; font-size:12px; margin-top:6px; }
.asm-modal .btns { display:flex; gap:8px; margin-top:10px; flex-wrap:wrap; }
/* 关闭按钮: 常压在图片/视频上, 必须是自带底色的圆钮, 否则亮画面上完全看不见 */
.asm-modal .x {
  position:absolute; top:8px; right:12px; z-index:5;
  width:30px; height:30px; padding:0; display:flex; align-items:center; justify-content:center;
  background:rgba(0,0,0,.60); border:1px solid rgba(255,255,255,.34); border-radius:50%;
  color:#fff; font-size:15px; line-height:1; cursor:pointer;
  -webkit-backdrop-filter:blur(6px); backdrop-filter:blur(6px);
  box-shadow:0 2px 10px rgba(0,0,0,.55);
  transition:background .15s, border-color .15s, transform .15s;
}
.asm-modal .x:hover { background:rgba(0,0,0,.85); border-color:rgba(255,255,255,.62); }
.asm-modal .x:active { transform:scale(.94); }
.asm-modal .x:focus-visible { outline:2px solid #5b8cff; outline-offset:2px; }
/* 预览弹窗给关闭按钮留出一条空档, 不让它压住画面 */
.asm-modal .pn.preview { padding-top:42px; }
.asm-modal img { max-height:70vh; object-fit:contain; }
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
      "音频": "Audio",
      "☑ 多选": "☑ Multi-select",
      "🗑 删除选中": "🗑 Delete selected",
      "⚙ 资产设置": "⚙ Settings",
      "💾 备份": "💾 Backup",
      "⟳ 扫描": "⟳ Scan",
      "文件夹": "Folder",
      "分类": "Category",
      "来源文件夹": "Source folders",
      "我的分类": "My categories",
      "还没有分类，点 ⚙ 新建": "No categories yet — click ⚙ to create",
      "全部文件夹": "All folders",
      "（根目录）": "(root)",
      "全部分类": "All categories",
      "未分类": "Uncategorized",
      "🏷 移到分类": "🏷 Move to category",
      "移到分类": "Move to category",
      " 项": " items",
      "已移动 ": "Moved ",
      "未分类（移出分类）": "Uncategorized (clear)",
      "还没有分类，在下面新建一个": "No categories yet — create one below",
      "新建分类名称": "New category name",
      "新建并移入": "Create and move",
      "移动失败": "Move failed",
      "已选 ": "Selected ",
      "当前：": "Current: ",
      "当前": "current",
      "多个分类": "Multiple categories",
      "搜索分类…": "Search categories…",
      "或": "or",
      "或新建一个分类": "or create a new category",
      "多选：单击切换 / Ctrl 单击加选 / Shift 单击连选 / 空白处拖拽框选":
        "Multi-select: click to toggle / Ctrl+click to add / Shift+click for a range / drag on empty space to box-select",
      "已退出多选": "Multi-select off",
      "按产出目录筛选": "Filter by source folder",
      "清除文件夹筛选": "Clear folder filter",
      "新建子分类": "New sub-category",
      "新分类名称": "New category name",
      "分类可以分两级：点 ＋ 在某个分类下新建子分类。删除分类不会删除文件。":
        "Categories can nest one level: click ＋ on a category to add a sub-category. Deleting a category never deletes files.",
      "点 ＋ 在某个分类下新建子分类；📌 置顶，↑↓ 调整顺序。删除分类不会删除文件。":
        "Click ＋ to add a sub-category; 📌 pins it to the top, ↑↓ reorders. Deleting a category never deletes files.",
      "置顶": "Pin to top",
      "取消置顶": "Unpin",
      "已置顶": "Pinned",
      "已取消置顶": "Unpinned",
      "置顶失败": "Pin failed",
      "上移": "Move up",
      "下移": "Move down",
      "调整顺序失败": "Reorder failed",
      " 个子分类已上移": " sub-categories moved up",
      "新建失败": "Create failed",
      "⚙ 管理分类": "⚙ Categories",
      "管理分类": "Manage categories",
      "重命名": "Rename",
      "删除分类": "Delete category",
      "保存": "Save",
      "取消": "Cancel",
      "关闭": "Close",
      "已重命名": "Renamed",
      "重命名失败": "Rename failed",
      "删除失败": "Delete failed",
      "已删除分类": "Category deleted",
      " 项已转为未分类": " assets became uncategorized",
      "新建分类": "New category",
      "已新建分类": "Category created",
      "图": "Img",
      "(未检测到提示词)": "(no prompt detected)",
      "没有匹配的产物": "No matching assets",
      "当天没有归档产物": "No assets on this day",
      "当天没有匹配当前筛选的产物": "No matching assets on this day",
      "点选日期查看当天产物": "Click a date to view its assets",
      "来源: ": "Source: ",
      "时间: ": "Time: ",
      "时长: ": "Duration: ",
      "模型/LoRA: ": "Models/LoRA: ",
      "参数: ": "Params: ",
      "提示词": "Prompt text",
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
      "归档安装前已有的产物": "Archive assets already present on install",
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
      "取消": "Dismiss",
      "💾 备份确认": "💾 Backup confirmation",
      "将备份以下内容:": "Will back up:",
      "• 资产库（图片/视频/音频/元数据/工作流）<br>• 工作流文件 (user/default/workflows)<br>• 插件配置": "• Asset library (images / videos / audio / metadata / workflows)<br>• Workflow files (user/default/workflows)<br>• Plugin config",
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
      "Category not found": "分类不存在",
      "Category already exists": "分类已存在",
      "Category name is required": "分类名不能为空",
      "Too many categories": "分类数量已达上限",
      "Unknown action": "未知操作",
      "Invalid direction": "方向不合法",
      "Category operation failed": "分类操作失败（归档目录可能不可写）",
      "Assign failed": "移动分类失败（归档目录可能不可写）",
      "Only one level of nesting is supported": "只支持一层子分类",
      "Parent category not found": "父分类不存在",
    };
    function terr(en) { return LANG === "zh" ? (ERR_L10N[en] || en) : en; }
    detectLang();
    // 语言变化时动态更新所有静态文本
    const relabelers = [];
    function bindText(el, zh, prop) {
      prop = prop || "textContent";
      el.dataset.i18n = zh;
      el.dataset.i18nProp = prop;
      el[prop] = t(zh);
      return el;
    }
    function relabel() {
      document.querySelectorAll("[data-i18n]").forEach((el) => {
        el[el.dataset.i18nProp || "textContent"] = t(el.dataset.i18n);
      });
      for (const f of relabelers) f();
    }
    function labeledRow(parts) {
      const d = $el("div");
      for (const p of parts) {
        if (p.zh) { const s = $el("span"); bindText(s, p.zh); d.appendChild(s); }
        if (p.text) d.appendChild(document.createTextNode(p.text));
      }
      return d;
    }

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
    // folderFilter: null = 全部文件夹, "" = 根目录, 其它 = 具体子目录
    // ("" 是合法的根目录值, 不能用它表示"全部", 否则两者会撞在一起)
    let folderFilter = null, catFilter = "";
    let categories = [];
    let foldersOpen = false;   // 来源文件夹默认收起, 分类是主视图
    const selected = new Set();
    let pollTimer = null;
    let curConfig = {};

    const byDate = {};
    function rebuildByDate() {
      for (const k in byDate) delete byDate[k];
      // 日历只统计"当前左侧选中范围"内的产物, 与右侧列表口径一致
      for (const r of runs) if (inScope(r)) (byDate[r.date] || (byDate[r.date] = [])).push(r);
    }

    function pad(n) { return String(n).padStart(2, "0"); }
    function mediaUrl(dir, f) { return "/asset/file?p=" + encodeURIComponent(dir + "/" + f); }

    function matches(r, kw) {
      kw = kw.toLowerCase();
      return ((r.positive + " " + (r.negative || "") + " " + (r.models || []).join(" ") + " " + r.name + " " + (r.date || "")).toLowerCase()).includes(kw);
    }
    // 分类是两层树: 选中父分类时, 其子分类下的产物也算在这个范围里(像文件夹一样)
    function catIdsFor(id) {
      if (!id) return null;
      const out = [id];
      for (const c of categories) if (c.parent === id) out.push(c.id);
      return out;
    }
    function rootCategories() {
      const ids = new Set(categories.map(c => c.id));
      return categories.filter(c => !c.parent || !ids.has(c.parent));
    }
    function kidsOf(id) {
      return categories.filter(c => c.parent === id);
    }
    function catCount(id) {
      const ids = new Set(catIdsFor(id));
      let n = 0;
      for (const r of runs) if (r.category && ids.has(r.category)) n++;
      return n;
    }

    // 左侧导航选中的范围(来源文件夹 + 我的分类)
    function inScope(r) {
      if (folderFilter !== null && (r.folder || "") !== folderFilter) return false;
      if (catFilter === "__none__" && r.category) return false;
      if (catFilter && catFilter !== "__none__") {
        const ids = catIdsFor(catFilter);
        if (!r.category || !ids.includes(r.category)) return false;
      }
      return true;
    }
    function filtered(list) {
      const kw = q.value.trim();
      return list.filter(r => {
        if (kind !== "all" && r.kind !== kind) return false;
        if (!inScope(r)) return false;
        return !kw || matches(r, kw);
      });
    }

    function categoryName(r) {
      if (!r.category) return "";
      const c = categories.find(x => x.id === r.category);
      return c ? c.name : "";
    }

    // ---------- 面板骨架 ----------
    const overlay = $el("div.asm-overlay");
    const body = $el("div.asm-body");
    const status = $el("div.asm-status", { textContent: "" });
    const q = $el("input.asm-search", { type: "text" });
    bindText(q, "搜索提示词 / 模型 / 文件名 / 日期…", "placeholder");
    const countEl = $el("span", { textContent: "", style: { fontSize: "12px", color: "var(--descrip-text,#aaa)" } });
    const calGrid = $el("div.asm-calgrid");
    const calListTitle = $el("h3");
    const calListCards = $el("div.cards");
    const calTitle = $el("span.asm-caltitle");

    const gridEl = $el("div.asm-grid");
    const calWrap = $el("div.asm-cal", { style: { display: "none" } });
    const weekdayEls = [];
    function renderWeekdays() {
      const wd = LANG === "zh" ? ["一", "二", "三", "四", "五", "六", "日"] : ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];
      weekdayEls.forEach((el, i) => { el.textContent = wd[i]; });
    }
    relabelers.push(renderWeekdays);
    const prevMonthBtn = $el("button.asm-calnav", { onclick: () => { calMonth--; if (calMonth < 0) { calMonth = 11; calYear--; } selDate = null; renderCal(); } });
    bindText(prevMonthBtn, "‹ 上月");
    const nextMonthBtn = $el("button.asm-calnav", { onclick: () => { calMonth++; if (calMonth > 11) { calMonth = 0; calYear++; } selDate = null; renderCal(); } });
    bindText(nextMonthBtn, "下月 ›");
    const latestBtn = $el("button.asm-calnav.latest", { onclick: () => { goLatest(); } });
    bindText(latestBtn, "回到最新");
    calWrap.appendChild($el("div", {}, [
      $el("div.asm-calbar", {}, [prevMonthBtn, calTitle, nextMonthBtn, latestBtn]),
      $el("div.asm-week", {}, Array.from({ length: 7 }, (_, idx) => {
        const s = $el("span" + (idx >= 5 ? ".we" : ""));
        weekdayEls.push(s);
        return s;
      })),
      calGrid,
    ]));
    renderWeekdays();
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
    function mkViewBtn(zh, v) {
      const b = $el("button.asm-btn" + (view === v ? ".on" : ""));
      bindText(b, zh);
      b.onclick = () => { view = v; Object.values(viewBtns).forEach(x => x.classList.remove("on")); b.classList.add("on"); refresh(); };
      viewBtns[v] = b;
      return b;
    }
    const kindBtns = {};
    function mkKindBtn(zh, k) {
      const b = $el("button.asm-btn" + (kind === k ? ".on" : ""));
      bindText(b, zh);
      b.onclick = () => { kind = k; Object.values(kindBtns).forEach(x => x.classList.remove("on")); b.classList.add("on"); refresh(); };
      kindBtns[k] = b;
      return b;
    }

    const multiBtn = $el("button.asm-btn", { onclick: toggleMulti });
    bindText(multiBtn, "☑ 多选");
    const batchBtn = $el("button.asm-btn.danger", { onclick: batchDelete, style: { display: "none" } });
    bindText(batchBtn, "🗑 删除选中");
    const assignBtn = $el("button.asm-btn.primary", { onclick: openAssignModal, style: { display: "none" } });
    bindText(assignBtn, "🏷 移到分类");

    const settingsBtn = $el("button.asm-btn", { onclick: openSettings });
    bindText(settingsBtn, "⚙ 资产设置");
    const backupBtn = $el("button.asm-btn", { onclick: confirmBackup });
    bindText(backupBtn, "💾 备份");
    const scanBtn = $el("button.asm-btn", { onclick: doScan });
    bindText(scanBtn, "⟳ 扫描");
    const toolbar = $el("div.asm-toolbar", {}, [
      q,
      mkViewBtn("网格", "grid"),
      mkViewBtn("日历", "cal"),
      mkKindBtn("全部", "all"),
      mkKindBtn("图片", "image"),
      mkKindBtn("视频", "video"),
      mkKindBtn("音频", "audio"),
      multiBtn,
      batchBtn,
      assignBtn,
      settingsBtn,
      backupBtn,
      scanBtn,
      countEl,
    ]);

    // ---------- 左侧固定导航: 来源文件夹(自动派生) / 我的分类(手动) ----------
    // 不用下拉: 归档多了文件夹会有上百项, 下拉里翻找又慢又看不到全貌。
    const side = $el("div.asm-side");

    function sideItem(label, count, active, kind, value, onClick, pinned) {
      const b = $el("button.asm-it" + (active ? ".on" : ""));
      b.dataset.k = kind;
      if (value === null) b.dataset.all = "1";   // "全部" 项: 不写 data-v
      else b.dataset.v = value;
      if (pinned) b.appendChild($el("span.pinmark", { textContent: "📌", title: t("已置顶") }));
      b.appendChild($el("span.tx", { textContent: label, title: label }));
      b.appendChild($el("span.n", { textContent: String(count) }));
      b.onclick = onClick;
      return b;
    }

    // 只切高亮, 不重建列表 —— 重建会把左侧滚动位置弹回顶部
    function sideActive(el) {
      const isF = el.dataset.k === "f";
      const cur = isF ? folderFilter : catFilter;
      if (el.dataset.all === "1") return isF ? cur === null : cur === "";
      return el.dataset.v === cur;
    }

    function syncSideSelection() {
      for (const el of side.querySelectorAll(".asm-it")) el.classList.toggle("on", sideActive(el));
    }

    function renderSide() {
      side.innerHTML = "";

      const fcounts = new Map();
      for (const r of runs) {
        const f = r.folder || "";
        fcounts.set(f, (fcounts.get(f) || 0) + 1);
      }
      // 选中的文件夹/分类被删掉后自动回到"全部"
      if (folderFilter !== null && !fcounts.has(folderFilter)) folderFilter = null;
      if (catFilter && catFilter !== "__none__" && !categories.some(c => c.id === catFilter)) catFilter = "";

      // ---- 主视图: 我的分类(树形, 两层) ----
      let uncat = 0;
      for (const r of runs) if (!r.category) uncat++;
      const manageBtn = $el("button.asm-mini", { onclick: openCategoryManager, title: t("管理分类") });
      manageBtn.textContent = "⚙";
      const cList = $el("div.list");
      cList.appendChild(sideItem(t("全部分类"), runs.length, catFilter === "", "c", null,
        () => { catFilter = ""; refresh(); }));
      cList.appendChild(sideItem(t("未分类"), uncat, catFilter === "__none__", "c", "__none__",
        () => { catFilter = "__none__"; refresh(); }));

      for (const root of rootCategories()) {
        cList.appendChild(sideItem(root.name, catCount(root.id), catFilter === root.id, "c", root.id,
          () => { catFilter = root.id; refresh(); }, root.pinned));
        for (const kid of kidsOf(root.id)) {
          const it = sideItem(kid.name, catCount(kid.id), catFilter === kid.id, "c", kid.id,
            () => { catFilter = kid.id; refresh(); }, kid.pinned);
          it.classList.add("child");
          cList.appendChild(it);
        }
      }
      if (!categories.length) {
        cList.appendChild($el("div.empty", { textContent: t("还没有分类，点 ⚙ 新建") }));
      }
      side.appendChild($el("div.sec.cats", {}, [
        $el("div.grp", {}, [
          $el("span", { textContent: t("我的分类") }),
          $el("span.sp"),
          manageBtn,
        ]),
        cList,
      ]));

      // ---- 底部: 来源文件夹(次要维度, 默认收起) ----
      const head = $el("div.grp.toggle", { title: t("按产出目录筛选") });
      head.appendChild($el("span.arrow", { textContent: foldersOpen ? "▾" : "▸" }));
      head.appendChild($el("span", { textContent: t("来源文件夹") }));
      head.appendChild($el("span.sp"));
      if (folderFilter !== null) {
        head.appendChild($el("span.chip", {
          textContent: folderFilter === "" ? t("（根目录）") : folderFilter,
          title: folderFilter === "" ? t("（根目录）") : folderFilter,
        }));
        const clear = $el("button.asm-mini", { textContent: "✕", title: t("清除文件夹筛选") });
        clear.onclick = (ev) => { ev.stopPropagation(); folderFilter = null; renderSide(); refresh(); };
        head.appendChild(clear);
      }
      head.onclick = () => { foldersOpen = !foldersOpen; renderSide(); };

      const foldersSec = $el("div.sec.folders", {}, [head]);
      if (foldersOpen) {
        const fList = $el("div.list");
        fList.appendChild(sideItem(t("全部文件夹"), runs.length, folderFilter === null, "f", null,
          () => { folderFilter = null; refresh(); }));
        const entries = [...fcounts.entries()].sort((a, b) => a[0].localeCompare(b[0]));
        for (const [f, n] of entries) {
          fList.appendChild(sideItem(f || t("（根目录）"), n, folderFilter === f, "f", f,
            () => { folderFilter = f; refresh(); }));
        }
        foldersSec.appendChild(fList);
      }
      side.appendChild(foldersSec);
    }

    relabelers.push(renderSide);

    const panelTitle = $el("h2");
    bindText(panelTitle, "🗂 资产管理");
    const panel = $el("div.asm-panel", {}, [
      $el("div.asm-header", {}, [
        panelTitle,
        $el("span.sp"),
        $el("button.asm-x", { textContent: "✕", onclick: closePanel }),
      ]),
      toolbar,
      $el("div.asm-main", {}, [side, body]),
      status,
    ]);
    body.appendChild(gridEl);
    body.appendChild(calWrap);
    overlay.appendChild(panel);
    document.body.appendChild(overlay);

    // ---------- 渲染 ----------
    function renderCard(r, container) {
      const card = $el("div.asm-card");
      card.dataset.dir = r.dir;
      if (selected.has(r.dir)) card.classList.add("selected");
      const thumb = r.thumb ? mediaUrl(r.dir, r.thumb) : mediaUrl(r.dir, r.media);
      const isVid = r.kind === "video";
      const isAudio = r.kind === "audio";
      const visual = isAudio
        ? $el("div.audio-art", {}, [
            $el("span.note", { textContent: "♫" }),
            $el("span.format", { textContent: ((r.media || "").split(".").pop() || "audio") }),
          ])
        : $el("img", { src: thumb, loading: "lazy" });
      card.appendChild($el("div.m", {}, [
        visual,
        isVid ? $el("div.play", { textContent: "▶" }) : null,
        $el("span.badge", { textContent: isVid ? t("视频") : isAudio ? t("音频") : t("图") }),
        selected.has(r.dir) ? $el("div.selmark", { textContent: "✓" }) : null,
      ].filter(Boolean)));
      card.appendChild($el("div.meta", {}, [
        categoryName(r) ? $el("div.cat", { textContent: categoryName(r) }) : null,
        $el("div.nm", { textContent: r.name }),
        $el("div.pr", { textContent: (r.positive || "").slice(0, 160) || t("(未检测到提示词)") }),
        r.models && r.models.length ? $el("div.mo", { textContent: r.models.join(" · ") }) : null,
      ].filter(Boolean)));
      card.onclick = (ev) => {
        // 刚做完框选: 拖拽结束时浏览器还会补一个 click, 这里吞掉
        if (Date.now() < suppressClickUntil) return;
        const additive = ev.ctrlKey || ev.metaKey;
        const ranged = ev.shiftKey;
        // Ctrl / Shift 直接进入多选, 不必先点"☑ 多选"
        if ((additive || ranged) && !multi) setMulti(true);
        if (!multi) { openPreview(r); return; }

        if (ranged) {
          if (anchorDir) selectRange(anchorDir, r.dir);
          else { selected.add(r.dir); anchorDir = r.dir; }
        } else if (additive) {
          if (selected.has(r.dir)) selected.delete(r.dir); else selected.add(r.dir);
          anchorDir = r.dir;
        } else {
          // 普通单击: 切换, 并把连选锚点挪到这张
          if (selected.has(r.dir)) selected.delete(r.dir); else selected.add(r.dir);
          anchorDir = r.dir;
        }
        syncCardSelection();
        updateBatchBtn();
      };
      container.appendChild(card);
    }

    // ---------- 多选: 单击切换 / Ctrl 加选 / Shift 连选 / 空白处拖拽框选 ----------
    let anchorDir = null;          // Shift 连选的锚点
    let suppressClickUntil = 0;    // 框选后短暂屏蔽 click

    function setMulti(on) {
      multi = on;
      multiBtn.classList.toggle("on", multi);
      if (!multi) { selected.clear(); anchorDir = null; }
      updateBatchBtn();
      refresh();
    }

    // 把 selected 的状态刷到当前可见卡片上(不重建 DOM)
    function syncCardSelection() {
      for (const card of overlay.querySelectorAll(".asm-card")) {
        const on = selected.has(card.dataset.dir);
        card.classList.toggle("selected", on);
        const m = card.querySelector(".m");
        const mark = card.querySelector(".selmark");
        if (on && m && !mark) m.appendChild($el("div.selmark", { textContent: "✓" }));
        if (!on && mark) mark.remove();
      }
    }

    function visibleCards() {
      const box = view === "grid" ? gridEl : calListCards;
      return [...box.querySelectorAll(".asm-card")];
    }

    // 从 fromDir 到 toDir 按当前显示顺序整段选中
    function selectRange(fromDir, toDir) {
      const list = visibleCards();
      const i = list.findIndex(c => c.dataset.dir === fromDir);
      const j = list.findIndex(c => c.dataset.dir === toDir);
      if (i < 0 || j < 0) { selected.add(toDir); return; }
      const [a, b] = i <= j ? [i, j] : [j, i];
      for (let k = a; k <= b; k++) selected.add(list[k].dataset.dir);
    }

    // 框选: 在空白处按下并拖动, 与选框相交的卡片即被选中
    const marquee = $el("div.asm-marquee");
    let dragBox = null;
    let autoScrollTimer = null;

    function beginMarquee(ev) {
      if (ev.button !== 0) return;
      // 只在卡片容器的空白处起手(卡片本身有自己的点击逻辑)
      if (ev.target.closest(".asm-card")) return;
      if (!ev.target.closest(".asm-grid, .asm-callist .cards")) return;
      ev.preventDefault();
      // 按住 Ctrl/Shift 框选是追加, 否则先清空
      const base = (ev.ctrlKey || ev.metaKey || ev.shiftKey) ? new Set(selected) : new Set();
      dragBox = { x0: ev.clientX, y0: ev.clientY, base, moved: false };
      lastDragX = ev.clientX; lastDragY = ev.clientY;
      marquee.style.display = "block";
      marquee.style.left = ev.clientX + "px";
      marquee.style.top = ev.clientY + "px";
      marquee.style.width = "0px";
      marquee.style.height = "0px";
      overlay.appendChild(marquee);
      window.addEventListener("mousemove", trackPointer);
      window.addEventListener("mousemove", moveMarquee);
      window.addEventListener("mouseup", endMarquee, { once: true });
      startAutoScroll();
    }

    function trackPointer(ev) { lastDragX = ev.clientX; lastDragY = ev.clientY; }

    function moveMarquee(ev) {
      if (!dragBox) return;
      const x = Math.min(dragBox.x0, ev.clientX);
      const y = Math.min(dragBox.y0, ev.clientY);
      const w = Math.abs(ev.clientX - dragBox.x0);
      const h = Math.abs(ev.clientY - dragBox.y0);
      if (w > 2 || h > 2) dragBox.moved = true;
      // 真的拖起来了才切进多选(单纯点一下空白不该改变模式), 这里不 refresh, 免得拖拽中途重建卡片
      if (dragBox.moved && !multi) {
        multi = true;
        multiBtn.classList.add("on");
        anchorDir = null;
      }
      marquee.style.left = x + "px";
      marquee.style.top = y + "px";
      marquee.style.width = w + "px";
      marquee.style.height = h + "px";

      const next = new Set(dragBox.base);
      for (const card of visibleCards()) {
        const b = card.getBoundingClientRect();
        if (b.left < x + w && b.right > x && b.top < y + h && b.bottom > y) next.add(card.dataset.dir);
      }
      selected.clear();
      for (const d of next) selected.add(d);
      syncCardSelection();
      updateBatchBtn();
    }

    // 拖到可视区上下边缘时自动滚动
    function startAutoScroll() {
      stopAutoScroll();
      autoScrollTimer = setInterval(() => {
        if (!dragBox || !lastDragY) return;
        const r = body.getBoundingClientRect();
        if (lastDragY < r.top + 48) body.scrollTop -= 18;
        else if (lastDragY > r.bottom - 48) body.scrollTop += 18;
        else return;
        moveMarquee({ clientX: lastDragX, clientY: lastDragY });
      }, 40);
    }
    function stopAutoScroll() {
      if (autoScrollTimer) { clearInterval(autoScrollTimer); autoScrollTimer = null; }
    }
    let lastDragX = 0, lastDragY = 0;

    function endMarquee() {
      window.removeEventListener("mousemove", trackPointer);
      window.removeEventListener("mousemove", moveMarquee);
      stopAutoScroll();
      if (dragBox && dragBox.moved) suppressClickUntil = Date.now() + 300;
      dragBox = null;
      marquee.style.display = "none";
      marquee.remove();
      updateBatchBtn();
    }

    // 空白处按下即开始框选(卡片容器内的空白也算)
    body.addEventListener("mousedown", beginMarquee);

    function renderGrid() {
      const list = filtered(runs);
      gridEl.innerHTML = "";
      countEl.textContent = list.length + " / " + runs.length;
      if (!list.length) { gridEl.appendChild($el("div.asm-empty", { textContent: t("没有匹配的产物") })); return; }
      for (const r of list) renderCard(r, gridEl);
    }

    function countOf(d) {
      const l = byDate[d] || [];
      return {
        all: l.length,
        img: l.filter(r => r.kind === "image").length,
        vid: l.filter(r => r.kind === "video").length,
        aud: l.filter(r => r.kind === "audio").length,
      };
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
            if (c.aud) cnt.appendChild($el("span.tag.tag-aud", { textContent: c.aud + (LANG === "zh" ? " 音" : " aud") }));
          } else {
            const n = kind === "image" ? c.img : kind === "video" ? c.vid : c.aud;
            const cls = kind === "image" ? "tag-img" : kind === "video" ? "tag-vid" : "tag-aud";
            const label = LANG === "zh" ? (kind === "image" ? " 图" : kind === "video" ? " 视" : " 音") : (kind === "image" ? " img" : kind === "video" ? " vid" : " aud");
            cnt.appendChild($el("span.tag." + cls, { textContent: n + label }));
          }
          day.appendChild(cnt);
        }
        day.onclick = () => { selDate = dk; renderCal(); };
        calGrid.appendChild(day);
      }
      const base = (selDate && byDate[selDate]) ? byDate[selDate].length : 0;
      const list = selDate ? filtered(byDate[selDate] || []) : [];
      calListTitle.textContent = "";
      if (selDate) {
        calListTitle.appendChild(document.createTextNode(
          LANG === "zh" ? (selDate + " · 当天归档 " + base + " 条") : (selDate + " · " + base + " assets")
        ));
        if (kind !== "all" || q.value.trim()) {
          const sub = $el("span.sub", {
            textContent: LANG === "zh" ? "（当前筛选 " + list.length + " 条）" : "(filtered: " + list.length + ")",
          });
          calListTitle.appendChild(sub);
        }
      } else {
        calListTitle.textContent = t("点选日期查看当天产物");
      }
      calListCards.innerHTML = "";
      if (selDate && base === 0) calListCards.appendChild($el("div.asm-empty", { textContent: t("当天没有归档产物") }));
      else if (!list.length && selDate) calListCards.appendChild($el("div.asm-empty", { textContent: t("当天没有匹配当前筛选的产物") }));
      else for (const r of list) renderCard(r, calListCards);
    }

    function refresh() {
      rebuildByDate();
      if (view === "grid") { gridEl.style.display = ""; calWrap.style.display = "none"; renderGrid(); }
      else { gridEl.style.display = "none"; calWrap.style.display = ""; renderCal(); }
      syncSideSelection();
      updateBatchBtn();
    }

    // ---------- 多选 / 批量删除 ----------
    function updateBatchBtn() {
      const on = multi && selected.size > 0;
      batchBtn.style.display = on ? "" : "none";
      assignBtn.style.display = on ? "" : "none";
      if (on) {
        batchBtn.textContent = t("🗑 删除选中") + "(" + selected.size + ")";
        assignBtn.textContent = t("🏷 移到分类") + "(" + selected.size + ")";
      }
    }
    function toggleMulti() {
      setMulti(!multi);
      statusMsg(multi
        ? t("多选：单击切换 / Ctrl 单击加选 / Shift 单击连选 / 空白处拖拽框选")
        : t("已退出多选"));
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

    // ---------- 移到分类 ----------
    async function assignTo(ids, cid) {
      const res = await fetch("/asset/assign", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_ids: ids, category: cid }),
      });
      const d = await res.json();
      if (!d.ok) { statusMsg(terr(d.error) || t("移动失败")); return; }
      const moved = new Set(d.updated || []);
      for (const r of runs) if (moved.has(r.dir)) r.category = cid;
      renderSide();
      refresh();
      const n = (d.updated || []).length;
      const skipped = (d.skipped || []).length;
      const target = cid ? ((categories.find(c => c.id === cid) || {}).name || t("分类")) : t("未分类");
      const skipTxt = skipped ? (LANG === "zh" ? "（跳过 " + skipped + " 项）" : " (skipped " + skipped + ")") : "";
      statusMsg(LANG === "zh"
        ? ("已把 " + n + " 项移到「" + target + "」" + skipTxt)
        : ("Moved " + n + " item(s) to \"" + target + "\"" + skipTxt));
    }

    function openAssignModal() {
      if (!selected.size) return;
      const ids = [...selected];
      const byDir = new Map(runs.map(r => [r.dir, r]));
      // 选中项当前所属分类: 全在同一个就显示名字, 否则显示"多个分类"
      const curSet = new Set(ids.map(d => (byDir.get(d) || {}).category || null));
      const curId = curSet.size === 1 ? [...curSet][0] : undefined;
      const curLabel = curId === undefined
        ? t("多个分类")
        : (curId ? ((categories.find(c => c.id === curId) || {}).name || t("分类")) : t("未分类"));

      const m = $el("div.asm-modal", { style: { display: "flex" } });
      m.appendChild($el("div.bk", { onclick: () => m.remove() }));
      const pn = $el("div.pn", { style: { width: "min(460px,92vw)" } });
      pn.appendChild(closeX(m));
      pn.appendChild($el("h3", { textContent: t("移到分类") }));

      const hint = $el("div.asm-assign-hint");
      hint.appendChild(document.createTextNode(t("已选 ") + ids.length + t(" 项") + " · " + t("当前：")));
      hint.appendChild($el("b", { textContent: curLabel }));
      pn.appendChild(hint);

      // 分类多时给个搜索框, 免得在长列表里翻
      const search = $el("input.asm-search", { type: "text" });
      search.placeholder = t("搜索分类…");
      search.style.cssText = "width:100%;margin-bottom:8px;display:" + (categories.length > 6 ? "block" : "none");
      pn.appendChild(search);

      const list = $el("div.asm-catlist.pick");
      const rows = [];
      function pickRow(label, cid, count, cls) {
        const isCur = cid === curId;
        const b = $el("button.asm-pickrow" + (isCur ? ".cur" : "") + (cls ? "." + cls : ""));
        b.appendChild($el("span.dot"));
        b.appendChild($el("span.nm", { textContent: label, title: label }));
        if (isCur) b.appendChild($el("span.tag", { textContent: t("当前") }));
        if (count !== null) b.appendChild($el("span.n", { textContent: String(count) }));
        b.dataset.kw = label.toLowerCase();
        b.onclick = async () => { m.remove(); await assignTo(ids, cid); };
        rows.push(b);
        return b;
      }

      for (const root of rootCategories()) {
        list.appendChild(pickRow(root.name, root.id, catCount(root.id)));
        for (const kid of kidsOf(root.id)) {
          list.appendChild(pickRow(kid.name, kid.id, catCount(kid.id), "child"));
        }
      }
      if (!categories.length) {
        list.appendChild($el("div.empty", { textContent: t("还没有分类，在下面新建一个") }));
      }
      pn.appendChild(list);

      // 移出分类单独一条: 它不是"选一个分类", 视觉上和上面区分开
      pn.appendChild($el("div.asm-sep", { textContent: t("或") }));
      const outRow = pickRow(t("未分类（移出分类）"), null, null, "out");
      pn.appendChild(outRow);

      search.oninput = () => {
        const kw = search.value.trim().toLowerCase();
        for (const r of rows) r.style.display = (!kw || r.dataset.kw.includes(kw)) ? "" : "none";
      };

      pn.appendChild($el("div.asm-sep", { textContent: t("或新建一个分类") }));
      const input = $el("input.asm-search", { type: "text" });
      input.placeholder = t("新建分类名称");
      input.style.flex = "1";
      input.style.minWidth = "120px";
      const createBtn = $el("button.asm-btn.primary");
      bindText(createBtn, "新建并移入");
      createBtn.onclick = async () => {
        const name = input.value.trim();
        if (!name) return;
        const res = await fetch("/asset/category", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "create", name }),
        });
        const d = await res.json();
        if (!d.ok) { statusMsg(terr(d.error) || t("新建失败")); return; }
        categories = d.categories || categories;
        m.remove();
        await assignTo(ids, d.category.id);
      };
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") createBtn.click(); });
      pn.appendChild($el("div.asm-newcat", {}, [input, createBtn]));
      pn.appendChild($el("div.asm-modal-foot", {}, [
        $el("button.asm-mini", { textContent: t("取消"), onclick: () => m.remove() }),
      ]));
      m.appendChild(pn);
      document.body.appendChild(m);
      setTimeout(() => input.focus(), 30);
    }

    // ---------- 分类管理: 新建 / 重命名 / 删除 ----------
    async function renameCategory(id, name) {
      name = (name || "").trim();
      if (!name) return false;
      const res = await fetch("/asset/category", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "rename", id, name }),
      });
      const d = await res.json();
      if (!d.ok) { statusMsg(terr(d.error) || t("重命名失败")); return false; }
      categories = d.categories || categories;
      renderSide();
      refresh();
      statusMsg(t("已重命名"));
      return true;
    }

    async function moveCategory(id, direction) {
      const res = await fetch("/asset/category", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "move", id, direction }),
      });
      const d = await res.json();
      if (!d.ok) { statusMsg(terr(d.error) || t("调整顺序失败")); return false; }
      categories = d.categories || categories;
      renderSide();
      return true;
    }

    async function pinCategory(id, pinned) {
      const res = await fetch("/asset/category", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "pin", id, pinned }),
      });
      const d = await res.json();
      if (!d.ok) { statusMsg(terr(d.error) || t("置顶失败")); return false; }
      categories = d.categories || categories;
      renderSide();
      statusMsg(pinned ? t("已置顶") : t("已取消置顶"));
      return true;
    }

    async function removeCategory(c) {
      const n = runs.filter(r => r.category === c.id).length;
      const kids = categories.filter(x => x.parent === c.id).length;
      const kidTxt = kids ? (LANG === "zh" ? "\n\n它的 " + kids + " 个子分类会上移一层，不会被删除。" : "\n\nIts " + kids + " sub-categories move up one level; they are not deleted.") : "";
      const msg = LANG === "zh"
        ? ("删除分类「" + c.name + "」？\n\n该分类下的 " + n + " 项产物会变成「未分类」，文件不会被删除。" + kidTxt)
        : ('Delete category "' + c.name + '"?\n\n' + n + " assets will become uncategorized. Files are not deleted." + kidTxt);
      if (!confirm(msg)) return false;
      const res = await fetch("/asset/category", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "delete", id: c.id }),
      });
      const d = await res.json();
      if (!d.ok) { statusMsg(terr(d.error) || t("删除失败")); return false; }
      categories = d.categories || [];
      for (const r of runs) if (r.category === c.id) r.category = null;
      renderSide();
      refresh();
      statusMsg(t("已删除分类") + (d.cleared ? " · " + d.cleared + t(" 项已转为未分类") : "") +
        (d.promoted ? " · " + d.promoted + t(" 个子分类已上移") : ""));
      return true;
    }

    function openCategoryManager() {
      const m = $el("div.asm-modal", { style: { display: "flex" } });
      m.appendChild($el("div.bk", { onclick: () => m.remove() }));
      const pn = $el("div.pn", { style: { width: "min(560px,92vw)" } });
      pn.appendChild(closeX(m));
      pn.appendChild($el("h3", { textContent: t("管理分类") }));
      pn.appendChild($el("div.asm-assign-hint", {
        textContent: t("点 ＋ 在某个分类下新建子分类；📌 置顶，↑↓ 调整顺序。删除分类不会删除文件。"),
      }));

      const list = $el("div.asm-catlist");
      let editingId = null;
      let addingUnder = null;   // 正在哪个分类下新建子分类

      function countOf(id) { return catCount(id); }

      // 同一层、同一置顶状态下的显示顺序(与侧栏一致), 用来判断 ↑↓ 是否可用
      function siblingsOf(c) {
        const par = c.parent || null;
        return categories
          .filter(x => (x.parent || null) === par && !!x.pinned === !!c.pinned)
          .sort((a, b) => a.order - b.order);
      }

      function addRow(parentId, isChild) {
        const input = $el("input.asm-mini-input", { type: "text" });
        input.placeholder = t("新分类名称");
        const save = $el("button.asm-mini", { textContent: t("保存") });
        const cancel = $el("button.asm-mini", { textContent: t("取消") });
        cancel.onclick = () => { addingUnder = null; renderList(); };
        save.onclick = async () => {
          const name = input.value.trim();
          if (!name) return;
          const res = await fetch("/asset/category", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ action: "create", name, parent: parentId }),
          });
          const d = await res.json();
          if (!d.ok) { statusMsg(terr(d.error) || t("新建失败")); return; }
          categories = d.categories || categories;
          addingUnder = null;
          renderSide();
          renderList();
          statusMsg(t("已新建分类"));
        };
        input.addEventListener("keydown", (e) => {
          if (e.key === "Enter") save.click();
          if (e.key === "Escape") cancel.click();
        });
        const row = $el("div.asm-catrow.manage" + (isChild ? ".child" : ""), {}, [input, save, cancel]);
        list.appendChild(row);
        setTimeout(() => input.focus(), 0);
      }

      function row(c, isChild) {
        if (editingId === c.id) {
          const input = $el("input.asm-mini-input", { type: "text" });
          input.value = c.name;
          const save = $el("button.asm-mini", { textContent: t("保存") });
          save.onclick = async () => {
            if (await renameCategory(c.id, input.value)) { editingId = null; renderList(); }
          };
          const cancel = $el("button.asm-mini", { textContent: t("取消") });
          cancel.onclick = () => { editingId = null; renderList(); };
          input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") save.click();
            if (e.key === "Escape") cancel.click();
          });
          list.appendChild($el("div.asm-catrow.manage" + (isChild ? ".child" : ""), {}, [input, save, cancel]));
          setTimeout(() => input.focus(), 0);
          return;
        }
        const rename = $el("button.asm-mini", { textContent: "✎", title: t("重命名") });
        rename.onclick = () => { editingId = c.id; renderList(); };
        const del = $el("button.asm-mini.danger", { textContent: "✕", title: t("删除分类") });
        del.onclick = async () => { if (await removeCategory(c)) renderList(); };

        // 置顶 + 上移/下移: 只在"同层 + 同置顶状态"的邻居之间换位
        const peers = siblingsOf(c);
        const at = peers.findIndex(x => x.id === c.id);
        const pin = $el("button.asm-mini.pin" + (c.pinned ? ".on" : ""), {
          textContent: "📌",
          title: c.pinned ? t("取消置顶") : t("置顶"),
        });
        pin.onclick = async () => { if (await pinCategory(c.id, !c.pinned)) renderList(); };
        const up = $el("button.asm-mini", { textContent: "↑", title: t("上移") });
        up.disabled = at <= 0;
        up.onclick = async () => { if (await moveCategory(c.id, "up")) renderList(); };
        const down = $el("button.asm-mini", { textContent: "↓", title: t("下移") });
        down.disabled = at < 0 || at >= peers.length - 1;
        down.onclick = async () => { if (await moveCategory(c.id, "down")) renderList(); };

        const kids = [];
        if (!isChild) {
          const add = $el("button.asm-mini", { textContent: "＋", title: t("新建子分类") });
          add.onclick = () => { addingUnder = c.id; editingId = null; renderList(); };
          kids.push(add);
        }
        list.appendChild($el("div.asm-catrow.manage" + (isChild ? ".child" : ""), {}, [
          pin,
          $el("span.catname", { textContent: c.name }),
          $el("span.catcount", { textContent: countOf(c.id) + t(" 项") }),
          up,
          down,
          ...kids,
          rename,
          del,
        ]));
      }

      function renderList() {
        list.innerHTML = "";
        if (!categories.length) {
          list.appendChild($el("div", {
            style: { fontSize: "12px", color: "var(--descrip-text,#aaa)" },
            textContent: t("还没有分类，在下面新建一个"),
          }));
          return;
        }
        for (const root of rootCategories()) {
          row(root, false);
          if (addingUnder === root.id) addRow(root.id, true);
          for (const kid of kidsOf(root.id)) row(kid, true);
        }
      }
      renderList();
      pn.appendChild(list);

      const input = $el("input.asm-search", { type: "text" });
      input.placeholder = t("新建分类名称");
      const createBtn = $el("button.asm-btn.primary");
      bindText(createBtn, "新建分类");
      createBtn.onclick = async () => {
        const name = input.value.trim();
        if (!name) return;
        const res = await fetch("/asset/category", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "create", name }),
        });
        const d = await res.json();
        if (!d.ok) { statusMsg(terr(d.error) || t("新建失败")); return; }
        categories = d.categories || categories;
        input.value = "";
        renderSide();
        renderList();
        statusMsg(t("已新建分类"));
      };
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") createBtn.click(); });
      pn.appendChild($el("div.asm-newcat", {}, [input, createBtn]));
      m.appendChild(pn);
      document.body.appendChild(m);
    }

    // ---------- 预览 ----------
    // 没有提示词时按原因给"可操作"的说明 —— 笼统的"未检测到提示词"是 issue #1 的抱怨点:
    // 用户看不出是"文件里本来就没有"还是"插件没提取到"。
    function promptHint(r) {
      if (r.positive) {
        // 有提示词: 若来自服务端兜底, 注明来源, 免得误以为文件自带元数据
        if (r.prompt_source === "history") {
          return $el("div", {
            style: { fontSize: "11px", color: "var(--descrip-text,#aaa)", marginTop: "6px" },
            textContent: LANG === "zh"
              ? "提示词由 ComfyUI 执行记录找回(该文件本身不带元数据)。"
              : "Prompt recovered from ComfyUI execution history (the file itself carries no metadata).",
          });
        }
        return null;
      }
      let msg;
      if (r.no_prompt_reason === "no_embedded_metadata") {
        if (r.kind === "audio") {
          msg = LANG === "zh"
            ? "⚠ 这个音频文件没有可读取的 ComfyUI 提示词元数据；若由 ComfyUI 生成，插件会尝试从执行记录中找回提示词和工作流。"
            : "⚠ This audio file has no readable ComfyUI prompt metadata. For files generated by ComfyUI, the plugin also tries to recover the prompt and workflow from execution history.";
        } else {
          msg = LANG === "zh"
            ? "⚠ 这个文件本身不带 ComfyUI 元数据。常见原因: 从浏览器另存、手机/微信转存后拖进 output 目录的图片, 或 ComfyUI 启动时加了 --disable-metadata。这类文件没有提示词可提取; 用「保存图像 / SaveImage」节点跑出来的图会自动归档并带上提示词。"
            : "⚠ This file carries no ComfyUI metadata. Common causes: an image saved from the browser, a phone/WeChat transfer dropped into the output directory, or ComfyUI started with --disable-metadata. Such files have no prompt to extract; images produced through a SaveImage node are archived with their prompt.";
        }
      } else if (r.no_prompt_reason === "no_text_nodes") {
        msg = LANG === "zh"
          ? "这次运行没有文本提示词节点(例如纯图像处理、证件照类工作流), 所以没有提示词可提取。"
          : "This run has no text prompt node (e.g. a pure image-processing or ID-photo workflow), so there is no prompt to extract.";
      } else {
        msg = t("(未检测到提示词)");
      }
      return $el("div", {
        style: { fontSize: "11px", color: "#e0a24a", marginTop: "6px", lineHeight: "1.6" },
        textContent: msg,
      });
    }

    // 所有弹窗共用的关闭按钮: 自带深色圆底, 压在图片/视频上也看得见
    function closeX(modal) {
      const b = $el("button.x", { textContent: "✕", title: t("关闭") });
      b.setAttribute("aria-label", t("关闭"));
      b.onclick = () => modal.remove();
      return b;
    }

    function openPreview(r) {
      const m = $el("div.asm-modal");
      m.style.display = "flex";
      const full = mediaUrl(r.dir, r.media);
      const media = r.kind === "video"
        ? $el("video", { src: full, controls: true, autoplay: true, muted: true, playsinline: true })
        : r.kind === "audio"
          ? $el("audio", { src: full, controls: true, preload: "metadata" })
          : $el("img", { src: full });
      const duration = Number(r.media_duration);
      const durationLabel = Number.isFinite(duration) && duration > 0
        ? Math.floor(duration / 60) + ":" + String(Math.floor(duration % 60)).padStart(2, "0")
        : "";
      const ta = $el("textarea", { textContent: (r.positive || "") + (r.negative ? "\n\nNegative prompt: " + r.negative : "") });
      const ph = promptHint(r);
      const models = (r.models || []).join(", ") || "—";
      const params = Object.keys(r.params || {}).map(k => k + "=" + r.params[k]).join(" · ") || "—";
      const pn = $el("div.pn.preview", {}, [
        closeX(m),
        media,
        $el("div.rows", {}, [
          labeledRow([{ zh: "来源: ", text: r.name }]),
          labeledRow([{ zh: "时间: ", text: r.time + " | " }, { zh: "模型/LoRA: ", text: models }]),
          ...(durationLabel ? [labeledRow([{ zh: "时长: ", text: durationLabel }])] : []),
          labeledRow([{ zh: "参数: ", text: params }]),
        ]),
        bindText($el("label", { style: { fontSize: "12px" } }), "提示词"),
        ta,
        ...(ph ? [ph] : []),
        $el("div.btns", {}, [
          bindText($el("button.asm-btn", { onclick: () => { ta.select(); navigator.clipboard?.writeText(ta.value).then(() => statusMsg(t("已复制"))); } }), "复制提示词"),
          bindText($el("button.asm-btn.primary", { onclick: () => downloadWorkflow(r) }), "下载 workflow.json"),
          bindText($el("button.asm-btn.danger", { onclick: () => doDelete(r, m) }), "🗑 从硬盘删除"),
        ]),
        bindText($el("div", { style: { fontSize: "11px", color: "var(--descrip-text,#aaa)", marginTop: "8px" } }), "💡 下载 workflow.json 后拖进 ComfyUI 画布, 即可完整还原整套工作流(节点+连线)。"),
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
      const fOut = $el("input", { value: curConfig.current_output_dir || "" });
      bindText(fOut, "留空=使用 ComfyUI 默认 output", "placeholder");
      const fArch = $el("input", { value: curConfig.archive_dir || c.archive_dir || "" });
      const fBak = $el("input", { value: c.backup_dir || "" });
      const fAuto = $el("input", { type: "checkbox" });
      fAuto.checked = c.auto_archive !== false;
      const fExisting = $el("input", { type: "checkbox" });
      fExisting.checked = c.archive_existing === true;
      const fThumb = $el("input", { type: "number", min: 100, max: 2000, value: String(c.thumb_width || 480) });
      const fInterval = $el("input", { type: "number", min: 3, max: 3600, value: String(c.interval_sec || 10) });

      const row = (zh, input, browse) => $el("div.row", {}, [
        bindText($el("label"), zh), input,
        browse ? bindText($el("button.asm-btn", { onclick: () => browseDir(input) }), "浏览…") : null,
      ].filter(Boolean));

      const pn = $el("div.pn", {}, [
        closeX(m),
        bindText($el("h2", { style: { margin: "0 0 10px", fontSize: "15px" } }), "⚙ 资产设置"),
        $el("div.asm-set", {}, [
          row("输出目录", fOut, true),
          row("归档库目录", fArch, true),
          row("备份目录", fBak, true),
          $el("div.chk", {}, [fAuto, bindText($el("span"), "自动归档新产物")]),
          $el("div.chk", {}, [fExisting, bindText($el("span"), "归档安装前已有的产物")]),
          row("缩略图宽度(px)", fThumb),
          row("扫描间隔(秒)", fInterval),
        ]),
        $el("div.btns", {}, [
          bindText($el("button.asm-btn.primary", { onclick: saveSettings }), "保存设置"),
        ]),
        bindText($el("div", { style: { fontSize: "11px", color: "var(--descrip-text,#aaa)", marginTop: "10px" } }), "改归档/备份目录后新产物进入新目录, 旧数据保留; 输出目录切换重启 ComfyUI 后仍生效; 自动归档开关和扫描间隔即时生效。"),
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
          archive_existing: fExisting.checked,
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
        closeX(m),
        bindText($el("h2", { style: { margin: "0 0 10px", fontSize: "15px" } }), "📁 选择目录"),
        pathEl,
        $el("div.btns", { style: { margin: "8px 0" } }, [
          bindText($el("button.asm-btn", { onclick: async () => {
            try {
              const res = await fetch("/asset/browse_dir?path=" + encodeURIComponent(curPath));
              const d = await res.json();
              if (d.ok) load(d.parent || "");
            } catch (e) {}
          } }), "⬆ 上一级"),
        ]),
        listEl,
        $el("div.btns", { style: { marginTop: "12px" } }, [
          bindText($el("button.asm-btn.primary", { onclick: () => { inputEl.value = curPath; m.remove(); } }), "✅ 选择此目录"),
          bindText($el("button.asm-btn", { onclick: () => m.remove() }), "取消"),
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
      const bakRow = $el("div", { style: { fontSize: "13px", marginBottom: "14px", wordBreak: "break-all" } });
      const bakPrefix = $el("span");
      bindText(bakPrefix, "备份目录: ");
      bakRow.appendChild(bakPrefix);
      bakRow.appendChild(document.createTextNode(bakDir));
      const pn = $el("div.pn", {}, [
        closeX(m),
        bindText($el("h2", { style: { margin: "0 0 12px", fontSize: "15px" } }), "💾 备份确认"),
        bindText($el("div", { style: { fontSize: "13px", marginBottom: "6px" } }), "将备份以下内容:"),
        bindText($el("div", { style: { fontSize: "13px", color: "var(--descrip-text,#aaa)", marginBottom: "12px", lineHeight: "1.8" } }), "• 资产库（图片/视频/元数据/工作流）<br>• 工作流文件 (user/default/workflows)<br>• 插件配置", "innerHTML"),
        bakRow,
        $el("div.btns", {}, [
          bindText($el("button.asm-btn.primary", { onclick: () => { m.remove(); doBackup(); } }), "确定备份"),
          bindText($el("button.asm-btn", { onclick: () => m.remove() }), "取消"),
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
      try {
        const c = await (await fetch("/asset/categories")).json();
        if (c.ok) categories = c.categories || [];
      } catch (e) {}
      try { curConfig = await (await fetch("/asset/config")).json(); } catch (e) {}
    }
    async function openPanel() {
      detectLang();
      relabel();
      overlay.style.display = "flex";
      statusMsg(t("加载中…"));
      fixLinkRenderMode();
      await loadRuns();
      if (runs.length) {
        const d = runs[0].date;
        calYear = Number(d.slice(0, 4)); calMonth = Number(d.slice(5, 7)) - 1; selDate = d;
      }
      renderSide();
      refresh();
      statusMsg(t("共 ") + runs.length + t(" 条资产"));
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(pollRefresh, 8000);
    }
    function closePanel() {
      overlay.style.display = "none";
      if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    }
    function checkLang() {
      const prev = LANG;
      detectLang();
      if (LANG !== prev) {
        relabel();
        if (overlay.style.display === "flex") refresh();
      }
    }
    async function pollRefresh() {
      checkLang();
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
          renderSide();
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
      relabelers.push(() => {
        try {
          const span = btn.element && btn.element.querySelector("span");
          if (span) span.textContent = t("资产管理");
          if (btn.element) btn.element.title = t("浏览/搜索/删除产物, 切换输出目录, 备份");
        } catch (e) {}
      });
    } catch (e) {
      console.error("AssetManager 菜单按钮注册失败:", e);
    }

    // 全局语言轮询: 始终跟随 ComfyUI 语言(含菜单按钮), 无需面板打开
    setInterval(checkLang, 1000);
  },
});
