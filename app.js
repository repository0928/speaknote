/**
 * SpeakNote — app.js
 * 語音筆記 Widget
 * 使用 Web Speech API + localStorage
 */

'use strict';

// =====================================================
// 狀態
// =====================================================
const STORAGE_KEY = 'speaknote_notes';

let notes = [];          // { id, title, content, createdAt, updatedAt }
let activeNoteId = null; // 目前開啟的筆記 id
let recognition = null;  // SpeechRecognition 實例
let isRecording = false;
let interimBuffer = '';  // 錄音中尚未確定的文字

// =====================================================
// DOM 取得
// =====================================================
const $ = id => document.getElementById(id);

const elNoteList     = $('note-list');
const elNoteCount    = $('note-count');
const elEditor       = $('editor');
const elEditorWrap   = $('editor-wrap');
const elEmptyState   = $('empty-state');
const elNoteTitleDisplay = $('note-title-display');
const elNoteDateDisplay  = $('note-date-display');
const elBtnRecord    = $('btn-record');
const elRecordLabel  = $('record-label');
const elRecordStatus = $('record-status');
const elInterimText  = $('interim-text');
const elBtnNewNote   = $('btn-new-note');
const elBtnCopy      = $('btn-copy');
const elBtnExport    = $('btn-export');
const elBtnDelete    = $('btn-delete');
const elSidebarToggle = $('sidebar-toggle');
const elSidebar      = $('sidebar');
const elLangSelect   = $('lang-select');
const elToast        = $('toast');
const elBtnUpload    = $('btn-upload');
const elFileInput    = $('file-input');

// =====================================================
// 工具函式
// =====================================================

/** 產生唯一 id */
function genId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
}

