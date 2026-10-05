// 学生端交互:单词卡片 + 单词测验
// 小工具:发起请求并检查状态
async function fetchJSON(url, options) {
  const res = await fetch(url, options);
  if (res.status === 401) {
    // 会话过期/被禁用:跳去登录页,登录后回到当前页面
    location.href = "/login?next=" + encodeURIComponent(location.pathname + location.search);
    const err = new Error("请先登录");
    err.status = 401;
    throw err;
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const err = new Error(data.detail || "请求失败,请稍后再试");
    err.status = res.status; // 供进度迁移逻辑判断 404
    throw err;
  }
  return res.json();
}

// 朗读:使用浏览器自带的语音合成,无需联网
// rate 默认 0.85(单词朗读用,稍慢方便听清);听力训练传 1.0 用常速(接近四级听力语速)
function speak(text, rate = 0.85) {
  if (!text) return;
  if (!("speechSynthesis" in window)) {
    alert("当前浏览器不支持语音朗读,换 Chrome 或 Edge 试试");
    return;
  }
  window.speechSynthesis.cancel(); // 连续点击时从头开始读
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = rate;
  window.speechSynthesis.speak(utterance);
}

/* ==================== 学习进度(保存在服务器,按账号隔离) ==================== */
// 旧版本把进度存在浏览器 localStorage 里,这两个键名保留,只用于首次登录时迁移
const TASK_DICT_STORAGE_KEYS = {
  gaokao: "task3500_mastered",
  cet4: "task_cet4_mastered",
};

const progressCache = new Map(); // dictKey -> Set(页内缓存,避免重复请求)

// 读取某本词库的进度;服务器没有记录时,把旧 localStorage 数据迁移上去(只做一次)
async function loadProgress(dictKey) {
  if (progressCache.has(dictKey)) return progressCache.get(dictKey);
  try {
    const data = await fetchJSON("/api/progress?dict_key=" + dictKey);
    const set = new Set(data.indices);
    progressCache.set(dictKey, set);
    return set;
  } catch (err) {
    if (err.status === 401) return new Set(); // 已在 fetchJSON 里跳转登录页
    if (err.status === 404) {
      // 服务器上还没有这条记录:把旧浏览器进度搬进账号
      const legacyRaw = localStorage.getItem(TASK_DICT_STORAGE_KEYS[dictKey]);
      if (legacyRaw !== null) {
        try {
          const legacySet = new Set(JSON.parse(legacyRaw || "[]"));
          const ok = await saveProgress(dictKey, legacySet);
          if (ok) localStorage.removeItem(TASK_DICT_STORAGE_KEYS[dictKey]); // 上传成功才删旧数据
          return legacySet;
        } catch {
          // 旧数据损坏解析失败:留着不动,不影响正常学习
        }
      }
      return new Set();
    }
    alert(err.message);
    return new Set();
  }
}

// 保存进度:先更新本地缓存(界面立即生效),再发给服务器;失败弹提示并回滚
async function saveProgress(dictKey, set) {
  const before = new Set(progressCache.get(dictKey) || []);
  progressCache.set(dictKey, set);
  try {
    await fetchJSON("/api/progress", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dict_key: dictKey, indices: [...set] }),
    });
    return true;
  } catch (err) {
    if (err.status !== 401) alert("进度保存失败:" + err.message);
    progressCache.set(dictKey, before);
    return false;
  }
}

