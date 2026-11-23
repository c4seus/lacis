"use strict";
(function () {
  const SVG = "http://www.w3.org/2000/svg";
  const THEMES = [
    { value: "", label: "Thème : automatique" },
    { value: "light", label: "Thème : clair" },
    { value: "dark", label: "Thème : sombre" },
  ];
  const ZOOM_STEP = 1.25;
  const MARGIN = 80;
  const data = JSON.parse(document.getElementById("lacis-data").textContent);
  const nodes = new Map(data.nodes.map((node) => [node.id, node]));
  const svg = document.getElementById("graph");
  const viewport = document.getElementById("viewport");
  const nodeLayer = document.getElementById("nodes");
  const edgeLayer = document.getElementById("edges");
  const details = document.getElementById("details");
  const list = document.getElementById("entities");
  const search = document.getElementById("search");
  const searchStatus = document.getElementById("search-status");
  const view = { x: 0, y: 0, scale: 1 };
  const shapes = new Map();
  const buttons = new Map();
  const edges = [];
  let selected = null;
  let themeIndex = 0;

  function element(name, attributes, parent) {
    const created = document.createElementNS(SVG, name);
    for (const [key, value] of Object.entries(attributes)) {
      created.setAttribute(key, value);
    }
    if (parent) {
      parent.appendChild(created);
    }
    return created;
  }

  function html(name, text, parent, className) {
    const created = document.createElement(name);
    if (text !== undefined && text !== null) {
      created.textContent = text;
    }
    if (className) {
      created.className = className;
    }
    if (parent) {
      parent.appendChild(created);
    }
    return created;
  }

  function polygon(points, half) {
    return points.map(([x, y]) => `${x * half},${y * half}`).join(" ");
  }

  function shapeOf(node, group) {
    const half = node.size / 2;
    if (node.shape === "rounded_square") {
      return element("rect", { x: -half, y: -half, width: node.size, height: node.size, rx: half / 2 }, group);
    }
    if (node.shape === "diamond") {
      return element("polygon", { points: polygon([[0, -1], [1, 0], [0, 1], [-1, 0]], half) }, group);
    }
    if (node.shape === "hexagon") {
      return element("polygon", { points: polygon([[-0.5, -1], [0.5, -1], [1, 0], [0.5, 1], [-0.5, 1], [-1, 0]], half) }, group);
    }
    return element("circle", { r: half }, group);
  }

  function drawEdges() {
    for (const edge of data.edges) {
      const source = nodes.get(edge.source);
      const target = nodes.get(edge.target);
      const line = element("line", {
        x1: source.x, y1: source.y, x2: target.x, y2: target.y,
        class: `edge ${edge.kind}`,
      }, edgeLayer);
      if (edge.kind === "directs") {
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const length = Math.hypot(dx, dy) || 1;
        const inset = target.size / 2 + 4;
        line.setAttribute("x2", target.x - (dx / length) * inset);
        line.setAttribute("y2", target.y - (dy / length) * inset);
        line.setAttribute("marker-end", "url(#arrow)");
      }
      element("title", {}, line).textContent = `${source.label} : ${edge.label} : ${target.label}`;
      edges.push({ edge, line });
    }
  }

  function drawNodes() {
    for (const node of data.nodes) {
      const group = element("g", {
        class: `node ${node.kind}${node.closed ? " closed" : ""}`,
        transform: `translate(${node.x} ${node.y})`,
      }, nodeLayer);
      if (node.severity) {
        element("circle", { r: node.size / 2 + 6, class: `ring ${node.severity}` }, group);
      }
      if (node.closed) {
        shapeOf(node, group).setAttribute("class", "underlay");
      }
      shapeOf(node, group).setAttribute("class", "shape");
      const text = element("text", { y: node.size / 2 + 16 }, group);
      text.textContent = node.label.split("\n")[0];
      element("title", {}, group).textContent = `${node.label.replaceAll("\n", " ")}, ${node.kindLabel}`;
      group.addEventListener("click", (event) => {
        event.stopPropagation();
        select(node.id, false);
      });
      shapes.set(node.id, group);
    }
  }

  function fillList() {
    const sorted = [...data.nodes].sort((first, second) => first.label.localeCompare(second.label, "fr"));
    for (const node of sorted) {
      const item = html("li", null, list);
      const button = html("button", null, item);
      button.type = "button";
      const swatch = html("span", null, button, `swatch ${node.kind.replace("_", "-")}`);
      swatch.setAttribute("aria-hidden", "true");
      html("span", node.label.replaceAll("\n", " "), button);
      button.setAttribute("aria-label", `${node.label.replaceAll("\n", " ")}, ${node.kindLabel}`);
      button.addEventListener("click", () => select(node.id, true));
      buttons.set(node.id, { item, button, node });
    }
    filterList();
  }

  function filterList() {
    const query = search.value.trim().toLocaleLowerCase("fr");
    let shown = 0;
    for (const { item, node } of buttons.values()) {
      const haystack = [node.label, node.kindLabel, ...(node.facts || [])].join(" ").toLocaleLowerCase("fr");
      const visible = !query || haystack.includes(query);
      item.hidden = !visible;
      shown += visible ? 1 : 0;
    }
    searchStatus.textContent = `${shown} entité${shown > 1 ? "s" : ""} sur ${buttons.size}`;
  }

  function apply(animated) {
    viewport.classList.toggle("animated", animated);
    viewport.setAttribute("transform", `translate(${view.x} ${view.y}) scale(${view.scale})`);
  }

  function bounds() {
    const xs = data.nodes.map((node) => node.x);
    const ys = data.nodes.map((node) => node.y);
    return {
      left: Math.min(...xs) - MARGIN, right: Math.max(...xs) + MARGIN,
      top: Math.min(...ys) - MARGIN, bottom: Math.max(...ys) + MARGIN,
    };
  }

  function fit(animated) {
    if (!data.nodes.length) {
      return;
    }
    const box = bounds();
    const width = svg.clientWidth || 800;
    const height = svg.clientHeight || 600;
    view.scale = Math.min(width / (box.right - box.left), height / (box.bottom - box.top), 2);
    view.x = width / 2 - ((box.left + box.right) / 2) * view.scale;
    view.y = height / 2 - ((box.top + box.bottom) / 2) * view.scale;
    apply(animated);
  }

  function zoom(factor, centreX, centreY) {
    const x = centreX === undefined ? (svg.clientWidth || 800) / 2 : centreX;
    const y = centreY === undefined ? (svg.clientHeight || 600) / 2 : centreY;
    const scale = Math.min(Math.max(view.scale * factor, 0.1), 6);
    view.x = x - ((x - view.x) * scale) / view.scale;
    view.y = y - ((y - view.y) * scale) / view.scale;
    view.scale = scale;
    apply(false);
  }

  function centreOn(node) {
    view.x = (svg.clientWidth || 800) / 2 - node.x * view.scale;
    view.y = (svg.clientHeight || 600) / 2 - node.y * view.scale;
    apply(true);
  }

  function section(title, parent) {
    html("h3", title, parent);
    return html("ul", null, parent);
  }

  function externalLink(text, url, parent) {
    const link = html("a", text, parent);
    link.href = url;
    link.rel = "noreferrer noopener";
    link.target = "_blank";
    return link;
  }

  function showDetails(node) {
    details.replaceChildren();
    html("p", node.name || node.label.replaceAll("\n", " "), details, "question");
    html("p", [node.kindLabel, ...(node.facts || [])].join(" · "), details, "muted");
    if (node.verdict) {
      const verdict = html("p", null, details);
      html("strong", `Verdict : ${node.verdict.label}`, verdict);
      if (node.verdict.reason) {
        verdict.append(`, ${node.verdict.reason}`);
      }
    }
    if (node.tags && node.tags.length) {
      html("p", `Tags : ${node.tags.join(", ")}`, details);
    }
    if (node.links && node.links.length) {
      const links = section("Liens", details);
      for (const link of node.links) {
        const item = html("li", `${link.role} : `, links);
        const button = html("button", link.label.replaceAll("\n", " "), item, "link-button");
        button.type = "button";
        button.addEventListener("click", () => select(link.id, true));
        if (link.closed) {
          item.append(" (fermé)");
        }
      }
    }
    if (node.signals && node.signals.length) {
      const signals = section("Signaux", details);
      for (const signal of node.signals) {
        const item = html("li", null, signals);
        html("span", signal.severity, item, `badge ${signal.level}`);
        item.append(` ${signal.title}, score ${signal.score}. `);
        if (signal.explanation) {
          item.append(signal.explanation);
        }
      }
    }
    if (node.note) {
      html("h3", "Note", details);
      html("p", node.note, details, "note");
    }
    if (node.notices && node.notices.length) {
      const notices = section("Annonces BODACC", details);
      for (const notice of node.notices) {
        const item = html("li", `${notice.date}, ${notice.family}${notice.summary ? ` : ${notice.summary}` : ""} `, notices);
        externalLink("annonce", notice.url, item);
      }
    }
    if (node.sources && node.sources.length) {
      const sources = section("Sources", details);
      for (const source of node.sources) {
        const item = html("li", `${source.name}, collecté le ${source.date} `, sources);
        externalLink("réponse", source.url, item);
      }
    }
  }

  function highlight(identifier) {
    const neighbours = new Set([identifier]);
    for (const { edge, line } of edges) {
      const touches = edge.source === identifier || edge.target === identifier;
      line.classList.toggle("highlighted", touches);
      line.classList.toggle("faded", !touches);
      if (touches) {
        neighbours.add(edge.source);
        neighbours.add(edge.target);
      }
    }
    for (const [id, group] of shapes) {
      group.classList.toggle("faded", !neighbours.has(id));
      group.classList.toggle("selected", id === identifier);
    }
  }

  function select(identifier, centre) {
    const node = nodes.get(identifier);
    if (!node) {
      return;
    }
    selected = identifier;
    for (const [id, { button }] of buttons) {
      button.setAttribute("aria-current", id === identifier ? "true" : "false");
    }
    highlight(identifier);
    showDetails(node);
    if (centre) {
      centreOn(node);
    }
    document.getElementById("details-heading").focus({ preventScroll: true });
  }

  function clearSelection() {
    selected = null;
    for (const { line } of edges) {
      line.classList.remove("highlighted", "faded");
    }
    for (const group of shapes.values()) {
      group.classList.remove("faded", "selected");
    }
  }

  function setTheme(index) {
    themeIndex = index;
    const theme = THEMES[index];
    if (theme.value) {
      document.documentElement.dataset.theme = theme.value;
    } else {
      delete document.documentElement.dataset.theme;
    }
    document.getElementById("theme-button").textContent = theme.label;
    try {
      window.localStorage.setItem("lacis-theme", theme.value);
    } catch (error) {
      return;
    }
  }

  function storedTheme() {
    try {
      const value = window.localStorage.getItem("lacis-theme") || "";
      return Math.max(THEMES.findIndex((theme) => theme.value === value), 0);
    } catch (error) {
      return 0;
    }
  }

  function listenToPointer() {
    let drag = null;
    svg.addEventListener("pointerdown", (event) => {
      if (event.target.closest(".node")) {
        return;
      }
      drag = { x: event.clientX - view.x, y: event.clientY - view.y, moved: false };
      svg.setPointerCapture(event.pointerId);
      svg.classList.add("dragging");
    });
    svg.addEventListener("pointermove", (event) => {
      if (!drag) {
        return;
      }
      view.x = event.clientX - drag.x;
      view.y = event.clientY - drag.y;
      drag.moved = true;
      apply(false);
    });
    svg.addEventListener("pointerup", () => {
      if (drag && !drag.moved && selected) {
        clearSelection();
      }
      drag = null;
      svg.classList.remove("dragging");
    });
    svg.addEventListener("wheel", (event) => {
      event.preventDefault();
      const box = svg.getBoundingClientRect();
      zoom(event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP, event.clientX - box.left, event.clientY - box.top);
    }, { passive: false });
  }

  function start() {
    const investigation = data.investigation;
    document.getElementById("investigation-name").textContent = `Enquête ${investigation.name}`;
    document.getElementById("investigation-question").textContent = investigation.question;
    const coverage = investigation.filtered ? "la vue filtrée du graphe" : "toute l'enquête";
    document.getElementById("investigation-export").textContent =
      `Exporté le ${investigation.exported} par Lacis ${investigation.version}, à partir de ${coverage} : ${data.nodes.length} entités.`;
    drawEdges();
    drawNodes();
    fillList();
    search.addEventListener("input", filterList);
    document.getElementById("zoom-in").addEventListener("click", () => zoom(ZOOM_STEP));
    document.getElementById("zoom-out").addEventListener("click", () => zoom(1 / ZOOM_STEP));
    document.getElementById("zoom-fit").addEventListener("click", () => fit(true));
    document.getElementById("theme-button").addEventListener("click", () => setTheme((themeIndex + 1) % THEMES.length));
    listenToPointer();
    setTheme(storedTheme());
    window.addEventListener("resize", () => fit(false));
    fit(false);
  }

  start();
})();
