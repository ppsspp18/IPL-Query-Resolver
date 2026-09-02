const state = {
    queries: [],
    current: null,
    options: {},
    running: false,
    benchmarkLoaded: false,
};

const $ = (sel) => document.querySelector(sel);

// --------------------------------------------------------------------------
// Helpers
// --------------------------------------------------------------------------
async function api(path, opts) {
    const res = await fetch(path, opts);
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${res.status})`);
    }
    return res.json();
}

function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

function formatCell(value) {
    if (value === null || value === undefined) return "";
    return String(value);
}

function renderTableSection(columns, rows) {
    const wrap = document.createElement("div");
    const tableWrap = document.createElement("div");
    tableWrap.className = "table-wrap";
    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    columns.forEach((col) => {
        const th = document.createElement("th");
        th.textContent = col;
        headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    const tbody = document.createElement("tbody");
    rows.forEach((row) => {
        const tr = document.createElement("tr");
        columns.forEach((col) => {
            const td = document.createElement("td");
            const val = formatCell(row[col]);
            td.textContent = val;
            td.title = val;
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(thead);
    table.appendChild(tbody);
    tableWrap.appendChild(table);
    wrap.appendChild(tableWrap);
    const count = document.createElement("div");
    count.className = "row-count";
    count.textContent = `${rows.length} row${rows.length === 1 ? "" : "s"}`;
    wrap.appendChild(count);
    return wrap;
}

// --------------------------------------------------------------------------
// View switching
// --------------------------------------------------------------------------
function switchView(view) {
    document.querySelectorAll(".tab").forEach((t) => {
        t.classList.toggle("active", t.dataset.view === view);
    });
    ["queries", "chat", "benchmark"].forEach((v) => {
        $(`#view-${v}`).classList.toggle("hidden", v !== view);
    });
    if (view === "benchmark" && !state.benchmarkLoaded) runBenchmark();
}

// --------------------------------------------------------------------------
// Queries tab
// --------------------------------------------------------------------------
async function loadOptionSource(source) {
    if (state.options[source]) return state.options[source];
    const data = await api(`/api/options?source=${encodeURIComponent(source)}`);
    state.options[source] = data.values;
    return data.values;
}

async function init() {
    const data = await api("/api/queries");
    state.queries = data.queries;
    renderQueryList(state.queries);

    document.querySelectorAll(".tab").forEach((t) => {
        t.addEventListener("click", () => switchView(t.dataset.view));
    });

    $("#querySearch").addEventListener("input", (e) => {
        const q = e.target.value.toLowerCase();
        const filtered = state.queries.filter(
            (qy) => qy.title.toLowerCase().includes(q) || String(qy.id) === q
        );
        renderQueryList(filtered);
    });

    $("#inputForm").addEventListener("submit", runQuery);
    $("#copyBtn").addEventListener("click", copyResults);
    initChat();
}

function renderQueryList(queries) {
    const ul = $("#queryList");
    ul.innerHTML = "";
    queries.forEach((q) => {
        const li = document.createElement("li");
        li.dataset.id = q.id;
        li.innerHTML = `<span class="qid">${q.id}</span>${escapeHtml(q.title)}`;
        li.addEventListener("click", () => selectQuery(q.id));
        ul.appendChild(li);
    });
}

function selectQuery(id) {
    state.current = state.queries.find((q) => q.id === id);
    document.querySelectorAll("#queryList li").forEach((li) => {
        li.classList.toggle("active", Number(li.dataset.id) === id);
    });
    $("#queryTitle").textContent = `${state.current.id}. ${state.current.title}`;
    $("#queryDesc").textContent = state.current.desc || "";
    $("#resultPanel").classList.add("hidden");
    $("#errorPanel").classList.add("hidden");
    $("#copyBtn").classList.add("hidden");
    renderInputs(state.current.inputs);
}