/* ==================== 单词学习 ==================== */
// 两种模式:按组学习(默认,单词任务分组顺序推进)/ 分类学习(后台添加的单词)
const wordsPage = document.getElementById("words-page");
if (wordsPage) {
  const modeTabs = document.getElementById("word-mode-tabs");
  const groupsMode = document.getElementById("groups-mode");
  const categoryMode = document.getElementById("category-mode");
  let mode = "groups"; // 当前模式

  // 模式切换
  modeTabs.addEventListener("click", (e) => {
    const tab = e.target.closest(".chip");
    if (!tab) return;
    mode = tab.dataset.mode;
    modeTabs.querySelectorAll(".chip").forEach((t) => t.classList.toggle("active", t === tab));
    groupsMode.classList.toggle("hidden", mode !== "groups");
    categoryMode.classList.toggle("hidden", mode !== "category");
  });

  /* ---------- 模式二:分类学习(后台单词,原有功能) ---------- */
  const flashcard = document.getElementById("flashcard");
  const chips = document.getElementById("category-chips");
  const cardCategory = document.getElementById("card-category");
  const cardEn = document.getElementById("card-en");
  const cardPhonetic = document.getElementById("card-phonetic");
  const cardCn = document.getElementById("card-cn");
  const cardExample = document.getElementById("card-example");
  const cardExampleCn = document.getElementById("card-example-cn");
  const cardProgress = document.getElementById("card-progress");
  const emptyTip = document.getElementById("words-empty");
  const btnPrev = document.getElementById("btn-prev");
  const btnNext = document.getElementById("btn-next");
  const soundFront = document.getElementById("card-sound-front");
  const soundBack = document.getElementById("card-sound-back");

  let dbWords = [];
  let dbIndex = 0;
  let currentCategory = "全部";

  // 加载分类按钮
  async function loadCategories() {
    const categories = await fetchJSON("/api/categories");
    chips.innerHTML = "";
    ["全部", ...categories].forEach((c) => {
      const btn = document.createElement("button");
      btn.className = "chip" + (c === currentCategory ? " active" : "");
      btn.textContent = c;
      btn.addEventListener("click", () => {
        currentCategory = c;
        chips.querySelectorAll(".chip").forEach((el) => el.classList.remove("active"));
        btn.classList.add("active");
        loadWords();
      });
      chips.appendChild(btn);
    });
  }

  // 加载分类单词列表
  async function loadWords() {
    try {
      dbWords = await fetchJSON("/api/words?category=" + encodeURIComponent(currentCategory));
    } catch (err) {
      dbWords = [];
      alert(err.message);
    }
    dbIndex = 0;
    renderCard();
  }

  // 渲染当前卡片
  function renderCard() {
    const w = dbWords[dbIndex];
    const empty = !w;
    flashcard.classList.toggle("hidden", empty);
    btnPrev.disabled = empty || dbWords.length <= 1;
    btnNext.disabled = empty || dbWords.length <= 1;
    emptyTip.classList.toggle("hidden", !empty);
    if (!w) { cardProgress.textContent = "0 / 0"; return; }

    flashcard.classList.remove("flipped");
    cardCategory.textContent = w.category;
    cardEn.textContent = w.english;
    cardPhonetic.textContent = w.phonetic || "";
    cardCn.textContent = w.chinese;
    cardExample.textContent = w.example || "";
    cardExampleCn.textContent = w.example_cn || "";
    cardProgress.textContent = `${dbIndex + 1} / ${dbWords.length}`;
  }

  flashcard.addEventListener("click", () => flashcard.classList.toggle("flipped"));
  btnPrev.addEventListener("click", () => { dbIndex = (dbIndex - 1 + dbWords.length) % dbWords.length; renderCard(); });
  btnNext.addEventListener("click", () => { dbIndex = (dbIndex + 1) % dbWords.length; renderCard(); });

  // 朗读按钮(stopPropagation 防止点按钮时卡片跟着翻面)
  soundFront.addEventListener("click", (e) => { e.stopPropagation(); speak(dbWords[dbIndex]?.english || ""); });
  soundBack.addEventListener("click", (e) => { e.stopPropagation(); speak(dbWords[dbIndex]?.english || ""); });

  /* ---------- 模式一:按组学习(和单词任务同词库、共享进度) ---------- */
  const dictTabs = document.getElementById("words-dict-tabs");
  const gCard = document.getElementById("gcard");
  const gBadge = document.getElementById("gcard-badge");
  const gEn = document.getElementById("gcard-en");
  const gPhonetic = document.getElementById("gcard-phonetic");
  const gCn = document.getElementById("gcard-cn");
  const gProgress = document.getElementById("gcard-progress");
  const gGroupNo = document.getElementById("words-group-no");
  const gDoneNum = document.getElementById("words-group-done-num");
  const gTotal = document.getElementById("words-group-total");
  const gFill = document.getElementById("words-group-fill");
  const gBanner = document.getElementById("words-group-banner");
  const gBannerText = document.getElementById("words-banner-text");
  const gBannerButtons = document.getElementById("words-banner-buttons");
  const gPrev = document.getElementById("gbtn-prev");
  const gNext = document.getElementById("gbtn-next");
  const gMaster = document.getElementById("gbtn-master");
  const gSoundF = document.getElementById("gcard-sound-front");
  const gSoundB = document.getElementById("gcard-sound-back");

  let dictKey = new URLSearchParams(location.search).get("dict") || "gaokao";
  let dictLabel = "高考 3500 词";
  let groupNo = parseInt(new URLSearchParams(location.search).get("group"), 10) || 0; // 0 = 自动定位到第一个没学完的组
  let groupWords = [];   // 当前组的单词
  let gIndex = 0;        // 组内当前位置
  let mastered = new Set(); // 当前词库已掌握的编号集合,loadProgress 完成后填充
  let gGroups = 0, gGroupSize = 30, gWordTotal = 0;
  let jumpTimer = null;  // 学完本组后自动跳下一组的定时器

  // 地址栏同步当前词库和组号(刷新后还能回到这里)
  function updateURL() {
    const u = new URL(location.href);
    u.searchParams.set("dict", dictKey);
    if (groupNo) u.searchParams.set("group", groupNo);
    history.replaceState(null, "", u);
  }

  // 加载词库切换按钮
  async function loadDictTabs() {
    const dicts = await fetchJSON("/api/tasks/dictionaries");
    if (!dicts.some((d) => d.key === dictKey)) {
      // 地址栏里的词库无效:改回默认词库,进度集合也要跟着换
      dictKey = dicts[0].key;
      mastered = await loadProgress(dictKey);
    }
    dictLabel = dicts.find((d) => d.key === dictKey)?.label || dictKey;

    dictTabs.innerHTML = "";
    dicts.forEach((d) => {
      const btn = document.createElement("button");
      btn.className = "chip" + (d.key === dictKey ? " active" : "");
      btn.textContent = `${d.label}(${d.total}词)`;
      btn.addEventListener("click", async () => {
        if (d.key === dictKey) return;
        dictKey = d.key;
        dictLabel = d.label;
        mastered = await loadProgress(dictKey);
        groupNo = 0; // 换词库后重新定位到第一个没学完的组
        dictTabs.querySelectorAll(".chip").forEach((el) => el.classList.remove("active"));
        btn.classList.add("active");
        initGroupFlow();
      });
      dictTabs.appendChild(btn);
    });
    initGroupFlow();
  }

  // 初始化分组学习流程:确定从哪一组开始
  async function initGroupFlow() {
    const s = await fetchJSON(`/api/tasks/summary?dict_key=${dictKey}`);
    gGroups = s.groups;
    gGroupSize = s.group_size;
    gWordTotal = s.total;
    if (!groupNo || groupNo > gGroups) groupNo = firstIncompleteGroup();
    if (!groupNo) groupNo = 1; // 全部学完时回到第 1 组复习
    await loadGroup(groupNo);
  }

  // 第一个还有没掌握单词的组(全部学完返回 0)
  function firstIncompleteGroup() {
    for (let g = 1; g <= gGroups; g++) {
      const start = (g - 1) * gGroupSize;
      const size = Math.min(gGroupSize, gWordTotal - start);
      let done = 0;
      for (let i = start; i < start + size; i++) if (mastered.has(i)) done++;
      if (done < size) return g;
    }
    return 0;
  }

  // 本组已掌握的数量
  function groupDoneCount() {
    return groupWords.filter((w) => mastered.has(w.index)).length;
  }

  function clearJump() {
    if (jumpTimer) { clearTimeout(jumpTimer); jumpTimer = null; }
  }

  async function loadGroup(g) {
    clearJump();
    groupNo = g;
    updateURL();
    try {
      const data = await fetchJSON(`/api/tasks/words?dict_key=${dictKey}&group=${groupNo}`);
      groupWords = data.words;
      gIndex = 0;
      renderGroup();
    } catch (err) {
      alert(err.message);
    }
  }

  function renderGroup() {
    clearJump();
    const w = groupWords[gIndex];
    if (!w) return;
    gCard.classList.remove("flipped", "hidden");
    gBadge.textContent = `${dictLabel} 第 ${groupNo} 组`;
    gEn.textContent = w.english;
    gPhonetic.textContent = w.phonetic || "";
    gCn.textContent = w.chinese;
    gProgress.textContent = `${gIndex + 1} / ${groupWords.length}`;

    const done = groupDoneCount();
    gGroupNo.textContent = groupNo;
    gDoneNum.textContent = done;
    gTotal.textContent = groupWords.length;
    gFill.style.width = ((done / groupWords.length) * 100).toFixed(1) + "%";
    gMaster.textContent = mastered.has(w.index) ? "↩ 取消标记" : "✓ 标记已掌握";
    gMaster.classList.toggle("task-master-marked", mastered.has(w.index));
    gPrev.disabled = groupWords.length <= 1;
    gNext.disabled = groupWords.length <= 1;
    gMaster.disabled = false;

    const allDone = done === groupWords.length;
    gBanner.classList.toggle("hidden", !allDone);
    if (!allDone) gBannerButtons.innerHTML = "";
  }

  // 标记已掌握:标记后自动跳到下一个;本组全部学完后自动进入下一组
  gMaster.addEventListener("click", () => {
    const w = groupWords[gIndex];
    if (!w) return;
    if (mastered.has(w.index)) {
      mastered.delete(w.index);
      saveProgress(dictKey, mastered);
      renderGroup();
    } else {
      mastered.add(w.index);
      saveProgress(dictKey, mastered);
      gIndex = (gIndex + 1) % groupWords.length;
      renderGroup();
      maybeJumpToNextGroup();
    }
  });

  // 学完本组:提示并自动进入下一组(最后一组则显示全部完成)
  function maybeJumpToNextGroup() {
    if (groupDoneCount() < groupWords.length) return;
    if (groupNo >= gGroups) {
      gBannerText.textContent = `🎉 恭喜!「${dictLabel}」所有组都学完了!`;
      gBannerButtons.innerHTML = '<button class="btn btn-outline" id="gbtn-reset-group">↩ 清除本组记录</button>';
      document.getElementById("gbtn-reset-group").addEventListener("click", () => {
        if (!confirm("确定要清除本组的学习记录吗?")) return;
        for (const w of groupWords) mastered.delete(w.index);
        saveProgress(dictKey, mastered);
        renderGroup();
      });
    } else {
      gBannerText.textContent = `🎉 第 ${groupNo} 组学完!即将进入第 ${groupNo + 1} 组…`;
      gBannerButtons.innerHTML = `<button class="btn btn-primary" id="btn-next-group-now">立即进入第 ${groupNo + 1} 组 →</button>`;
      document.getElementById("btn-next-group-now").addEventListener("click", () => loadGroup(groupNo + 1));
      jumpTimer = setTimeout(() => loadGroup(groupNo + 1), 2000);
    }
  }

  gCard.addEventListener("click", () => gCard.classList.toggle("flipped"));
  gPrev.addEventListener("click", () => { gIndex = (gIndex - 1 + groupWords.length) % groupWords.length; renderGroup(); });
  gNext.addEventListener("click", () => { gIndex = (gIndex + 1) % groupWords.length; renderGroup(); });

  // 朗读按钮(stopPropagation 防止点按钮时卡片跟着翻面)
  gSoundF.addEventListener("click", (e) => { e.stopPropagation(); speak(groupWords[gIndex]?.english || ""); });
  gSoundB.addEventListener("click", (e) => { e.stopPropagation(); speak(groupWords[gIndex]?.english || ""); });

  // 键盘操作:← → 切换,空格翻面(按当前模式作用于对应卡片)
  document.addEventListener("keydown", (e) => {
    if (mode === "groups") {
      if (!groupWords.length) return;
      if (e.key === "ArrowLeft") { gIndex = (gIndex - 1 + groupWords.length) % groupWords.length; renderGroup(); }
      if (e.key === "ArrowRight") { gIndex = (gIndex + 1) % groupWords.length; renderGroup(); }
      if (e.key === " ") { e.preventDefault(); gCard.classList.toggle("flipped"); }
    } else {
      if (!dbWords.length) return;
      if (e.key === "ArrowLeft") { dbIndex = (dbIndex - 1 + dbWords.length) % dbWords.length; renderCard(); }
      if (e.key === "ArrowRight") { dbIndex = (dbIndex + 1) % dbWords.length; renderCard(); }
      if (e.key === " ") { e.preventDefault(); flashcard.classList.toggle("flipped"); }
    }
  });

  loadCategories().then(loadWords);
  // 先加载账号里的进度,再开始按组学习(不能顶层 await,用 .then 引导)
  loadProgress(dictKey)
    .then((s) => { mastered = s; loadDictTabs(); })
    .catch((err) => alert(err.message));
}

