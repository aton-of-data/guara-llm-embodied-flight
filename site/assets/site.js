// SPDX-License-Identifier: Apache-2.0
// Guará project site — theme persistence, code decoration, TOC scroll-spy.
(function () {
  "use strict";

  /* ---- theme ---- */
  var root = document.documentElement;
  function apply(t) {
    root.setAttribute("data-theme", t);
    var b = document.getElementById("theme-toggle");
    if (b) {
      b.textContent = t === "dark" ? "☾" : "☀";
      b.setAttribute("aria-label", "Switch to " + (t === "dark" ? "light" : "dark") + " theme");
    }
  }
  var stored = null;
  try { stored = localStorage.getItem("guara-theme"); } catch (e) {}
  apply(stored || (window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark"));

  document.addEventListener("click", function (ev) {
    var t = ev.target.closest && ev.target.closest("#theme-toggle");
    if (!t) return;
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    apply(next);
    try { localStorage.setItem("guara-theme", next); } catch (e) {}
  });

  /* ---- lightweight code decoration ----
     Deliberately conservative: comments, strings, numbers and a small keyword set.
     Nothing here parses the language; it only tints what is unambiguous. */
  var KW = {
    bash: /\b(?:cd|export|pip|python3|docker|colcon|ros2|sudo|test|echo|git|source|make|curl|ollama)\b/g,
    cpp: /\b(?:struct|class|const|constexpr|noexcept|bool|double|void|return|if|else|inline|namespace|using|auto|static|std|uint8_t|uint16_t|uint32_t|uint64_t|float|explicit|public|private)\b/g,
    python: /\b(?:def|class|return|import|from|if|else|elif|for|in|not|and|or|None|True|False|raise|with|as|lambda)\b/g,
    json: /\b(?:true|false|null)\b/g
  };
  var SENTINEL_A = "␄";
  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

  Array.prototype.forEach.call(document.querySelectorAll("pre > code"), function (code) {
    var lang = (code.className.match(/language-(\w+)/) || [, "text"])[1];
    var out = esc(code.textContent);
    var slots = [];
    function stash(html) { slots.push(html); return SENTINEL_A + (slots.length - 1) + SENTINEL_A; }

    // strings first, then comments, so a # inside a string survives
    out = out.replace(/(&quot;)(?:[^\\\n]|\\.)*?\1|"(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'/g, function (m) {
      return stash('<span class="t-str">' + m + "</span>");
    });
    out = out.replace(/(^|[^:\w/])(#|\/\/)[^\n]*/g, function (m, p) {
      return p + stash('<span class="t-cmt">' + m.slice(p.length) + "</span>");
    });
    if (KW[lang]) out = out.replace(KW[lang], function (m) { return stash('<span class="t-kw">' + m + "</span>"); });
    out = out.replace(/\b\d+(?:\.\d+)?(?:e-?\d+)?\b/g, function (m) { return stash('<span class="t-num">' + m + "</span>"); });
    out = out.replace(new RegExp(SENTINEL_A + "(\\d+)" + SENTINEL_A, "g"), function (_, i) { return slots[+i]; });
    code.innerHTML = out;
  });

  /* ---- copy buttons ---- */
  Array.prototype.forEach.call(document.querySelectorAll(".code-head .copy"), function (btn) {
    btn.addEventListener("click", function () {
      var pre = btn.closest(".code-head").nextElementSibling;
      if (!pre) return;
      var text = pre.innerText;
      var done = function () {
        var o = btn.getAttribute("data-label") || "copy";
        btn.textContent = "copied";
        setTimeout(function () { btn.textContent = o; }, 1400);
      };
      if (navigator.clipboard) { navigator.clipboard.writeText(text).then(done, function () {}); }
      else {
        var ta = document.createElement("textarea");
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand("copy"); done(); } catch (e) {}
        document.body.removeChild(ta);
      }
    });
  });

  /* ---- TOC scroll-spy ---- */
  var links = Array.prototype.slice.call(document.querySelectorAll(".toc a[href^='#']"));
  if (links.length && "IntersectionObserver" in window) {
    var map = {};
    var order = [];
    links.forEach(function (a) {
      var el = document.getElementById(a.getAttribute("href").slice(1));
      if (el) { map[el.id] = a; order.push(el.id); }
    });
    var seen = {};
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { seen[e.target.id] = e.isIntersecting; });
      var current = null;
      order.forEach(function (id) { if (seen[id] && !current) current = id; });
      links.forEach(function (a) { a.classList.remove("active"); });
      if (current && map[current]) map[current].classList.add("active");
    }, { rootMargin: "-88px 0px -70% 0px", threshold: 0 });
    order.forEach(function (id) { obs.observe(document.getElementById(id)); });
  }
})();
