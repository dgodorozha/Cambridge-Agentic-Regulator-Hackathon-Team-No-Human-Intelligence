/* HSL TERMINAL v2 client runtime.
   Command line + keyboard: CODE⏎ maximises a panel, Esc restores, 0-9 jump,
   REG opens the run registry. The market tape renders on TradingView
   Lightweight Charts (vendored, assets/vendor/, Apache-2.0). Time on the tape
   is the simulation step of one scenario, never a calendar date. The stream
   store fans out ticks, marks, alerts and ledger entries pushed by the poll. */
(function () {
  "use strict";

  var CODES = ["MKT", "NET", "GAP", "SEN", "INT", "CSF", "LDG", "RUN", "AUT", "REG", "RSK", "DAT", "SEC", "FAM", "AGT"];
  var AMBER = "#f6b52a", WHITE = "#e4e9f2", MUTED = "#5d6a80", HAIR = "rgba(148,163,196,.30)",
      INFO = "#6cb5ff", BAD = "#ff5f5f", GRIDLINE = "rgba(148,163,196,.10)";

  var st = {
    chart: null, tape: null, markers: null,
    tapes: {}, order: [], live: null, shown: null, follow: true,
    three: null, threeChart: null, threeDD: null, mode: "tape",
    lastPx: null, lastStep: null, tickerItems: [], alertCount: 0, ledgerCount: 0,
    maxed: null, selKnown: {}
  };
  window.__hslState = st;   // read only, for diagnostics

  function $(id) { return document.getElementById(id); }
  function clearNative(inp) {
    var set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    set.call(inp, "");
    inp.dispatchEvent(new Event("input", { bubbles: true }));
  }

  /* ------------------------------------------------ maximise / grid -- */
  function maximise(code) {
    if (CODES.indexOf(code) < 0) return false;
    restore();
    var p = $("panel-" + code);
    if (!p) return false;
    p.classList.add("maxed");
    document.body.classList.add("hasmax");
    st.maxed = code;
    if (code === "MKT") setTimeout(fitShown, 60);
    return true;
  }
  function restore() {
    if (st.maxed) {
      var p = $("panel-" + st.maxed);
      if (p) p.classList.remove("maxed");
    }
    document.body.classList.remove("hasmax");
    st.maxed = null;
  }
  function flash(msg, ok) {
    var el = $("cmd-msg");
    if (!el) return;
    el.textContent = msg;
    el.className = ok ? "ok" : "err";
    clearTimeout(flash._t);
    flash._t = setTimeout(function () { el.textContent = ""; }, 2600);
  }
  function frontEl() { return $("front"); }
  function frontOpen() { var f = frontEl(); return f && !f.classList.contains("off"); }
  function showFront() { var f = frontEl(); if (f) f.classList.remove("off"); }
  function hideFront() { var f = frontEl(); if (f) f.classList.add("off"); }

  function exec(raw) {
    var c = (raw || "").toUpperCase().replace(/<GO>|\s/g, "");
    if (!c) return;
    if (c === "FRONT" || c === "100") {
      restore(); showFront(); flash("Front page", true);
      if (document.activeElement) document.activeElement.blur();
      return;
    }
    if (c === "GRID" || c === "ESC" || c === "HOME") { hideFront(); restore(); flash("Grid", true); return; }
    if (c === "HELP") { flash("CODE then GO opens a page; digits 0 to 9 and K D F A S R; Esc restores the grid; drag the lines between boxes to resize; LAYOUT resets", true); return; }
    if (c === "0") c = "AUT";
    if (c === "ASK" || c === "BOT" || c === "CHAT" || c === "9") {
      hideFront(); restore();
      if (window.HSL_ASK) window.HSL_ASK.open();
      flash("ASK", true); return;
    }
    if (c === "RUNS" || c === "HIST" || c === "REGISTRY") c = "REG";
    if (c === "RISK" || c === "ASSURE" || c === "ASSURANCE" || c === "V3" || c === "RED") c = "RSK";
    if (c === "DATA" || c === "UPLOAD" || c === "DESK") c = "DAT";
    if (c === "SECURITY" || c === "POSTURE" || c === "SAFE") c = "SEC";
    if (c === "FAMILY" || c === "FAMILIES" || c === "LIB" || c === "LIBRARY" || c === "SCEN") c = "FAM";
    if (c === "AGENT" || c === "AGENTS" || c === "WORKSHOP") c = "AGT";
    if (c === "LAYOUT" || c === "RESET") { window.hslResetLayout && window.hslResetLayout(); return; }
    if (/^[1-8]$/.test(c)) c = CODES[+c - 1];
    if (window.HSL_ASK) window.HSL_ASK.close();          // a page opens from anywhere, including from ASK
    if (maximise(c)) { hideFront(); flash(c + " maximised", true); }
    else { flash("Unknown function " + c.slice(0, 12), false); }
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      hideFront(); restore();
      if (window.HSL_ASK) window.HSL_ASK.close();
      if (document.activeElement && document.activeElement.id === "cmd") {
        clearNative(document.activeElement);
        document.activeElement.blur();
      }
      return;
    }
    var t = e.target, typing = t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" ||
      t.tagName === "SELECT" || t.isContentEditable);
    if (t && t.id === "cmd" && e.key === "Enter") { exec(t.value); clearNative(t); t.blur(); e.preventDefault(); return; }
    if (frontOpen() && !typing && e.key === "Enter") { hideFront(); e.preventDefault(); return; }
    if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
    if (/^[0-9]$/.test(e.key)) { exec(e.key); e.preventDefault(); return; }
    var letter = { k: "RSK", d: "DAT", f: "FAM", a: "AGT", s: "SEC", r: "REG", g: "GRID", h: "FRONT" }[e.key.toLowerCase()];
    if (letter && !e.shiftKey) { exec(letter); e.preventDefault(); }
  }, true);
  // keys pressed inside the network or case file frames are forwarded by those pages
  window.addEventListener("message", function (e) {
    var m = e.data || {};
    if (!m.hslKey) return;
    if (m.hslKey === "Escape") { hideFront(); restore(); if (window.HSL_ASK) window.HSL_ASK.close(); return; }
    if (/^[0-9]$/.test(m.hslKey)) { exec(m.hslKey); return; }
    var letter = { k: "RSK", d: "DAT", f: "FAM", a: "AGT", s: "SEC", r: "REG", g: "GRID", h: "FRONT" }[String(m.hslKey).toLowerCase()];
    if (letter) exec(letter);
  });

  document.addEventListener("click", function (e) {
    if (!frontOpen()) return;
    var b = e.target.closest ? e.target.closest("#fenter,#frun,.slot") : null;
    if (!b) return;
    if (b.id === "fenter") { hideFront(); }
    else if (b.id === "frun") { hideFront(); exec("RUN"); }
    else if (b.dataset && b.dataset.code) { exec(b.dataset.code); }
  }, true);

  document.addEventListener("click", function (e) {
    var k = e.target.closest ? e.target.closest("button.fkey") : null;
    if (!k || !k.dataset.code) return;
    exec(k.dataset.code);
  });

  // drag handles between panels and between rows; the sizes live in the flex
  // basis of the neighbours, so the layout stays a plain flex layout
  (function () {
    var drag = null;
    function flexOf(el) { var f = parseFloat(getComputedStyle(el).flexGrow); return isNaN(f) ? 1 : f; }
    document.addEventListener("pointerdown", function (e) {
      var g = e.target.closest ? e.target.closest(".gutter") : null;
      if (!g) return;
      var prev = g.previousElementSibling, next = g.nextElementSibling;
      while (prev && prev.classList.contains("gutter")) prev = prev.previousElementSibling;
      while (next && next.classList.contains("gutter")) next = next.nextElementSibling;
      if (!prev || !next) return;
      var vertical = g.classList.contains("gutter-v");
      var a = vertical ? prev.getBoundingClientRect().width : prev.getBoundingClientRect().height;
      var b = vertical ? next.getBoundingClientRect().width : next.getBoundingClientRect().height;
      drag = { g: g, prev: prev, next: next, vertical: vertical, start: vertical ? e.clientX : e.clientY,
               a: a, b: b, total: a + b, grow: flexOf(prev) + flexOf(next) };
      g.classList.add("dragging");
      document.body.classList.add(vertical ? "resizing" : "resizing-h");
      g.setPointerCapture && g.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    document.addEventListener("pointermove", function (e) {
      if (!drag) return;
      var d = (drag.vertical ? e.clientX : e.clientY) - drag.start;
      var min = drag.vertical ? 160 : 90;
      var a = Math.max(min, Math.min(drag.total - min, drag.a + d));
      var b = drag.total - a;
      drag.prev.style.flex = (drag.grow * a / drag.total) + " 1 0";
      drag.next.style.flex = (drag.grow * b / drag.total) + " 1 0";
    });
    function end() {
      if (!drag) return;
      drag.g.classList.remove("dragging");
      document.body.classList.remove("resizing", "resizing-h");
      drag = null;
      window.dispatchEvent(new Event("resize"));      // charts and the network redraw to the new box
    }
    document.addEventListener("pointerup", end);
    document.addEventListener("pointercancel", end);
    // double click a handle to restore the default split
    document.addEventListener("dblclick", function (e) {
      var g = e.target.closest ? e.target.closest(".gutter") : null;
      if (!g) return;
      var row = g.parentElement;
      row.querySelectorAll(":scope > .panel, :scope > .trow").forEach(function (p) { p.style.flex = ""; });
      window.dispatchEvent(new Event("resize"));
    });
    window.hslResetLayout = function () {
      document.querySelectorAll(".trow, .trow > .panel").forEach(function (p) { p.style.flex = ""; });
      window.dispatchEvent(new Event("resize"));
    };
  })();

  // sectioned panel bodies: the selection survives the server's re-renders
  var SEC = {};
  function applySec(body) {
    if (!body) return;
    var want = SEC[body.id] || "0";
    var btns = body.querySelectorAll(".sec-btn"), secs = body.querySelectorAll(".sec");
    if (!btns.length) return;
    var found = false;
    btns.forEach(function (b) { if (b.dataset.sec === want) found = true; });
    if (!found) want = "0";
    btns.forEach(function (b) { b.classList.toggle("on", b.dataset.sec === want); });
    secs.forEach(function (s) { s.classList.toggle("on", s.dataset.sec === want); });
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest ? e.target.closest("button.sec-btn") : null;
    if (!b) return;
    var body = b.closest(".p-body");
    if (!body) return;
    SEC[body.id] = b.dataset.sec;
    applySec(body);
  });
  var secObs = new MutationObserver(function (muts) {
    var seen = {};
    muts.forEach(function (m) {
      var body = m.target.closest ? m.target.closest(".p-body") : null;
      if (body && !seen[body.id]) { seen[body.id] = true; applySec(body); }
    });
  });
  document.querySelectorAll(".p-body").forEach(function (b) { secObs.observe(b, { childList: true, subtree: true }); });

  // identifiers shown to the supervisor: underscores to spaces, sentence case
  var ACR = { rl: "RL", llm: "LLM", luld: "LULD", es: "ES", hhi: "HHI", ai: "AI", us: "US", eu: "EU", uk: "UK", f1: "F1" };
  function nice(s) {
    s = String(s);
    if (!/^[A-Za-z][A-Za-z0-9]*(_[A-Za-z0-9]+)+$/.test(s)) return s;
    return s.split("_").map(function (w, i) {
      var l = w.toLowerCase();
      if (ACR[l]) return ACR[l];
      if (w.length === 1 && w === w.toUpperCase()) return w;
      return i === 0 ? w.charAt(0).toUpperCase() + w.slice(1) : w;
    }).join(" ");
  }
  window.hslNice = nice;

  document.addEventListener("dblclick", function (e) {
    var head = e.target.closest && e.target.closest(".p-head");
    if (!head) return;
    var panel = head.parentElement, code = panel && panel.dataset.code;
    if (!code) return;
    if (st.maxed === code) restore(); else exec(code);
  });

  /* --------------------------------------------------------- charts -- */
  function chartOpts(el) {
    return {
      autoSize: true,
      layout: { background: { color: "transparent" }, textColor: "#97a3b8", fontSize: 10,
                fontFamily: "JetBrains Mono, ui-monospace, Menlo, Consolas, monospace", attributionLogo: false },
      grid: { vertLines: { color: GRIDLINE }, horzLines: { color: GRIDLINE } },
      crosshair: { mode: 0,
        vertLine: { color: AMBER, width: 1, style: 3, labelBackgroundColor: "#b5821a" },
        horzLine: { color: AMBER, width: 1, style: 3, labelBackgroundColor: "#b5821a" } },
      localization: { timeFormatter: function (t) { return "step " + t; } },
      timeScale: { borderColor: HAIR, timeVisible: false, secondsVisible: false,
                   tickMarkFormatter: function (t) { return String(t); } },
      rightPriceScale: { borderColor: HAIR },
      el: el
    };
  }

  function ensureTape() {
    if (st.chart) return true;
    if (typeof LightweightCharts === "undefined") return false;
    var el = $("mkt-chart");
    if (!el || !el.clientWidth) return false;
    st.chart = LightweightCharts.createChart(el, chartOpts(el));
    st.tape = st.chart.addSeries(LightweightCharts.LineSeries, {
      color: INFO, lineWidth: 1,
      priceFormat: { type: "price", precision: 4, minMove: 0.0001 },
      lastValueVisible: true, priceLineVisible: true, priceLineColor: INFO,
      crosshairMarkerVisible: true
    });
    st.markers = LightweightCharts.createSeriesMarkers(st.tape, []);
    if (st.shown) show(st.shown, true);
    return true;
  }

  function markerOf(m) {
    if (m.kind === "shock") return { time: m.step, position: "aboveBar", color: AMBER, shape: "arrowDown", text: "shock" };
    return { time: m.step, position: "belowBar", color: WHITE, shape: "circle", text: m.text || "alert" };
  }

  function show(name, force) {
    var tp = st.tapes[name];
    if (!tp || !st.tape) { st.shown = name; return; }
    if (st.shown === name && !force) return;
    st.shown = name;
    st.tape.setData(tp.pts);
    st.markers.setMarkers(tp.marks.map(markerOf).sort(function (a, b) { return a.time - b.time; }));
    st.chart.timeScale().fitContent();
    setRead("");
  }

  function fitShown() {
    if (st.chart && st.mode === "tape") st.chart.timeScale().fitContent();
    if (st.threeChart && st.mode === "3w") st.threeChart.timeScale().fitContent();
  }

  function ensureThree() {
    if (st.threeChart || !st.three) return;
    if (typeof LightweightCharts === "undefined") return;
    var el = $("mkt-three");
    if (!el) return;
    st.threeChart = LightweightCharts.createChart(el, chartOpts(el));
    function line(vals, color, width, title) {
      var s = st.threeChart.addSeries(LightweightCharts.LineSeries, {
        color: color, lineWidth: width, title: title,
        priceFormat: { type: "price", precision: 4, minMove: 0.0001 }
      });
      s.setData(vals.map(function (v, i) { return { time: i, value: v }; }));
      return s;
    }
    line(st.three.quiet, "#97a3b8", 1, "quiet");
    var herd = line(st.three.herd, BAD, 2, "herd");
    line(st.three.treated, INFO, 2, "throttle");
    if (st.three.shock != null) {
      LightweightCharts.createSeriesMarkers(herd, [{ time: st.three.shock, position: "aboveBar",
        color: AMBER, shape: "arrowDown", text: "shock" }]);
    }
  }

  function setMode(mode) {
    st.mode = mode;
    var tapeEl = $("mkt-chart"), threeEl = $("mkt-three"), bT = $("mkt-tape-btn"), b3 = $("mkt-3w-btn");
    if (!tapeEl || !threeEl) return;
    if (mode === "3w" && st.three) {
      threeEl.style.display = "block"; tapeEl.style.display = "none";
      ensureThree();
      if (b3) b3.classList.add("on"); if (bT) bT.classList.remove("on");
      var d = st.threeDD || {};
      setRead("Same shock: quiet " + fmt3(d.quiet) + ", herd " + fmt3(d.herd) + ", throttle " + fmt3(d.treated) + " (post shock drawdown)");
      requestAnimationFrame(function () { if (st.threeChart) st.threeChart.timeScale().fitContent(); });
    } else {
      threeEl.style.display = "none"; tapeEl.style.display = "block";
      if (bT) bT.classList.add("on"); if (b3) b3.classList.remove("on");
      setRead("");
      requestAnimationFrame(fitShown);
    }
  }
  function fmt3(v) { return v == null ? "n/a" : Number(v).toFixed(3); }

  document.addEventListener("click", function (e) {
    if (e.target.id === "mkt-3w-btn" && !e.target.disabled) setMode("3w");
    if (e.target.id === "mkt-tape-btn") setMode("tape");
  });
  document.addEventListener("change", function (e) {
    if (e.target.id !== "mkt-sel") return;
    var v = e.target.value;
    if (v === "__live__") { st.follow = true; if (st.live) show(st.live, true); }
    else { st.follow = false; show(v, true); }
  });

  function setRead(extra) {
    var el = $("mkt-read");
    if (!el) return;
    if (extra) { el.textContent = extra; return; }
    var tp = st.shown ? st.tapes[st.shown] : null;
    var n = tp ? tp.pts.length : 0;
    el.textContent = (st.shown ? nice(st.shown) : "No scenario") + ", " + n + " steps, one tick per simulated step" +
      (st.follow ? ", following live" : "");
  }

  function syncSelect(done) {
    var sel = $("mkt-sel");
    if (!sel) return;
    (done || []).forEach(function (d) {
      if (st.selKnown[d.name]) return;
      st.selKnown[d.name] = true;
      var o = document.createElement("option");
      o.value = d.name;
      o.textContent = nice(d.name) + (d.quiet ? ", quiet" : ", shock t=" + d.shock) +
        (d.holdout ? ", held out" : "") + ", DD " + Number(d.post_shock_dd).toFixed(3);
      sel.appendChild(o);
    });
  }

  /* ------------------------------------------------------ feeds etc -- */
  function feedRow(host, cls, cells, cap) {
    var row = document.createElement("div");
    row.className = "row new " + cls;
    cells.forEach(function (c) {
      var s = document.createElement("span");
      s.className = c[0]; s.textContent = c[1]; row.appendChild(s);
    });
    host.insertBefore(row, host.firstChild);
    while (host.childNodes.length > cap) host.removeChild(host.lastChild);
  }

  function pushTicker(items) {
    st.tickerItems = st.tickerItems.concat(items).slice(-8);
    var el = $("ticker-text");
    if (!el || !st.tickerItems.length) return;
    el.innerHTML = "";
    st.tickerItems.forEach(function (a, i) {
      if (i) { var sep = document.createElement("span"); sep.className = "sep"; sep.textContent = "|"; el.appendChild(sep); }
      var s = document.createElement("span"); s.className = "a-" + a.lvl; s.textContent = a.msg; el.appendChild(s);
    });
  }

  /* -------------------------------------------------- stream fanout -- */
  window.dash_clientside = window.dash_clientside || {};
  window.dash_clientside.hsl = {
    onStream: function (d) {
      if (!d) return 0;
      var ready = ensureTape();

      if ((d.run_id && st.runId && d.run_id !== st.runId) || (!d.run_id && st.runId)) {
        /* a new run started: clear the tape store */
        st.tapes = {}; st.order = []; st.live = null; st.shown = null; st.follow = true;
        st.three = null; st.threeChart = null; st.selKnown = {};
        var sel = $("mkt-sel");
        if (sel) { sel.innerHTML = ""; var o = document.createElement("option"); o.value = "__live__"; o.textContent = "Live"; sel.appendChild(o); }
        var t3 = $("mkt-three"); if (t3) t3.innerHTML = "";
        if (st.tape) { st.tape.setData([]); st.markers.setMarkers([]); }
        setMode("tape");
        var sa = $("sen-alerts"); if (sa) sa.innerHTML = "";
        var lf = $("ldg-feed"); if (lf) lf.innerHTML = "";
        st.alertCount = 0; st.ledgerCount = 0;
      }
      st.runId = d.run_id || null;

      if (d.ticks && d.ticks.length) {
        d.ticks.forEach(function (t) {
          var scen = t[0], step = t[1], v = t[2];
          if (!st.tapes[scen]) { st.tapes[scen] = { pts: [], marks: [] }; st.order.push(scen); }
          var tp = st.tapes[scen];
          if (!tp.pts.length || tp.pts[tp.pts.length - 1].time < step) tp.pts.push({ time: step, value: v });
          st.live = scen; st.lastPx = v; st.lastStep = step;
        });
        if (st.follow && st.live && st.shown !== st.live) show(st.live, true);
        else if (ready && st.shown === st.live) {
          var tp2 = st.tapes[st.live], last = tp2.pts[tp2.pts.length - 1];
          d.ticks.forEach(function (t) { if (t[0] === st.live) st.tape.update({ time: t[1], value: t[2] }); });
          if (last) st.chart.timeScale().scrollToRealTime();
        }
      }
      if (d.marks && d.marks.length) {
        d.marks.forEach(function (m) {
          if (!st.tapes[m.scen]) { st.tapes[m.scen] = { pts: [], marks: [] }; st.order.push(m.scen); }
          st.tapes[m.scen].marks.push(m);
        });
        if (ready && st.shown) {
          st.markers.setMarkers(st.tapes[st.shown].marks.map(markerOf).sort(function (a, b) { return a.time - b.time; }));
        }
      }
      syncSelect(d.tapes_done);

      var tr = $("tick-read");
      if (tr) tr.textContent = st.lastPx == null ? "" :
        (nice(st.live || "") + "  last " + st.lastPx.toFixed(4) + "  step " + st.lastStep);
      if (st.mode === "tape") setRead("");

      if (d.alerts && d.alerts.length) {
        var host = $("sen-alerts");
        d.alerts.forEach(function (a) { if (host) feedRow(host, a.lvl, [["t", a.t], ["m", a.msg]], 250); });
        st.alertCount += d.alerts.length;
        pushTicker(d.alerts);
        var pl = $("ph-live-SEN"); if (pl) pl.textContent = "alerts " + st.alertCount;
      }
      if (d.ledger && d.ledger.length) {
        var lg = $("ldg-feed");
        d.ledger.forEach(function (r) {
          if (lg) feedRow(lg, "info", [["t", "#" + r.seq + " " + r.ts], ["a", r.actor],
            ["m", r.event + (r.keys ? " (" + r.keys + ")" : "")], ["h", r.hash + "…"]], 400);
        });
        st.ledgerCount = Math.max(st.ledgerCount, d.ledger[d.ledger.length - 1].seq || 0);
        var pll = $("ph-live-LDG"); if (pll) pll.textContent = "chain " + st.ledgerCount;
      }

      var lamp = $("live-stage");
      if (lamp && d.stage) { lamp.textContent = d.stage.toUpperCase(); lamp.className = "st-" + d.stage; document.body.dataset.stage = d.stage; }
      var ph = $("phase-line"); if (ph && d.phase) ph.textContent = d.phase;
      var pr = $("ph-live-RUN"); if (pr && d.stage) pr.textContent = d.stage;

      if (d.three && !st.three) {
        st.three = d.three; st.threeDD = d.three_dd || null;
        var b3 = $("mkt-3w-btn"); if (b3) b3.disabled = false;
      }
      return 0;
    }
  };

  /* ------------------------------------------------------ bootstrap -- */
  function boot() {
    var clockOn = false, chipsOn = false;
    function tryClock() {
      if (clockOn) return true;
      var clk = $("clock"); if (!clk) return false;
      clockOn = true;
      var tick = function () { clk.textContent = new Date().toISOString().slice(11, 19) + " UTC"; };
      tick(); setInterval(tick, 1000);
      return true;
    }
    function tryChips() {
      if (chipsOn) return true;
      var live = { NET: "live run", CSF: "pivot", GAP: "fidelity against decision", INT: "6 rules", REG: "all runs", RSK: "assurance" };
      var keys = Object.keys(live);
      if (!$("ph-live-" + keys[0])) return false;
      keys.forEach(function (k) { var el = $("ph-live-" + k); if (el) el.textContent = live[k]; });
      chipsOn = true;
      return true;
    }
    var tries = 0, t = setInterval(function () {
      var tapeUp = ensureTape();
      if (!tapeUp) setRead("");
      var extras = tryClock() && tryChips();
      if ((tapeUp && extras) || ++tries > 240) clearInterval(t);
    }, 250);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot); else boot();
})();