/* ==================== 句子测验 ==================== */
const quizBox = document.getElementById("quiz-box");
if (quizBox) {
  const TOTAL = 10; // "全部随机"一轮的题目数(选组/重做按本地列表长度)
  const startView = document.getElementById("quiz-start");
  const questionView = document.getElementById("quiz-question");
  const endView = document.getElementById("quiz-end");
  const groupChips = document.getElementById("quiz-group-chips");
  const quizIndex = document.getElementById("quiz-index");
  const quizTotal = document.getElementById("quiz-total");
  const quizScore = document.getElementById("quiz-score");
  const quizGroupName = document.getElementById("quiz-group-name");
  const quizWord = document.getElementById("quiz-word");
  const quizOptions = document.getElementById("quiz-options");
  const quizFeedback = document.getElementById("quiz-feedback");
  const quizResult = document.getElementById("quiz-result");
  const finalScore = document.getElementById("quiz-final-score");
  const finalMessage = document.getElementById("quiz-final-message");
  const wordPop = document.getElementById("word-pop");
  const roundHint = document.getElementById("quiz-round-hint");

  let currentGroup = 0;      // 当前选题范围:0 = 全部随机,>0 = 第几组
  let currentGroupLabel = "全部随机";
  let roundMode = "group";   // 出题模式:"group" 按组出题 / "redo" 重做错题
  let roundQuestions = [];   // 本轮题目列表(选组/重做在本地,全部随机逐题向服务器要)
  let quizGroupSize = 50;    // 每组题数(从 /api/quiz/groups 取)
  let quizProgress = {};     // 已完成的组:{组号: {score, total}}
  let quizDrafts = {};       // 进行中的草稿:{组号: {next_index, score, total}}
  let wrongQuestions = [];   // 最近一轮答错的题 {english, options, correct_answer}
  let newWrongs = [];        // 本轮(含重做)又答错的题,供下一轮重做
  let current = 0;   // 当前是第几题
  let score = 0;     // 答对题数
  let currentQ = null; // 当前题目
  let answered = false;

  document.getElementById("btn-start").addEventListener("click", () => startRound("group"));
  document.getElementById("btn-next-question").addEventListener("click", nextQuestion);
  document.getElementById("btn-restart").addEventListener("click", () => startRound(roundMode));
  document.getElementById("btn-redo-wrong").addEventListener("click", () => startRound("redo"));
  document.getElementById("btn-back-groups").addEventListener("click", backToGroups);
  document.getElementById("btn-quit-round").addEventListener("click", quitRound);
  document.getElementById("quiz-sound").addEventListener("click", () => speak(currentQ?.english || ""));

  // 加载题库概况,生成"全部随机 + 第 1~20 组"选择按钮
  // 组按钮三色:白=没做过 / 黄"进行中"=上次没做完 / 绿✓=已完成
  async function loadGroups() {
    const s = await fetchJSON("/api/quiz/groups");
    quizGroupSize = s.group_size;
    try {
      quizProgress = (await fetchJSON("/api/quiz/progress")).records;
      quizDrafts = (await fetchJSON("/api/quiz/drafts")).drafts;
    } catch (err) {
      // 成绩/草稿加载失败(如会话过期跳登录页)不影响选题,忽略即可
    }
    // 已完成的小组即使有残留草稿也按绿色算
    for (const g of Object.keys(quizDrafts)) {
      if (quizProgress[g]) delete quizDrafts[g];
    }
    const mk = (g, label) => {
      const btn = document.createElement("button");
      btn.className =
        "chip" +
        (g === currentGroup ? " active" : "") +
        (g > 0 && quizProgress[g] ? " done" : g > 0 && quizDrafts[g] ? " partial" : "");
      btn.textContent = label;
      btn.dataset.group = g;
      btn.addEventListener("click", () => {
        currentGroup = g;
        currentGroupLabel = label;
        groupChips.querySelectorAll(".chip").forEach((el) => el.classList.remove("active"));
        btn.classList.add("active");
        updateHint();
      });
      groupChips.appendChild(btn);
    };
    mk(0, "全部随机");
    for (let g = 1; g <= s.groups; g++) mk(g, `第 ${g} 组`);
    updateHint();
  }

  // 根据当前选中的范围更新提示文字(进行中的组显示上次做到哪)
  function updateHint() {
    if (currentGroup === 0) {
      roundHint.textContent = "全部随机:随机抽 10 题,答完立刻知道对错。";
      return;
    }
    const d = quizDrafts[currentGroup];
    roundHint.textContent = d
      ? (d.next_index > 1
        ? `第 ${currentGroup} 组:上次做到第 ${d.next_index - 1} / ${quizGroupSize} 题,点"开始测验"接着做。`
        : `第 ${currentGroup} 组:上次刚开始做,点"开始测验"接着做。`)
      : `第 ${currentGroup} 组:本组共 ${quizGroupSize} 题,一次做完;完成后本组标记为 ✓ 已完成。`;
  }

  // 这一轮的题目总数:选组/重做按本地列表长度,全部随机固定 10 题
  function roundTotal() {
    return roundQuestions.length || TOTAL;
  }

  async function startRound(mode) {
    roundMode = mode;
    newWrongs = [];
    current = 0;
    score = 0;
    if (mode === "redo") {
      roundQuestions = [...wrongQuestions]; // 重做错题:题目在本地
    } else if (currentGroup > 0) {
      try {
        // 选组测验:没做完的组先恢复上次的草稿,否则取一整组新题
        let draft = null;
        if (!quizProgress[currentGroup]) {
          try {
            draft = (await fetchJSON(`/api/quiz/draft?group=${currentGroup}`)).draft;
          } catch (err) {
            // 404 = 没有草稿,正常开始
          }
        }
        if (draft && draft.questions && draft.questions.length) {
          roundQuestions = draft.questions;
          current = (draft.next_index || 1) - 1;
          score = draft.score || 0;
          newWrongs = draft.wrongs || [];
        } else {
          const qs = await fetchJSON(`/api/quiz/group-questions?group=${currentGroup}`);
          roundQuestions = qs.map((q) => ({ english: q.english, chinese: q.chinese, options: q.options }));
        }
      } catch (err) {
        alert(err.message);
        return;
      }
    } else {
      roundQuestions = []; // 全部随机:每题向服务器现取
    }
    startView.classList.add("hidden");
    endView.classList.add("hidden");
    questionView.classList.remove("hidden");
    nextQuestion();
  }

  function backToGroups() {
    closeWordPop();
    questionView.classList.add("hidden");
    endView.classList.add("hidden");
    startView.classList.remove("hidden");
  }

  // 退出本轮:选组测验把进度存成草稿(该组变黄色"进行中"),下次点进接着做
  // 全部随机/错题重做不存草稿,直接退出
  function quitRound() {
    if (roundMode !== "group" || currentGroup === 0) return backToGroups();
    if (!confirm("退出后进度会保存,下次点进这一组可以接着做。确定退出吗?")) return;
    const draft = {
      questions: roundQuestions,
      next_index: answered ? current + 1 : current, // 没答完的题下次重新出现
      score,
      wrongs: newWrongs,
    };
    fetchJSON("/api/quiz/draft", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ group_no: currentGroup, draft }),
    })
      .then(() => {
        quizDrafts[currentGroup] = { next_index: draft.next_index, score, total: roundQuestions.length };
        const chip = groupChips.querySelector(`.chip[data-group="${currentGroup}"]`);
        if (chip && !chip.classList.contains("done")) chip.classList.add("partial");
        updateHint();
        backToGroups();
      })
      .catch((err) => alert(`进度保存失败:${err.message}`));
  }

  async function nextQuestion() {
    current++;
    if (current > roundTotal()) return endRound();
    answered = false;
    quizIndex.textContent = current;
    quizTotal.textContent = roundTotal();
    quizScore.textContent = score;
    quizGroupName.textContent = roundMode === "redo" ? "错题重做" : currentGroupLabel;
    quizFeedback.classList.add("hidden");
    quizOptions.innerHTML = "";
    closeWordPop();

    try {
      if (roundQuestions.length) {
        // 选组/重做:题目在本地列表里
        currentQ = roundQuestions[current - 1];
      } else {
        const q = await fetchJSON(`/api/quiz/question?group=${currentGroup}`);
        currentQ = { english: q.english, options: q.options };
      }
      renderSentence(currentQ.english);
      currentQ.options.forEach((text) => {
        const btn = document.createElement("button");
        btn.className = "quiz-option";
        btn.textContent = text;
        btn.addEventListener("click", () => answer(text, btn));
        quizOptions.appendChild(btn);
      });
    } catch (err) {
      alert(err.message);
      questionView.classList.add("hidden");
      startView.classList.remove("hidden");
    }
  }

  // 句子按单词拆成可点击的片段
  function renderSentence(sentence) {
    quizWord.innerHTML = "";
    sentence.split(/\s+/).forEach((token) => {
      const span = document.createElement("span");
      span.className = "quiz-word-token";
      span.dataset.word = token;
      span.textContent = token;
      quizWord.appendChild(span);
      quizWord.appendChild(document.createTextNode(" "));
    });
  }

  /* ---------- 点词查义 ---------- */
  // 事件委托:点句子里任意单词都走这里
  quizWord.addEventListener("click", (e) => {
    const token = e.target.closest(".quiz-word-token");
    if (token) showWordPop(token);
  });

  async function showWordPop(token) {
    quizWord.querySelectorAll(".quiz-word-token.active").forEach((t) => t.classList.remove("active"));
    token.classList.add("active");
    // 气泡定位在单词下方,超出屏幕右缘时往左收
    const rect = token.getBoundingClientRect();
    wordPop.style.left = `${Math.min(rect.left, window.innerWidth - 276)}px`;
    wordPop.style.top = `${rect.bottom + 6}px`;
    wordPop.classList.remove("hidden");
    wordPop.innerHTML = '<p class="word-pop-loading">查询中…</p>';
    try {
      const r = await fetchJSON(`/api/word-lookup?word=${encodeURIComponent(token.dataset.word)}`);
      wordPop.innerHTML = "";
      const head = document.createElement("div");
      head.className = "word-pop-head";
      const w = document.createElement("span");
      w.className = "word-pop-word";
      w.textContent = r.word;
      head.appendChild(w);
      if (r.found) {
        const s = document.createElement("button");
        s.className = "sound-btn word-pop-sound";
        s.textContent = "🔊";
        s.addEventListener("click", () => speak(r.word));
        head.appendChild(s);
      }
      wordPop.appendChild(head);
      const ph = document.createElement("p");
      ph.className = "word-pop-phonetic";
      ph.textContent = r.phonetic || "";
      wordPop.appendChild(ph);
      const cn = document.createElement("p");
      cn.className = "word-pop-cn";
      cn.textContent = r.chinese;
      wordPop.appendChild(cn);
    } catch (err) {
      wordPop.innerHTML = '<p class="word-pop-cn">查询失败,请重试</p>';
    }
  }

  function closeWordPop() {
    wordPop.classList.add("hidden");
    quizWord.querySelectorAll(".quiz-word-token.active").forEach((t) => t.classList.remove("active"));
  }

  // 点击气泡和句子单词以外的地方,或按 Esc,关闭气泡
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".quiz-word-token") && !e.target.closest("#word-pop")) closeWordPop();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeWordPop();
  });

  /* ---------- 答题与判分 ---------- */
  async function answer(text, btn) {
    if (answered) return; // 防止重复作答
    answered = true;
    // 先禁用所有选项,防止再次点击
    quizOptions.querySelectorAll(".quiz-option").forEach((b) => (b.disabled = true));

    try {
      if (roundQuestions.length) {
        // 选组/重做:题目在本地,直接对答案
        const correctAnswer = currentQ.correct_answer ?? currentQ.chinese;
        markAnswer(text, btn, text === correctAnswer, correctAnswer);
      } else {
        const r = await fetchJSON("/api/quiz/answer", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ english: currentQ.english, answer: text }),
        });
        currentQ.correct_answer = r.correct_answer;
        markAnswer(text, btn, r.correct, r.correct_answer);
      }
      quizFeedback.classList.remove("hidden");
    } catch (err) {
      alert(err.message);
    }
  }

  function markAnswer(text, btn, correct, correctAnswer) {
    if (correct) {
      btn.classList.add("correct");
      score++;
      quizScore.textContent = score;
      quizResult.textContent = "✓ 回答正确!";
      quizResult.className = "quiz-result good";
    } else {
      btn.classList.add("wrong");
      quizOptions.querySelectorAll(".quiz-option").forEach((b) => {
        if (b.textContent === correctAnswer) b.classList.add("correct");
      });
      quizResult.textContent = `✗ 回答错误,正确答案是:${correctAnswer}`;
      quizResult.className = "quiz-result bad";
      newWrongs.push(currentQ); // 记入错题,结束后可重做
    }
  }

  function endRound() {
    questionView.classList.add("hidden");
    endView.classList.remove("hidden");
    wrongQuestions = newWrongs; // 更新错题列表
    newWrongs = [];
    const total = roundTotal();
    finalScore.textContent = `${score} / ${total}`;

    // 有错题就显示"重做错题"按钮
    const redoBtn = document.getElementById("btn-redo-wrong");
    if (wrongQuestions.length) {
      redoBtn.textContent = `重做错题(${wrongQuestions.length} 题)`;
      redoBtn.classList.remove("hidden");
    } else {
      redoBtn.classList.add("hidden");
    }

    const msg =
      roundMode === "redo"
        ? (wrongQuestions.length === 0
          ? "错题全部做对,太棒了!🎉"
          : `错题重做完成,还有 ${wrongQuestions.length} 道没做对,再试一次!💪`)
        : score === total ? "太棒了,满分!你是句子小达人!🏆"
        : score / total >= 0.8 ? "很棒!继续保持!👍"
        : score / total >= 0.6 ? "不错,把错题重做一遍会更好!💪"
        : "别灰心,多读几遍句子,重做错题再挑战一次!📖";
    finalMessage.textContent = msg;

    // 选组测验做完一轮:成绩存进账号,该组标记为已完成
    if (roundMode === "group" && currentGroup > 0) {
      fetchJSON("/api/quiz/progress", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_no: currentGroup, score, total }),
      })
        .then(() => {
          quizProgress[currentGroup] = { score, total };
          delete quizDrafts[currentGroup];
          const chip = groupChips.querySelector(`.chip[data-group="${currentGroup}"]`);
          if (chip) {
            chip.classList.remove("partial");
            chip.classList.add("done");
          }
          // 做完一整组,顺手把草稿清掉(失败也不影响完成标记)
          fetchJSON(`/api/quiz/draft?group=${currentGroup}`, { method: "DELETE" }).catch(() => {});
        })
        .catch((err) => alert(`成绩保存失败:${err.message}`));
    }
  }

  loadGroups().catch((err) => alert(err.message));
}