/** 格式化日期 */
function formatDate(ts) {
  const d = new Date(ts);
  const pad = n => String(n).padStart(2, '0');
  return `${d.getFullYear()}/${pad(d.getMonth()+1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** 短日期（側邊欄用） */
function formatDateShort(ts) {
  const d = new Date(ts);
  const now = new Date();
  const isToday = d.toDateString() === now.toDateString();
  const pad = n => String(n).padStart(2, '0');
  if (isToday) return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  return `${pad(d.getMonth()+1)}/${pad(d.getDate())}`;
}

/** Toast 通知 */
let toastTimer = null;
function showToast(msg) {
  elToast.textContent = msg;
  elToast.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => elToast.classList.remove('show'), 2200);
}

/** 從內容推導標題（取第一行非空文字，最多 24 字） */
function titleFromContent(content) {
  if (!content || !content.trim()) return '（空白筆記）';
  const first = content.trim().split('\n').find(l => l.trim());
  return first ? first.trim().slice(0, 24) || '（空白筆記）' : '（空白筆記）';
}

// =====================================================
// localStorage
// =====================================================
function loadNotes() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    notes = raw ? JSON.parse(raw) : [];
  } catch {
    notes = [];
  }
}

function saveNotes() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(notes));
}

// =====================================================
// 筆記 CRUD
// =====================================================

/** 建立新筆記並切換過去 */
function createNote(initialContent = '') {
  const now = Date.now();
  const note = {
    id:        genId(),
    title:     titleFromContent(initialContent),
    content:   initialContent,
    createdAt: now,
    updatedAt: now,
  };
  notes.unshift(note);
  saveNotes();
  renderNoteList();
  openNote(note.id);
  return note;
}

/** 開啟（選取）筆記 */
function openNote(id) {
  activeNoteId = id;
  const note = notes.find(n => n.id === id);
  if (!note) return;

  // 編輯器
  elEditor.value = note.content;
  elEmptyState.classList.add('hidden');
  elEditor.classList.remove('hidden');

  // 工具列
  elNoteTitleDisplay.textContent = note.title || '（空白筆記）';
  elNoteDateDisplay.textContent  = formatDate(note.updatedAt);
  elBtnCopy.disabled   = false;
  elBtnExport.disabled = false;
  elBtnDelete.disabled = false;

  // 側邊欄高亮
  document.querySelectorAll('.note-item').forEach(el => {
    el.classList.toggle('active', el.dataset.id === id);
  });

  // 行動裝置：選筆記後自動收起側邊欄
  if (window.innerWidth <= 600) {
    elSidebar.classList.add('collapsed');
  }
}

/** 更新目前開啟筆記的內容 */
function updateActiveNote(content) {
  if (!activeNoteId) return;
  const note = notes.find(n => n.id === activeNoteId);
  if (!note) return;
  note.content   = content;
  note.title     = titleFromContent(content);
  note.updatedAt = Date.now();
  saveNotes();
  // 更新工具列標題
  elNoteTitleDisplay.textContent = note.title;
  elNoteDateDisplay.textContent  = formatDate(note.updatedAt);
  // 更新列表對應項目
  const item = elNoteList.querySelector(`.note-item[data-id="${activeNoteId}"]`);
  if (item) {
    item.querySelector('.note-item-title').textContent   = note.title;
    item.querySelector('.note-item-preview').textContent = note.content.replace(/\n/g, ' ').slice(0, 60) || '（空白）';
    item.querySelector('.note-item-date').textContent    = formatDateShort(note.updatedAt);
  }
}

/** 刪除筆記 */
function deleteNote(id) {
  if (!confirm('確定要刪除這則筆記嗎？')) return;
  notes = notes.filter(n => n.id !== id);
  saveNotes();
  if (activeNoteId === id) {
    activeNoteId = null;
    elEditor.value = '';
    elEditor.classList.add('hidden');
    elEmptyState.classList.remove('hidden');
    elNoteTitleDisplay.textContent = '—';
    elNoteDateDisplay.textContent  = '';
    elBtnCopy.disabled   = true;
    elBtnExport.disabled = true;
    elBtnDelete.disabled = true;
  }
  renderNoteList();
  showToast('筆記已刪除');
}

// =====================================================
// 渲染筆記列表
// =====================================================
function renderNoteList() {
  elNoteList.innerHTML = '';
  if (notes.length === 0) {
    elNoteList.innerHTML = '<p style="padding:16px 10px;font-size:12px;color:var(--text-muted);text-align:center;">還沒有筆記</p>';
    elNoteCount.textContent = '0 則筆記';
    return;
  }

  notes.forEach(note => {
    const item = document.createElement('div');
    item.className = 'note-item' + (note.id === activeNoteId ? ' active' : '');
    item.dataset.id = note.id;
    item.innerHTML = `
      <div class="note-item-title">${escHtml(note.title || '（空白筆記）')}</div>
      <div class="note-item-preview">${escHtml((note.content || '（空白）').replace(/\n/g, ' ').slice(0, 60))}</div>
      <div class="note-item-date">${formatDateShort(note.updatedAt)}</div>
    `;
    item.addEventListener('click', () => openNote(note.id));
    elNoteList.appendChild(item);
  });

  elNoteCount.textContent = `${notes.length} 則筆記`;
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// =====================================================
// Web Speech API
// =====================================================

/** 檢查瀏覽器是否支援 */
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

function initRecognition() {
  if (!SpeechRecognition) return null;

  const r = new SpeechRecognition();
  r.continuous      = true;
  r.interimResults  = true;
  r.lang            = elLangSelect.value;

  r.onstart = () => {
    isRecording = true;
    elBtnRecord.classList.add('recording');
    elRecordLabel.textContent = '停止錄音';
    elRecordStatus.textContent = '🔴 錄音中…';
  };

  r.onend = () => {
    // 若不是手動停止（例如因靜音自動停止），自動重啟
    if (isRecording) {
      try { r.start(); } catch {}
    }
  };

  r.onerror = e => {
    if (e.error === 'no-speech') return; // 靜音忽略
    if (e.error === 'aborted')  return;
    showToast(`語音辨識錯誤：${e.error}`);
    stopRecording();
  };

  r.onresult = e => {
    let interim = '';
    let newFinal = '';

    for (let i = e.resultIndex; i < e.results.length; i++) {
      const result = e.results[i];
      if (result.isFinal) {
        newFinal += result[0].transcript;
      } else {
        interim += result[0].transcript;
      }
    }

    // 即時預覽
    elInterimText.textContent = interim;

    if (newFinal) {
      // 將確定文字插入筆記
      appendTranscript(newFinal);
    }
  };

  return r;
}

/** 將轉錄文字附加到筆記 */
function appendTranscript(text) {
  const trimmed = text.trim();
  if (!trimmed) return;

  if (!activeNoteId) {
    // 若無開啟的筆記，建立新筆記
    createNote(trimmed);
  } else {
    const current = elEditor.value;
    const newContent = current
      ? current + (current.endsWith('\n') ? '' : '\n') + trimmed
      : trimmed;
    elEditor.value = newContent;
    updateActiveNote(newContent);
    // 捲動到底
    elEditor.scrollTop = elEditor.scrollHeight;
  }
}

/** 開始錄音 */
function startRecording() {
  if (!SpeechRecognition) {
    showToast('你的瀏覽器不支援語音辨識（請使用 Chrome）');
    return;
  }

  // 若無開啟筆記，先建立一則（空白，等待錄音填入）
  if (!activeNoteId) {
    createNote('');
  }

  recognition = initRecognition();
  if (!recognition) return;

  isRecording = true;
  try {
    recognition.start();
  } catch (err) {
    showToast('無法啟動麥克風：' + err.message);
    isRecording = false;
  }
}

/** 停止錄音 */
function stopRecording() {
  isRecording = false;
  elInterimText.textContent = '';
  elBtnRecord.classList.remove('recording');
  elRecordLabel.textContent  = '開始錄音';
  elRecordStatus.textContent = '';
  if (recognition) {
    try { recognition.stop(); } catch {}
    recognition = null;
  }
}

// =====================================================
// 匯出 / 複製
// =====================================================

function copyNote() {
  const note = notes.find(n => n.id === activeNoteId);
  if (!note) return;
  navigator.clipboard.writeText(note.content)
    .then(() => showToast('已複製到剪貼簿'))
    .catch(() => {
      // fallback
      elEditor.select();
      document.execCommand('copy');
      showToast('已複製到剪貼簿');
    });
}

function exportNote() {
  const note = notes.find(n => n.id === activeNoteId);
  if (!note) return;
  const blob = new Blob([note.content], { type: 'text/plain;charset=utf-8' });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement('a');
  const safe = note.title.replace(/[\\/:*?"<>|]/g, '_').slice(0, 40) || 'speaknote';
  a.href     = url;
  a.download = `${safe}.txt`;
  a.click();
  URL.revokeObjectURL(url);
  showToast('筆記已下載');
}

// =====================================================
// 事件綁定
// =====================================================

// 錄音按鈕
elBtnRecord.addEventListener('click', () => {
  if (isRecording) {
    stopRecording();
    showToast('錄音結束');
  } else {
    startRecording();
  }
});

// 語言切換（重新建立 recognition）
elLangSelect.addEventListener('change', () => {
  if (isRecording) {
    stopRecording();
    setTimeout(startRecording, 200);
  }
});

// 新增空白筆記
elBtnNewNote.addEventListener('click', () => {
  createNote('');
  elEditor.focus();
});

// 編輯器輸入 → 自動儲存（debounce 600ms）
let saveTimer = null;
elEditor.addEventListener('input', () => {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => updateActiveNote(elEditor.value), 600);
});

// 複製
elBtnCopy.addEventListener('click', copyNote);

// 下載
elBtnExport.addEventListener('click', exportNote);

// 刪除
elBtnDelete.addEventListener('click', () => deleteNote(activeNoteId));

// 側邊欄切換
elSidebarToggle.addEventListener('click', () => {
  elSidebar.classList.toggle('collapsed');
});

// 上傳音檔按鈕 → 觸發 file input
elBtnUpload.addEventListener('click', () => {
  if (!elBtnUpload.disabled) elFileInput.click();
});

// 選取檔案後送出
elFileInput.addEventListener('change', () => {
  const file = elFileInput.files[0];
  if (file) handleFileUpload(file);
});

// =====================================================
// 音檔上傳 → Whisper 轉錄
// =====================================================

/** 上傳音檔到後端 /api/transcribe，回傳文字 */
async function transcribeFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch('/api/transcribe', {
    method: 'POST',
    body: formData,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '伺服器錯誤' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  return await res.json(); // { text, language, duration }
}

/** 呼叫後端 /api/summarize，取得 AI 摘要 */
async function summarizeText(text) {
  const res = await fetch('/api/summarize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '摘要失敗' }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  const data = await res.json();
  return data.summary;
}

/** 處理使用者選取的音檔 */
async function handleFileUpload(file) {
  if (!file) return;

  const baseName = file.name.replace(/\.[^.]+$/, '');

  // UI：進入 loading 狀態
  elBtnUpload.classList.add('loading');
  elBtnUpload.disabled = true;
  elInterimText.textContent = '';

  try {
    // ── 步驟 1：語音轉文字 ──
    elRecordStatus.textContent = `⏳ 辨識中：${file.name}`;
    const { text, language, duration } = await transcribeFile(file);

    if (!text || !text.trim()) {
      showToast('未辨識到任何語音內容');
      return;
    }

    // 建立「原始轉錄」筆記
    const transcriptHeader = `📝 ${baseName}（轉錄）\n${'─'.repeat(24)}\n`;
    createNote(transcriptHeader + text.trim());
    showToast(`✅ 辨識完成（${language}，${duration} 秒）`);

    // ── 步驟 2：AI 摘要 ──
    elRecordStatus.textContent = '✨ AI 摘要產生中…';
    const summary = await summarizeText(text.trim());

    // 建立「AI 摘要」筆記
    const summaryHeader = `✨ ${baseName}（摘要）\n${'─'.repeat(24)}\n`;
    createNote(summaryHeader + summary);
    showToast('✨ AI 摘要完成！');

  } catch (err) {
    showToast(`❌ ${err.message}`);
    console.error('handleFileUpload error:', err);
  } finally {
    elBtnUpload.classList.remove('loading');
    elBtnUpload.disabled = false;
    elRecordStatus.textContent = '';
    elFileInput.value = '';
  }
}

// =====================================================
// 初始化
// =====================================================
function init() {
  loadNotes();
  renderNoteList();

  // 若有筆記，自動開啟最新一則
  if (notes.length > 0) {
    openNote(notes[0].id);
  }

  // 不支援語音辨識時提示
  if (!SpeechRecognition) {
    elRecordStatus.textContent = '⚠️ 此瀏覽器不支援語音辨識';
    elBtnRecord.disabled = true;
    elBtnRecord.style.opacity = '0.5';
  }
}

init();