async function renderInputs(inputs) {
    const form = $("#inputForm");
    form.innerHTML = "";
    if (!inputs.length) {
        form.appendChild(makeRunButton());
        return;
    }
    for (const input of inputs) {
        if (input.type === "radio") {
            const field = document.createElement("div");
            field.className = "field";
            const label = document.createElement("label");
            label.textContent = input.label;
            const group = document.createElement("div");
            group.className = "radio-group";
            const opts = input.options || [];
            opts.forEach((opt, idx) => {
                const lbl = document.createElement("label");
                const rad = document.createElement("input");
                rad.type = "radio";
                rad.name = input.name;
                rad.value = opt.value;
                if ((input.default || opts[0].value) === opt.value) {
                    rad.checked = true;
                    lbl.classList.add("selected");
                }
                rad.addEventListener("change", () => {
                    group.querySelectorAll("label").forEach((l) => l.classList.remove("selected"));
                    lbl.classList.add("selected");
                });
                lbl.appendChild(rad);
                lbl.appendChild(document.createTextNode(" " + opt.label));
                group.appendChild(lbl);
            });
            field.appendChild(label);
            field.appendChild(group);
            form.appendChild(field);
        } else if (input.type === "select") {
            const field = document.createElement("div");
            field.className = "field";
            const label = document.createElement("label");
            label.textContent = input.label;
            const sel = document.createElement("select");
            sel.name = input.name;
            sel.dataset.required = input.required === false ? "false" : "true";
            const ph = document.createElement("option");
            ph.value = "";
            ph.textContent = input.required === false ? `All ${input.label}s` : `Select ${input.label}...`;
            sel.appendChild(ph);
            field.appendChild(label);
            field.appendChild(sel);
            form.appendChild(field);
            loadOptionSource(input.source)
                .then((values) => {
                    values.forEach((v) => {
                        const opt = document.createElement("option");
                        opt.value = v;
                        opt.textContent = v;
                        sel.appendChild(opt);
                    });
                })
                .catch((err) => showError(err.message));
        }
    }
    form.appendChild(makeRunButton());
}

function makeRunButton() {
    const btn = document.createElement("button");
    btn.type = "submit";
    btn.className = "btn";
    btn.id = "runBtn";
    btn.textContent = "Run Query";
    return btn;
}

async function runQuery(e) {
    e.preventDefault();
    if (!state.current || state.running) return;

    const inputs = {};
    let valid = true;
    document.querySelectorAll("#inputForm select").forEach((sel) => {
        const required = sel.dataset.required === "false";
        if (sel.value) inputs[sel.name] = sel.value;
        else if (!required) valid = false;
    });
    document.querySelectorAll("#inputForm input[type=radio]:checked").forEach((rad) => {
        inputs[rad.name] = rad.value;
    });

    if (!valid) {
        showError("Please fill in all required fields.");
        return;
    }

    const samePairs = [["bowler", "batter"], ["team1", "team2"]];
    for (const [a, b] of samePairs) {
        if (inputs[a] && inputs[b] && inputs[a] === inputs[b]) {
            showError(`${a === "bowler" ? "Bowler" : "Team 1"} and ${a === "bowler" ? "batter" : "Team 2"} must be different players/teams.`);
            return;
        }
    }

    state.running = true;
    const btn = $("#runBtn");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span>';
    $("#errorPanel").classList.add("hidden");

    try {
        const data = await fetch("/api/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ query_id: state.current.id, inputs }),
        });
        const body = await data.json().catch(() => ({}));
        if (!data.ok) throw new Error(body.detail || `Request failed (${data.status})`);
        renderResult(body.result);
    } catch (err) {
        showError(err.message);
    } finally {
        state.running = false;
        btn.disabled = false;
        btn.textContent = "Run Query";
    }
}

function renderResult(result) {
    const panel = $("#resultPanel");
    panel.classList.remove("hidden");
    $("#resultTitle").textContent = result.title;
    const body = $("#resultBody");
    body.innerHTML = "";

    result.sections.forEach((section) => {
        if (section.type === "table") {
            body.appendChild(renderTable(section));
        } else if (section.type === "cards") {
            body.appendChild(renderCards(section));
        } else if (section.type === "note") {
            const note = document.createElement("div");
            note.className = "note";
            note.textContent = section.text;
            body.appendChild(note);
        }
    });

    $("#copyBtn").classList.remove("hidden");
    window.scrollTo({ top: panel.offsetTop - 12, behavior: "smooth" });
}