/* ==================== 听力训练 ==================== */
// 听英文句子(不显示英文),从中文选项里选出正确意思,答完展示听力原文
const listeningBox = document.getElementById("listening-box");
if (listeningBox) {
  const TOTAL = 10; // "全部随机"一轮的题目数(选组/重做按本地列表长度)
  const startView = document.getElementById("listen-start");
  const questionView = document.getElementById("listen-question");
  const endView = document.getElementById("listen-end");
  const groupChips = document.getElementById("listen-group-chips");
  const listenIndex = document.getElementById("listen-index");
  const listenTotal = document.getElementById("listen-total");
  const listenScore = document.getElementById("listen-score");
  const listenGroupName = document.getElementById("listen-group-name");
  const listenOptions = document.getElementById("listen-options");
  const listenFeedback = document.getElementById("listen-feedback");
  const listenResult = document.getElementById("listen-result");
  const listenScript = document.getElementById("listen-script");
  const finalScore = document.getElementById("listen-final-score");
  const finalMessage = document.getElementById("listen-final-message");
  const roundHint = document.getElementById("listen-round-hint");

  let currentGroup = 0;      // 当前选题范围:0 = 全部随机,>0 = 第几组
  let currentGroupLabel = "全部随机";
  let roundMode = "group";   // 出题模式:"group" 按组出题 / "redo" 重做错题
  let roundQuestions = [];   // 本轮题目列表(选组/重做在本地,全部随机逐题向服务器要)
  let listenGroupSize = 50;  // 每组题数(从 /api/listening/groups 取)
  let listenProgress = {};   // 已完成的组:{组号: {score, total}}
  let wrongQuestions = [];   // 最近一轮答错的题
  let newWrongs = [];        // 本轮(含重做)又答错的题,供下一轮重做
  let current = 0;   // 当前是第几题
  let score = 0;     // 答对题数
  let currentQ = null; // 当前题目
  let answered = false;

  document.getElementById("btn-listen-start").addEventListener("click", () => startRound("group"));
  document.getElementById("btn-listen-next").addEventListener("click", nextQuestion);
  document.getElementById("btn-listen-restart").addEventListener("click", () => startRound(roundMode));
  document.getElementById("btn-listen-redo-wrong").addEventListener("click", () => startRound("redo"));
  document.getElementById("btn-listen-back-groups").addEventListener("click", backToGroups);
  document.getElementById("btn-listen-play").addEventListener("click", () => speak(currentQ?.english || "", 1.0));
  document.getElementById("btn-listen-replay").addEventListener("click", () => speak(currentQ?.english || "", 1.0));

  // 加载题库概况,生成"全部随机 + 第 1~20 组"选择按钮,已完成的组打 ✓
  async function loadGroups() {
    const s = await fetchJSON("/api/listening/groups");
    listenGroupSize = s.group_size;
    try {
      listenProgress = (await fetchJSON("/api/listening/progress")).records;
    } catch (err) {
      // 成绩加载失败(如会话过期跳登录页)不影响选题,忽略即可
    }
    const mk = (g, label) => {
      const btn = document.createElement("button");
      btn.className = "chip" + (g === currentGroup ? " active" : "") + (g > 0 && listenProgress[g] ? " done" : "");
      btn.textContent = label;
      btn.dataset.group = g;
      btn.addEventListener("click", () => {
        currentGroup = g;
        currentGroupLabel = label;
        groupChips.querySelectorAll(".chip").forEach((el) => el.classList.remove("active"));
        btn.classList.add("active");
        updateHint();
      });
      groupChips.appendChild(btn);
    };
    mk(0, "全部随机");
    for (let g = 1; g <= s.groups; g++) mk(g, `第 ${g} 组`);
    updateHint();
  }

  // 根据当前选中的范围更新提示文字
  function updateHint() {
    roundHint.textContent =
      currentGroup === 0
        ? "全部随机:随机抽 10 题,听音选意,答完展示原文。"
        : `第 ${currentGroup} 组:本组共 ${listenGroupSize} 题,听音选意,答完展示原文;完成后本组标记为 ✓ 已完成。`;
  }

  // 这一轮的题目总数:选组/重做按本地列表长度,全部随机固定 10 题
  function roundTotal() {
    return roundQuestions.length || TOTAL;
  }

  async function startRound(mode) {
    roundMode = mode;
    newWrongs = [];
    current = 0;
    score = 0;
    if (mode === "redo") {
      roundQuestions = [...wrongQuestions]; // 重做错题:题目在本地
    } else if (currentGroup > 0) {
      try {
        // 选组训练:一次取回这一整组,一轮做完
        const qs = await fetchJSON(`/api/listening/group-questions?group=${currentGroup}`);
        roundQuestions = qs.map((q) => ({ english: q.english, chinese: q.chinese, options: q.options }));
      } catch (err) {
        alert(err.message);
        return;
      }
    } else {
      roundQuestions = []; // 全部随机:每题向服务器现取
    }
    startView.classList.add("hidden");
    endView.classList.add("hidden");
    questionView.classList.remove("hidden");
    nextQuestion();
  }

  function backToGroups() {
    questionView.classList.add("hidden");
    endView.classList.add("hidden");
    startView.classList.remove("hidden");
  }

  async function nextQuestion() {
    current++;
    if (current > roundTotal()) return endRound();
    answered = false;
    listenIndex.textContent = current;
    listenTotal.textContent = roundTotal();
    listenScore.textContent = score;
    listenGroupName.textContent = roundMode === "redo" ? "错题重做" : currentGroupLabel;
    listenFeedback.classList.add("hidden");
    listenOptions.innerHTML = "";
    listenScript.innerHTML = "";

    try {
      if (roundQuestions.length) {
        // 选组/重做:题目在本地列表里
        currentQ = roundQuestions[current - 1];
      } else {
        const q = await fetchJSON(`/api/listening/question?group=${currentGroup}`);
        currentQ = { english: q.english, chinese: q.chinese, options: q.options };
      }
      // 只展示中文选项,英文等答完才作为听力原文展示
      currentQ.options.forEach((text) => {
        const btn = document.createElement("button");
        btn.className = "quiz-option";
        btn.textContent = text;
        btn.addEventListener("click", () => answer(text, btn));
        listenOptions.appendChild(btn);
      });
      speak(currentQ.english, 1.0); // 自动朗读句子(常速)
    } catch (err) {
      alert(err.message);
      questionView.classList.add("hidden");
      startView.classList.remove("hidden");
    }
  }

  function answer(text, btn) {
    if (answered) return; // 防止重复作答
    answered = true;
    listenOptions.querySelectorAll(".quiz-option").forEach((b) => (b.disabled = true));
    // 题目在本地(或带中文答案),直接判分
    const correctAnswer = currentQ.correct_answer ?? currentQ.chinese;
    if (text === correctAnswer) {
      btn.classList.add("correct");
      score++;
      listenScore.textContent = score;
      listenResult.textContent = "✓ 回答正确!";
      listenResult.className = "quiz-result good";
    } else {
      btn.classList.add("wrong");
      listenOptions.querySelectorAll(".quiz-option").forEach((b) => {
        if (b.textContent === correctAnswer) b.classList.add("correct");
      });
      listenResult.textContent = `✗ 回答错误,正确答案是:${correctAnswer}`;
      listenResult.className = "quiz-result bad";
      newWrongs.push(currentQ); // 记入错题,结束后可重做
    }
    showScript(); // 答完展示完整听力原文
    listenFeedback.classList.remove("hidden");
  }

  // 听力原文:英文句子 + 对照原文再听一遍
  function showScript() {
    const en = document.createElement("p");
    en.className = "listen-script-en";
    en.textContent = currentQ.english;
    listenScript.appendChild(en);
    const btn = document.createElement("button");
    btn.className = "btn btn-sm btn-outline";
    btn.textContent = "🔊 对照原文再听一遍";
    btn.addEventListener("click", () => speak(currentQ.english, 1.0));
    listenScript.appendChild(btn);
  }

  function endRound() {
    questionView.classList.add("hidden");
    endView.classList.remove("hidden");
    wrongQuestions = newWrongs; // 更新错题列表
    newWrongs = [];
    const total = roundTotal();
    finalScore.textContent = `${score} / ${total}`;

    // 有错题就显示"重做错题"按钮
    const redoBtn = document.getElementById("btn-listen-redo-wrong");
    if (wrongQuestions.length) {
      redoBtn.textContent = `重做错题(${wrongQuestions.length} 题)`;
      redoBtn.classList.remove("hidden");
    } else {
      redoBtn.classList.add("hidden");
    }

    const msg =
      roundMode === "redo"
        ? (wrongQuestions.length === 0
          ? "错题全部做对,太棒了!🎉"
          : `错题重做完成,还有 ${wrongQuestions.length} 道没做对,再试一次!💪`)
        : score === total ? "太棒了,满分!你的听力真厉害!🏆"
        : score / total >= 0.8 ? "很棒!继续保持!👍"
        : score / total >= 0.6 ? "不错,把错题重做一遍会更好!💪"
        : "别灰心,多听几遍原文,重做错题再挑战一次!📖";
    finalMessage.textContent = msg;

    // 选组训练做完一轮:成绩存进账号,该组标记为已完成
    if (roundMode === "group" && currentGroup > 0) {
      fetchJSON("/api/listening/progress", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_no: currentGroup, score, total }),
      })
        .then(() => {
          listenProgress[currentGroup] = { score, total };
          groupChips.querySelector(`.chip[data-group="${currentGroup}"]`)?.classList.add("done");
        })
        .catch((err) => alert(`成绩保存失败:${err.message}`));
    }
  }

  loadGroups().catch((err) => alert(err.message));
}

