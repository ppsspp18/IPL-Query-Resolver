const state = {
    queries: [],
    current: null,
    options: {},
    running: false,
};

const $ = (sel) => document.querySelector(sel);

async function api(path) {
    const res = await fetch(path);
    if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Request failed (${res.status})`);
    }
    return res.json();
}

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

    $("#querySearch").addEventListener("input", (e) => {
        const q = e.target.value.toLowerCase();
        const filtered = state.queries.filter(
            (qy) => qy.title.toLowerCase().includes(q) || String(qy.id) === q
        );
        renderQueryList(filtered);
    });

    $("#inputForm").addEventListener("submit", runQuery);
    $("#copyBtn").addEventListener("click", copyResults);
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
        const btn = makeRunButton();
        form.appendChild(btn);
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
    const tableWrap = document.createElement("div");
    tableWrap.className = "table-wrap";

    const table = document.createElement("table");
    const thead = document.createElement("thead");
    const headRow = document.createElement("tr");
    section.columns.forEach((col) => {
        const th = document.createElement("th");
        th.textContent = col;
        headRow.appendChild(th);
    });
    thead.appendChild(headRow);
    const tbody = document.createElement("tbody");
    section.rows.forEach((row) => {
        const tr = document.createElement("tr");
        section.columns.forEach((col) => {
            const td = document.createElement("td");
            td.textContent = formatCell(row[col]);
            td.title = formatCell(row[col]);
            tr.appendChild(td);
        });
        tbody.appendChild(tr);
    });
    table.appendChild(thead);
    table.appendChild(tbody);
    tableWrap.appendChild(table);

    const count = document.createElement("div");
    count.className = "row-count";
    count.textContent = `${section.rows.length} row${section.rows.length === 1 ? "" : "s"}`;

    wrap.appendChild(title);
    wrap.appendChild(tableWrap);
    wrap.appendChild(count);
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

function formatCell(value) {
    if (value === null || value === undefined) return "";
    return String(value);
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

function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
}

init().catch((err) => showError("Failed to load: " + err.message));