function renderTable(section) {
    const wrap = document.createElement("div");
    const title = document.createElement("div");
    title.className = "section-title";
    title.textContent = section.title || "Results";
    const tableWrap = renderTableSection(section.columns, section.rows);
    wrap.appendChild(title);
    wrap.appendChild(tableWrap);
    return wrap;
}

function renderCards(section) {
    const wrap = document.createElement("div");
    const title = document.createElement("div");
    title.className = "section-title";
    title.textContent = section.title || "";
    const grid = document.createElement("div");
    grid.className = "cards-grid";
    section.cards.forEach((card) => {
        const div = document.createElement("div");
        div.className = "card";
        const label = document.createElement("div");
        label.className = "card-label";
        label.textContent = card.label;
        const value = document.createElement("div");
        value.className = "card-value";
        value.textContent = card.value;
        div.appendChild(label);
        div.appendChild(value);
        if (card.detail) {
            const detail = document.createElement("div");
            detail.className = "card-detail";
            detail.textContent = card.detail;
            div.appendChild(detail);
        }
        grid.appendChild(div);
    });
    wrap.appendChild(title);
    wrap.appendChild(grid);
    return wrap;
}

function showError(msg) {
    const panel = $("#errorPanel");
    panel.textContent = msg;
    panel.classList.remove("hidden");
    $("#copyBtn").classList.add("hidden");
}