/* ==================== 单词任务(多词库) ==================== */
// 进度读写函数 loadProgress / saveProgress 在文件顶部(服务器存储,按账号隔离),和单词学习页共享

// 任务总览页
const taskGroupGrid = document.getElementById("task-group-grid");
if (taskGroupGrid) {
  const dictTabs = document.getElementById("task-dict-tabs");
  const totalNum = document.getElementById("task-overview-num");
  const totalFill = document.getElementById("task-overview-fill");
  const totalEl = document.getElementById("task-total");
  const groupsEl = document.getElementById("task-groups");
  const groupSizeEl = document.getElementById("task-group-size");

  // 当前词库:从地址栏 ?dict= 读取,默认高考
  let currentDict = new URLSearchParams(location.search).get("dict") || "gaokao";

  // 加载词库列表,生成切换按钮
  async function loadDictionaries() {
    const dicts = await fetchJSON("/api/tasks/dictionaries");
    if (!dicts.some((d) => d.key === currentDict)) currentDict = dicts[0].key;

    dictTabs.innerHTML = "";
    dicts.forEach((d) => {
      const btn = document.createElement("button");
      btn.className = "chip" + (d.key === currentDict ? " active" : "");
      btn.textContent = `${d.label}(${d.total}词)`;
      btn.addEventListener("click", () => {
        currentDict = d.key;
        // 更新地址栏(不刷新页面),刷新后还能回到这个词库
        const u = new URL(location.href);
        u.searchParams.set("dict", d.key);
        history.replaceState(null, "", u);
        dictTabs.querySelectorAll(".chip").forEach((el) => el.classList.remove("active"));
        btn.classList.add("active");
        loadOverview();
      });
      dictTabs.appendChild(btn);
    });
    loadOverview();
  }

  async function loadOverview() {
    const s = await fetchJSON(`/api/tasks/summary?dict_key=${currentDict}`);
    const mastered = await loadProgress(currentDict);

    totalEl.textContent = s.total;
    groupsEl.textContent = s.groups;
    groupSizeEl.textContent = s.group_size;
    totalNum.textContent = `${mastered.size} / ${s.total}`;
    totalFill.style.width = ((mastered.size / s.total) * 100).toFixed(1) + "%";

    // 一次遍历统计每组已掌握的数量
    const counts = {};
    for (const idx of mastered) {
      const g = Math.floor(idx / s.group_size) + 1;
      counts[g] = (counts[g] || 0) + 1;
    }

    taskGroupGrid.innerHTML = "";
    for (let g = 1; g <= s.groups; g++) {
      const doneCount = counts[g] || 0;
      const size = g === s.groups ? s.total - (g - 1) * s.group_size : s.group_size;
      const card = document.createElement("a");
      // 三色:白=没学过 / 黄=学了一部分 / 绿=全部学完
      card.className = "task-group-card" + (doneCount === size ? " done" : doneCount > 0 ? " partial" : "");
      card.href = `/tasks/${currentDict}/${g}`;
      card.innerHTML = `
        <div class="task-group-name">第 ${g} 组</div>
        <div class="task-group-progress">已掌握 ${doneCount} / ${size}</div>`;
      taskGroupGrid.appendChild(card);
    }
  }
  loadDictionaries().catch((err) => alert(err.message));
}