/* ---------------------------------------- ASK: server side, grounded -- */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var ASK = { welcomed: false, busy: false };
  var esc = function (s) {
    return String(s).replace(/[&<>]/g, function (m) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;" }[m]; });
  };

  function chLog(cls, html) {
    var d = document.createElement("div");
    d.className = "msg " + cls;
    d.innerHTML = html;
    $("ch-log").appendChild(d);
    $("ch-log").scrollTop = 1e9;
    return d;
  }

  function showSources(srcs) {
    $("ch-src").innerHTML = (srcs || []).map(function (c, i) {
      return '<div class="s"><b>[S' + (i + 1) + "] " + esc(c.title) + "</b><br>" + esc(c.text) + "</div>";
    }).join("") || '<div class="s">no matching context</div>';
  }

  function openChat() {
    document.body.classList.add("chatting");
    if (!ASK.welcomed) {
      ASK.welcomed = true;
      chLog("bot", "Ask about this run: a sentinel, the decision gap, a scenario, an intervention " +
        "rule, the autonomy gate, the ledger, or \u201cwhat should the authority certify?\u201d " +
        "Answers are computed on the server from the run artefacts; sources appear on the right.");
    }
    var inp = $("ch-in"); if (inp) inp.focus();
  }
  function closeChat() { var i = $("ch-in"); if (i) i.blur(); document.body.classList.remove("chatting"); }

  function clearInput(inp) {
    var set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
    set.call(inp, "");
    inp.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function askSend() {
    var inp = $("ch-in"), q = (inp.value || "").trim();
    if (!q || ASK.busy) return;
    ASK.busy = true;
    clearInput(inp);
    chLog("user", esc(q));
    var think = chLog("think", "consulting the artefacts \u2026");
    var whoEl = $("approver"), who = whoEl ? whoEl.value : "";
    fetch("/ask", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ q: q, who: who }) })
      .then(function (r) { return r.json().then(function (d) { d._status = r.status; return d; }); })
      .then(function (d) {
        think.remove();
        if (d.error) { chLog("bot", esc("Not answered: " + d.error)); return; }
        chLog("bot", esc(d.text));
        showSources(d.sources);
        $("ch-brain").textContent = d.brain || "";
      })
      .catch(function (e) { think.remove(); chLog("bot", esc("The server did not answer (" + e + ")")); })
      .then(function () { ASK.busy = false; });
  }

  window.HSL_ASK = { open: openChat, close: closeChat,
    isOpen: function () { return document.body.classList.contains("chatting"); } };

  var tries = 0, t = setInterval(function () {
    var back = $("ch-back"), send = $("ch-send"), inp = $("ch-in");
    if (back && send && inp) {
      back.onclick = closeChat;
      send.onclick = askSend;
      inp.addEventListener("keydown", function (e) { if (e.key === "Enter") { askSend(); e.stopPropagation(); } });
      clearInterval(t);
    } else if (++tries > 240) { clearInterval(t); }
  }, 250);
})();
