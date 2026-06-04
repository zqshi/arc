/**
 * Prototype Inspector — 注入到原型 iframe 中的元素选中脚本。
 *
 * 功能：
 * - Inspect 模式：hover 高亮 + click 选中
 * - 选中后通过 postMessage 上报元素信息
 * - 支持 apply 修改（接收 postMessage 替换元素 HTML）
 * - Undo 能力（保存修改前快照）
 */

// 生成注入到 iframe srcDoc 中的 inspector 脚本
export function buildInspectorScript(): string {
  return `<script>
(function() {
  var inspectMode = false;
  var selectedEl = null;
  var hoverEl = null;
  var undoStack = [];

  // 样式注入
  var style = document.createElement('style');
  style.textContent = \`
    .__arc-hover { outline: 2px dashed rgba(99,102,241,0.6) !important; outline-offset: 2px; cursor: crosshair !important; }
    .__arc-selected { outline: 2px solid #6366f1 !important; outline-offset: 2px; box-shadow: 0 0 0 4px rgba(99,102,241,0.15) !important; }
  \`;
  document.head.appendChild(style);

  // 生成 CSS selector
  function getSelector(el) {
    if (el.id) return '#' + el.id;
    var path = [];
    while (el && el !== document.body) {
      var tag = el.tagName.toLowerCase();
      if (el.className && typeof el.className === 'string') {
        var cls = el.className.trim().split(/\\s+/).filter(function(c) { return !c.startsWith('__arc-'); }).slice(0, 2).join('.');
        if (cls) tag += '.' + cls;
      }
      path.unshift(tag);
      el = el.parentElement;
    }
    return path.join(' > ');
  }

  // 获取元素信息
  function getElementInfo(el) {
    var computed = window.getComputedStyle(el);
    return {
      selector: getSelector(el),
      tagName: el.tagName.toLowerCase(),
      text: (el.textContent || '').trim().slice(0, 200),
      html: el.outerHTML.slice(0, 500),
      attributes: Array.from(el.attributes).reduce(function(acc, a) { acc[a.name] = a.value; return acc; }, {}),
      styles: {
        color: computed.color,
        backgroundColor: computed.backgroundColor,
        fontSize: computed.fontSize,
        fontWeight: computed.fontWeight,
        padding: computed.padding,
        margin: computed.margin,
        width: computed.width,
        height: computed.height,
      }
    };
  }

  // Hover 处理
  document.addEventListener('mouseover', function(e) {
    if (!inspectMode) return;
    var target = e.target;
    if (target === document.body || target === document.documentElement) return;
    if (hoverEl && hoverEl !== target) hoverEl.classList.remove('__arc-hover');
    if (target !== selectedEl) {
      target.classList.add('__arc-hover');
      hoverEl = target;
    }
  }, true);

  document.addEventListener('mouseout', function(e) {
    if (!inspectMode || !hoverEl) return;
    hoverEl.classList.remove('__arc-hover');
    hoverEl = null;
  }, true);

  // Click 选中
  document.addEventListener('click', function(e) {
    if (!inspectMode) return;
    e.preventDefault();
    e.stopPropagation();

    var target = e.target;
    if (target === document.body || target === document.documentElement) return;

    // 取消上一个选中
    if (selectedEl) selectedEl.classList.remove('__arc-selected');
    if (hoverEl) hoverEl.classList.remove('__arc-hover');

    target.classList.add('__arc-selected');
    selectedEl = target;
    hoverEl = null;

    // 上报
    window.parent.postMessage({
      type: 'element_selected',
      data: getElementInfo(target)
    }, '*');
  }, true);

  // 接收父级消息
  window.addEventListener('message', function(e) {
    var msg = e.data;
    if (!msg || typeof msg !== 'object') return;

    if (msg.type === 'set_inspect_mode') {
      inspectMode = !!msg.enabled;
      if (!inspectMode) {
        if (hoverEl) hoverEl.classList.remove('__arc-hover');
        if (selectedEl) selectedEl.classList.remove('__arc-selected');
        hoverEl = null;
        selectedEl = null;
      }
      document.body.style.cursor = inspectMode ? 'crosshair' : '';
    }

    if (msg.type === 'apply_html' && selectedEl) {
      // 保存 undo 快照
      undoStack.push({ el: selectedEl, html: selectedEl.outerHTML });
      // 替换
      selectedEl.outerHTML = msg.html;
      selectedEl = null;
      window.parent.postMessage({ type: 'apply_done' }, '*');
    }

    if (msg.type === 'undo' && undoStack.length > 0) {
      var snapshot = undoStack.pop();
      // 需要重新找到元素（因为 outerHTML 替换后引用失效）
      var temp = document.createElement('div');
      temp.innerHTML = snapshot.html;
      var restored = temp.firstElementChild;
      // 找到当前位置替换回去（通过 selector 或位置）
      try {
        var current = document.querySelector(getSelector(snapshot.el));
        if (current) {
          current.outerHTML = snapshot.html;
          window.parent.postMessage({ type: 'undo_done' }, '*');
        }
      } catch(ex) {
        // fallback: 无法定位，报错
        window.parent.postMessage({ type: 'undo_failed', error: ex.message }, '*');
      }
    }

    if (msg.type === 'deselect') {
      if (selectedEl) selectedEl.classList.remove('__arc-selected');
      selectedEl = null;
    }
  });
})();
<\/script>`;
}

// 将 inspector 脚本注入到原型 HTML 中
export function injectInspector(html: string): string {
  const script = buildInspectorScript();
  if (html.includes('</body>')) {
    return html.replace('</body>', script + '</body>');
  }
  return html + script;
}

// 元素信息类型
export interface SelectedElementInfo {
  selector: string;
  tagName: string;
  text: string;
  html: string;
  attributes: Record<string, string>;
  styles: Record<string, string>;
}