// 某本词库某一组的学习页(路径格式:/tasks/{词库}/{组号})
const taskCard = document.getElementById("task-card");
if (taskCard) {
  const segments = location.pathname.split("/").filter(Boolean); // ["tasks", 词库, 组号]
  const dictKey = segments[1] || "gaokao";
  const groupNo = parseInt(segments[2], 10);
  const doneEl = document.getElementById("task-group-done");
  const totalEl = document.getElementById("task-group-total");
  const fillEl = document.getElementById("task-group-fill");
  const enEl = document.getElementById("task-en");
  const phoneticEl = document.getElementById("task-phonetic");
  const cnEl = document.getElementById("task-cn");
  const btnPrev = document.getElementById("task-prev");
  const btnNext = document.getElementById("task-next");
  const btnMaster = document.getElementById("task-master");
  const btnReset = document.getElementById("task-reset");
  const btnReview = document.getElementById("task-review");
  const btnPrevGroup = document.getElementById("task-prev-group");
  const btnNextGroup = document.getElementById("task-next-group");
  const groupPosEl = document.getElementById("task-group-pos");
  const doneText = document.getElementById("task-done-text");
  const doneNext = document.getElementById("task-done-next");
  const controls = document.getElementById("task-controls");
  const doneBox = document.getElementById("task-done");

  let words = [];
  let index = 0;
  let totalGroups = groupNo; // 词库总组数,拿到数据后更新
  let reviewMode = false; // 复习模式:进入时本组已全部掌握,浏览卡片不影响进度
  let mastered = new Set(); // 已掌握的编号集合,loadProgress 完成后填充

  // 朗读按钮(stopPropagation 防止点按钮时卡片跟着翻面)
  document.getElementById("task-sound-front").addEventListener("click", (e) => {
    e.stopPropagation(); speak(words[index]?.english || "");
  });
  document.getElementById("task-sound-back").addEventListener("click", (e) => {
    e.stopPropagation(); speak(words[index]?.english || "");
  });

  async function load() {
    try {
      mastered = await loadProgress(dictKey); // 先从账号里读取进度,再判断是否进入复习模式
      const data = await fetchJSON(`/api/tasks/words?dict_key=${dictKey}&group=${groupNo}`);
      words = data.words;
      totalGroups = data.groups;
      totalEl.textContent = words.length;
      reviewMode = doneCount() === words.length; // 进组时已全部掌握 → 直接进入复习模式
      setupGroupNav();
      render();
    } catch (err) {
      alert(err.message);
      location.href = `/tasks?dict=${dictKey}`;
    }
  }

  // 组间导航:没学完也能去上一组/下一组,进度互不影响
  function setupGroupNav() {
    groupPosEl.textContent = `第 ${groupNo} / ${totalGroups} 组`;
    btnPrevGroup.disabled = groupNo <= 1;
    btnNextGroup.disabled = groupNo >= totalGroups;
    if (groupNo > 1) btnPrevGroup.onclick = () => { location.href = `/tasks/${dictKey}/${groupNo - 1}`; };
    if (groupNo < totalGroups) {
      btnNextGroup.onclick = () => { location.href = `/tasks/${dictKey}/${groupNo + 1}`; };
      doneNext.href = `/tasks/${dictKey}/${groupNo + 1}`;
      doneNext.textContent = "下一组 →";
    } else {
      // 最后一组:学完框里的按钮改为返回任务列表
      doneNext.href = `/tasks?dict=${dictKey}`;
      doneNext.textContent = "返回任务列表";
    }
  }

  // 本组已掌握的数量
  function doneCount() {
    return words.filter((w) => mastered.has(w.index)).length;
  }

  function render() {
    const w = words[index];
    if (!w) return;
    taskCard.classList.remove("flipped");
    enEl.textContent = w.english;
    phoneticEl.textContent = w.phonetic || "";
    cnEl.textContent = w.chinese;

    const done = doneCount();
    doneEl.textContent = done;
    fillEl.style.width = ((done / words.length) * 100).toFixed(1) + "%";

    if (reviewMode) {
      // 复习模式:只能浏览,不提供"取消标记",已学完的进度不受影响
      btnMaster.disabled = true;
      btnMaster.classList.remove("task-master-marked");
      btnMaster.textContent = "🔁 复习模式 · 不影响进度";
    } else {
      btnMaster.disabled = false;
      btnMaster.textContent = mastered.has(w.index) ? "↩ 取消标记" : "✓ 标记已掌握";
      btnMaster.classList.toggle("task-master-marked", mastered.has(w.index));
    }

    if (reviewMode) {
      // 复习模式:卡片照常浏览,底部显示复习横幅
      controls.classList.remove("hidden");
      taskCard.classList.remove("hidden");
      doneBox.classList.remove("hidden");
      doneText.textContent = "🔁 复习模式:本组已全部掌握,浏览卡片不影响学习进度";
      btnReview.classList.add("hidden");
    } else if (done === words.length) {
      // 刚学完:显示完成框,可以复习本组或去下一组
      controls.classList.add("hidden");
      taskCard.classList.add("hidden");
      doneBox.classList.remove("hidden");
      doneText.textContent = "🎉 本组单词已全部掌握!";
      btnReview.classList.remove("hidden");
    } else {
      controls.classList.remove("hidden");
      taskCard.classList.remove("hidden");
      doneBox.classList.add("hidden");
    }
  }

  taskCard.addEventListener("click", () => taskCard.classList.toggle("flipped"));
  btnPrev.addEventListener("click", () => { index = (index - 1 + words.length) % words.length; render(); });
  btnNext.addEventListener("click", () => { index = (index + 1) % words.length; render(); });

  // 学完后点"复习本组":进入复习模式浏览卡片
  btnReview.addEventListener("click", () => {
    reviewMode = true;
    index = 0;
    render();
  });

  // 标记已掌握:标记后自动跳到下一个;再点一次取消标记
  btnMaster.addEventListener("click", () => {
    if (reviewMode) return;
    const w = words[index];
    if (!w) return;
    if (mastered.has(w.index)) {
      mastered.delete(w.index);
      saveProgress(dictKey, mastered);
      render();
    } else {
      mastered.add(w.index);
      saveProgress(dictKey, mastered);
      index = (index + 1) % words.length;
      render();
    }
  });

  btnReset.addEventListener("click", () => {
    if (!confirm("确定要清除本组的学习记录吗?")) return;
    for (const w of words) mastered.delete(w.index);
    saveProgress(dictKey, mastered);
    reviewMode = false; // 清除记录后回到普通学习模式
    render();
  });

  // 键盘操作:← → 切换,空格翻面
  document.addEventListener("keydown", (e) => {
    if (!words.length) return;
    if (e.key === "ArrowLeft") { index = (index - 1 + words.length) % words.length; render(); }
    if (e.key === "ArrowRight") { index = (index + 1) % words.length; render(); }
    if (e.key === " ") { e.preventDefault(); taskCard.classList.toggle("flipped"); }
  });

  load();
}
