// 后台管理交互:单词管理、课程管理的增删改查

// 通用请求封装:未登录自动跳转登录页
async function apiFetch(url, options = {}) {
  const res = await fetch(url, options);
  if (res.status === 401) {
    location.href = "/admin/login";
    throw new Error("请先登录");
  }
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "请求失败");
  }
  if (res.status === 204) return null;
  return res.json();
}

// 防止表格里的文字被当作 HTML 执行(转义特殊字符)
function escapeHtml(text) {
  const map = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  return String(text ?? "").replace(/[&<>"']/g, (c) => map[c]);
}

/* ==================== 单词管理 ==================== */
const wordTbody = document.getElementById("word-tbody");
if (wordTbody) {
  const searchInput = document.getElementById("search-input");
  const categoryFilter = document.getElementById("category-filter");
  const btnAdd = document.getElementById("btn-add");
  const dialog = document.getElementById("word-dialog");
  const form = document.getElementById("word-form");
  const dialogTitle = document.getElementById("dialog-title");
  const idInput = document.getElementById("word-id");

  let timer = null;

  // 加载单词列表(支持搜索和分类筛选)
  async function loadWords() {
    const params = new URLSearchParams();
    const search = searchInput.value.trim();
    const category = categoryFilter.value;
    if (search) params.set("search", search);
    if (category && category !== "全部") params.set("category", category);

    wordTbody.innerHTML = '<tr><td colspan="6" class="empty-tip">加载中…</td></tr>';
    try {
      const words = await apiFetch("/admin/api/words?" + params);
      if (!words.length) {
        wordTbody.innerHTML = '<tr><td colspan="6" class="empty-tip">没有找到单词</td></tr>';
        return;
      }
      wordTbody.innerHTML = words.map((w) => `
        <tr>
          <td>${w.id}</td>
          <td><strong>${escapeHtml(w.english)}</strong></td>
          <td>${escapeHtml(w.chinese)}</td>
          <td>${escapeHtml(w.phonetic)}</td>
          <td><span class="badge">${escapeHtml(w.category)}</span></td>
          <td>
            <button class="btn btn-small btn-outline" onclick="editWord(${w.id})">编辑</button>
            <button class="btn btn-small btn-danger" onclick="deleteWord(${w.id})">删除</button>
          </td>
        </tr>`).join("");
    } catch (err) {
      alert(err.message);
    }
  }

  // 打开添加/编辑对话框
  window.editWord = async function (id = null) {
    form.reset();
    idInput.value = id ?? "";
    dialogTitle.textContent = id ? "编辑单词" : "添加单词";
    if (id) {
      const words = await apiFetch("/admin/api/words");
      const w = words.find((x) => x.id === id);
      if (w) {
        form.elements.english.value = w.english;
        form.elements.chinese.value = w.chinese;
        form.elements.phonetic.value = w.phonetic;
        form.elements.category.value = w.category;
        form.elements.example.value = w.example;
        form.elements.example_cn.value = w.example_cn;
      }
    }
    dialog.showModal();
  };

  window.deleteWord = async function (id) {
    if (!confirm("确定要删除这个单词吗?")) return;
    try {
      await apiFetch("/admin/api/words/" + id, { method: "DELETE" });
      loadWords();
    } catch (err) { alert(err.message); }
  };

  // 提交表单:添加或更新
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    delete data.id;
    const id = idInput.value;
    try {
      await apiFetch(id ? `/admin/api/words/${id}` : "/admin/api/words", {
        method: id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      dialog.close();
      refreshCategories();
      loadWords();
    } catch (err) { alert(err.message); }
  });

  document.getElementById("btn-cancel").addEventListener("click", () => dialog.close());

  // 输入防抖:停止输入 300 毫秒后再搜索
  searchInput.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(loadWords, 300);
  });
  categoryFilter.addEventListener("change", loadWords);
  btnAdd.addEventListener("click", () => editWord());

  // 更新分类下拉框(添加了带新分类的单词后)
  async function refreshCategories() {
    const categories = await apiFetch("/api/categories");
    categoryFilter.innerHTML = '<option value="全部">全部分类</option>' +
      categories.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
  }

  loadWords();
}