function copyResults() {
    const tables = $("#resultBody").querySelectorAll("table");
    const parts = [];
    let i = 0;
    $("#resultBody").querySelectorAll(".table-wrap").forEach((tw) => {
        const table = tw.querySelector("table");
        const rows = [];
        table.querySelectorAll("tr").forEach((tr) => {
            const cells = [];
            tr.querySelectorAll("th,td").forEach((c) => cells.push('"' + c.textContent.replace(/"/g, '""') + '"'));
            rows.push(cells.join(","));
        });
        const title = tw.previousElementSibling && tw.previousElementSibling.classList.contains("section-title")
            ? tw.previousElementSibling.textContent : "Table " + (i + 1);
        parts.push(title + "\n" + rows.join("\n"));
        i++;
    });
    if (!parts.length) return;
    navigator.clipboard.writeText(parts.join("\n\n")).then(() => {
        const btn = $("#copyBtn");
        const old = btn.textContent;
        btn.textContent = "Copied!";
        setTimeout(() => (btn.textContent = old), 1200);
    });
}

// --------------------------------------------------------------------------
// Chat tab — WebSocket streaming of the request lifecycle
// --------------------------------------------------------------------------
let chatSocket = null;
let chatPending = [];
let chatActive = false;

function initChat() {
    $("#chatForm").addEventListener("submit", (e) => {
        e.preventDefault();
        const input = $("#chatInput");
        const question = input.value.trim();
        if (!question) return;
        input.value = "";
        enqueueChat(question);
    });
    $("#chatLog").addEventListener("click", (e) => {
        const chip = e.target.closest(".chip");
        if (chip) {
            $("#chatInput").value = chip.dataset.q;
            $("#chatForm").dispatchEvent(new Event("submit"));
        }
    });
}

function enqueueChat(question) {
    addChatMessage("user", question);
    if (chatActive) {
        // Queue for after the current question resolves (server is serial).
        chatPending.push(question);
        return;
    }
    sendChat(question);
}

function addChatMessage(role, text) {
    const msg = document.createElement("div");
    msg.className = `chat-msg ${role}`;
    msg.textContent = text;
    $("#chatLog").appendChild(msg);
    scrollChat();
    return msg;
}

function addChatBubble(role) {
    const bubble = document.createElement("div");
    bubble.className = `chat-msg ${role} chat-rich`;
    $("#chatLog").appendChild(bubble);
    scrollChat();
    return bubble;
}

function scrollChat() {
    $("#chatLog").scrollTop = $("#chatLog").scrollHeight;
}

function stageRow(bubble, label) {
    const row = document.createElement("div");
    row.className = "stage-row";
    row.innerHTML = `<span class="spinner"></span> ${escapeHtml(label)}...`;
    bubble.appendChild(row);
    scrollChat();
    return row;
}

function stageDone(row, detail, ok = true) {
    const status = ok ? "ok" : "err";
    const mark = ok ? "&#10003;" : "&#10007;";
    const text = row.textContent.replace(/\.\.\.$/, "");
    row.innerHTML = `<span class="stage-dot ${status}">${mark}</span> ${text} ${detail ? `<span class="stage-detail">${escapeHtml(detail)}</span>` : ""}`;
    row.classList.add("done");
    scrollChat();
}

function renderSqlBlock(container, sql, source) {
    const wrap = document.createElement("div");
    wrap.className = "sql-block";
    const head = document.createElement("div");
    head.className = "sql-head";
    head.textContent = `Generated SQL ${source ? `(via ${source} engine)` : ""}`;
    const pre = document.createElement("pre");
    pre.textContent = sql;
    wrap.appendChild(head);
    wrap.appendChild(pre);
    container.appendChild(wrap);
    scrollChat();
}

function renderChatResult(bubble, result) {
    if (result.truncated) {
        const note = document.createElement("div");
        note.className = "note";
        note.textContent = `Showing first ${result.rows.length} of ${result.row_count} rows.`;
        bubble.appendChild(note);
    }
    if (result.rows && result.rows.length) {
        bubble.appendChild(renderTableSection(result.columns, result.rows));
    } else {
        const note = document.createElement("div");
        note.className = "note";
        note.textContent = "No rows returned.";
        bubble.appendChild(note);
    }
    scrollChat();
}

function sendChat(question) {
    chatActive = true;
    const sendBtn = $("#chatForm button");
    sendBtn.disabled = true;

    const bubble = addChatBubble("assistant");
    let pending = stageRow(bubble, "Connecting to WebSocket");
    let validationRow = null;
    let genRow = null;
    let execRow = null;
    let gotResult = false;

    const finish = () => {
        chatActive = false;
        sendBtn.disabled = false;
        if (chatPending.length) sendChat(chatPending.shift());
    };

    const onMessage = (ev) => {
        switch (ev.type) {
            case "validation":
                if (!validationRow) {
                    validationRow = pending;
                    stageDone(validationRow, "");
                    pending = null;
                }
                break;
            case "sql_generation":
                if (!genRow) {
                    genRow = stageRow(bubble, "Detecting intent & generating schema-aware SQL");
                    stageDone(genRow, ev.data ? `intent: ${ev.data.intent}` : "");
                    if (ev.data && ev.data.sql) renderSqlBlock(bubble, ev.data.sql, ev.data.sql_source);
                }
                break;
            case "query_execution":
                if (!execRow) {
                    execRow = stageRow(bubble, "Executing read-only query on MySQL");
                    stageDone(execRow, ev.data ? `${ev.data.row_count} rows in ${ev.data.elapsed_ms} ms` : "");
                }
                break;
            case "result":
                gotResult = true;
                if (pending) { stageDone(pending, ""); pending = null; }
                renderChatResult(bubble, ev.data);
                break;
            case "error":
                gotResult = true;
                const err = document.createElement("div");
                err.className = "chat-error";
                err.textContent = `\u26A0 ${ev.message || "Something went wrong"}`;
                bubble.appendChild(err);
                scrollChat();
                break;
        }
        if (gotResult) finish();
    };

    const open = () => {
        if (chatSocket && chatSocket.readyState === WebSocket.OPEN) {
            chatSocket.onmessage = (e) => { let m; try { m = JSON.parse(e.data); } catch { return; } onMessage(m); };
            pending.innerHTML = `<span class="stage-dot ok">&#10003;</span> Stream connected`;
            chatSocket.send(JSON.stringify({ question }));
        } else {
            const proto = location.protocol === "https:" ? "wss" : "ws";
            chatSocket = new WebSocket(`${proto}://${location.host}/ws/chat`);
            chatSocket.onopen = () => open();
            chatSocket.onerror = () => {
                if (pending) { pending.innerHTML = `<span class="stage-dot err">&#10007;</span> WebSocket error`; pending = null; }
                finish();
            };
            chatSocket.onmessage = (e) => { let m; try { m = JSON.parse(e.data); } catch { return; } onMessage(m); };
            chatSocket.onclose = () => {
                chatSocket = null;
                if (!gotResult && pending) {
                    pending.classList.add("err");
                    pending.innerHTML = `<span class="stage-dot err">&#10007;</span> Connection closed before a response was received.`;
                    pending = null;
                }
                finish();
            };
        }
    };
    open();
}

// --------------------------------------------------------------------------
// Benchmark tab
// --------------------------------------------------------------------------
let benchmarkRunning = false;

async function runBenchmark() {
    if (benchmarkRunning) return;
    benchmarkRunning = true;
    const btn = $("#benchRun");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Running 33 queries...';
    $("#benchSummary").innerHTML = "";
    $("#benchBody").innerHTML = "";

    try {
        const report = await api("/api/benchmark");
        state.benchmarkLoaded = true;
        renderBenchmark(report);
    } catch (err) {
        $("#benchBody").innerHTML = `<div class="note">Failed to run benchmark: ${escapeHtml(err.message)}</div>`;
    } finally {
        benchmarkRunning = false;
        btn.disabled = false;
        btn.textContent = "Run benchmark";
    }
}

function renderBenchmark(report) {
    const summary = $("#benchSummary");
    const cards = [
        ["Accuracy", `${report.accuracy}%`, `${report.passed}/${report.total} correct`],
        ["Passed", report.passed, "correct answers"],
        ["Wrong", report.wrong, "result mismatch"],
        ["Failed", report.failed, "could not answer"],
        ["Avg query time", `${report.avg_query_ms} ms`, "per question"],
    ];
    const grid = document.createElement("div");
    grid.className = "cards-grid";
    cards.forEach(([label, value, detail]) => {
        const div = document.createElement("div");
        div.className = "card";
        const l = document.createElement("div");
        l.className = "card-label";
        l.textContent = label;
        const v = document.createElement("div");
        v.className = "card-value";
        v.textContent = value;
        div.appendChild(l);
        div.appendChild(v);
        if (detail) {
            const d = document.createElement("div");
            d.className = "card-detail";
            d.textContent = detail;
            div.appendChild(d);
        }
        grid.appendChild(div);
    });
    summary.appendChild(grid);

    const body = $("#benchBody");
    const title = document.createElement("div");
    title.className = "section-title";
    title.textContent = "Per-case results (33 complex queries)";
    body.appendChild(title);

    const tableWrap = document.createElement("div");
    tableWrap.className = "table-wrap";
    const table = document.createElement("table");
    table.className = "bench-table";
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr><th>ID</th><th>Status</th><th>Category</th><th>Intent</th><th>SQL match</th><th>Time (ms)</th><th>Question</th></tr>";
    table.appendChild(thead);
    const tbody = document.createElement("tbody");
    report.cases.forEach((c) => {
        const tr = document.createElement("tr");
        const status = c.status === "passed" ? "PASS" : c.status === "wrong" ? "WRONG" : "FAIL";
        const cls = `badge ${c.status}`;
        const detail = c.status === "failed" && c.error ? ` title="${escapeHtml(c.error)}"` : "";
        tr.innerHTML = `
            <td>${c.id}</td>
            <td><span class="${cls}"${detail}>${status}</span></td>
            <td>${escapeHtml(c.category)}</td>
            <td>${escapeHtml(c.intent)}</td>
            <td>${c.sql_match ? "yes" : "-"}</td>
            <td>${c.elapsed_ms || 0}</td>
            <td>${escapeHtml(c.question)}</td>`;
        tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    tableWrap.appendChild(table);
    body.appendChild(tableWrap);
    const count = document.createElement("div");
    count.className = "row-count";
    count.textContent = `${report.total} queries`;
    body.appendChild(count);
}

init().catch((err) => showError("Failed to load: " + err.message));