/* ==================== 课程管理 ==================== */
const lessonTbody = document.getElementById("lesson-tbody");
if (lessonTbody) {
  const btnAdd = document.getElementById("btn-add");
  const dialog = document.getElementById("lesson-dialog");
  const form = document.getElementById("lesson-form");
  const dialogTitle = document.getElementById("lesson-dialog-title");
  const idInput = document.getElementById("lesson-id");

  // 加载课程列表
  async function loadLessons() {
    lessonTbody.innerHTML = '<tr><td colspan="4" class="empty-tip">加载中…</td></tr>';
    try {
      const lessons = await apiFetch("/admin/api/lessons");
      if (!lessons.length) {
        lessonTbody.innerHTML = '<tr><td colspan="4" class="empty-tip">还没有课程,点击右上角"添加课程"</td></tr>';
        return;
      }
      lessonTbody.innerHTML = lessons.map((l) => `
        <tr>
          <td>${l.id}</td>
          <td><strong>${escapeHtml(l.title)}</strong></td>
          <td class="cell-ellipsis">${escapeHtml(l.summary)}</td>
          <td>
            <button class="btn btn-small btn-outline" onclick="editLesson(${l.id})">编辑</button>
            <button class="btn btn-small btn-danger" onclick="deleteLesson(${l.id})">删除</button>
          </td>
        </tr>`).join("");
    } catch (err) {
      alert(err.message);
    }
  }

  // 打开添加/编辑对话框
  window.editLesson = async function (id = null) {
    form.reset();
    idInput.value = id ?? "";
    dialogTitle.textContent = id ? "编辑课程" : "添加课程";
    if (id) {
      const lessons = await apiFetch("/admin/api/lessons");
      const l = lessons.find((x) => x.id === id);
      if (l) {
        form.elements.title.value = l.title;
        form.elements.summary.value = l.summary;
        form.elements.content.value = l.content;
        form.elements.content_cn.value = l.content_cn;
      }
    }
    dialog.showModal();
  };

  window.deleteLesson = async function (id) {
    if (!confirm("确定要删除这个课程吗?")) return;
    try {
      await apiFetch("/admin/api/lessons/" + id, { method: "DELETE" });
      loadLessons();
    } catch (err) { alert(err.message); }
  };

  // 提交表单:添加或更新
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    delete data.id;
    const id = idInput.value;
    try {
      await apiFetch(id ? `/admin/api/lessons/${id}` : "/admin/api/lessons", {
        method: id ? "PUT" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      dialog.close();
      loadLessons();
    } catch (err) { alert(err.message); }
  });

  document.getElementById("btn-cancel").addEventListener("click", () => dialog.close());
  btnAdd.addEventListener("click", () => editLesson());
  loadLessons();
}

/* ==================== 用户管理 ==================== */
const userTbody = document.getElementById("user-tbody");
if (userTbody) {
  // 时间格式化:没有登录过显示"从未登录"
  function fmtTime(iso) {
    if (!iso) return "从未登录";
    return new Date(iso).toLocaleString("zh-CN", { hour12: false });
  }

  // 加载用户列表
  async function loadUsers() {
    userTbody.innerHTML = '<tr><td colspan="7" class="empty-tip">加载中…</td></tr>';
    try {
      const users = await apiFetch("/admin/api/users");
      if (!users.length) {
        userTbody.innerHTML = '<tr><td colspan="7" class="empty-tip">还没有注册用户</td></tr>';
        return;
      }
      userTbody.innerHTML = users.map((u) => `
        <tr>
          <td>${u.id}</td>
          <td><strong>${escapeHtml(u.username)}</strong></td>
          <td>${fmtTime(u.created_at)}</td>
          <td>${fmtTime(u.last_login)}</td>
          <td>${u.mastered_count}</td>
          <td>${u.is_active
            ? '<span class="badge">正常</span>'
            : '<span class="badge off">已禁用</span>'}</td>
          <td>
            <button class="btn btn-small btn-outline" onclick="toggleUser(${u.id}, ${u.is_active})">
              ${u.is_active ? "禁用" : "启用"}
            </button>
            <button class="btn btn-small btn-outline" onclick="resetUserPassword(${u.id}, '${escapeHtml(u.username)}')">重置密码</button>
            <button class="btn btn-small btn-danger" onclick="deleteUser(${u.id}, '${escapeHtml(u.username)}')">删除</button>
          </td>
        </tr>`).join("");
    } catch (err) {
      alert(err.message);
    }
  }

  // 禁用/启用账号
  window.toggleUser = async function (id, isActive) {
    const tip = isActive
      ? "确定要禁用这个账号吗?禁用后该用户会被立即退出,且无法登录。"
      : "确定要恢复启用这个账号吗?";
    if (!confirm(tip)) return;
    try {
      await apiFetch(`/admin/api/users/${id}/toggle-active`, { method: "POST" });
      loadUsers();
    } catch (err) { alert(err.message); }
  };

  // 重置密码
  window.resetUserPassword = async function (id, username) {
    const p = prompt(`请输入「${username}」的新密码(至少 6 位):`);
    if (p === null) return;
    if (p.length < 6) { alert("密码至少需要 6 位"); return; }
    try {
      await apiFetch(`/admin/api/users/${id}/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: p }),
      });
      alert("密码已重置");
    } catch (err) { alert(err.message); }
  };

  // 删除用户
  window.deleteUser = async function (id, username) {
    if (!confirm(`确定要删除用户「${username}」吗?他/她的学习进度也会一起删除!`)) return;
    try {
      await apiFetch(`/admin/api/users/${id}`, { method: "DELETE" });
      loadUsers();
    } catch (err) { alert(err.message); }
  };

  loadUsers();
}
