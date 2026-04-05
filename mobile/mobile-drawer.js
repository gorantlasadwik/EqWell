(function () {
  function createEl(tag, className, html) {
    var el = document.createElement(tag);
    if (className) {
      el.className = className;
    }
    if (typeof html === "string") {
      el.innerHTML = html;
    }
    return el;
  }

  function textFromNode(node) {
    if (!node) {
      return "";
    }
    return String(node.textContent || "").trim();
  }

  function buildAppBar(brand, subtitle) {
    var bar = createEl("header", "mobile-appbar");
    bar.innerHTML =
      '<button type="button" class="mobile-icon-btn" aria-label="Open menu" data-drawer-open>' +
      '<span class="material-symbols-outlined">menu</span>' +
      "</button>" +
      '<div class="mobile-appbar-brand">' +
      '<strong class="mobile-appbar-title">' + brand + "</strong>" +
      '<span class="mobile-appbar-subtitle">' + subtitle + "</span>" +
      "</div>" +
      '<button type="button" class="mobile-icon-btn" aria-label="Open alerts">' +
      '<span class="material-symbols-outlined">notifications</span>' +
      "</button>";
    return bar;
  }

  function setupDrawer() {
    var aside = document.querySelector("aside");
    if (!aside) {
      return;
    }

    var body = document.body;
    body.classList.add("mobile-has-drawer");

    var drawerHead = createEl(
      "div",
      "mobile-drawer-head",
      '<span class="mobile-drawer-brand">EqWell</span>' +
        '<button type="button" class="mobile-drawer-close" aria-label="Close menu" data-drawer-close>' +
        '<span class="material-symbols-outlined">close</span>' +
        "</button>"
    );
    aside.insertBefore(drawerHead, aside.firstChild);

    var backdrop = createEl("div", "mobile-backdrop");
    backdrop.setAttribute("data-drawer-close", "");
    body.insertBefore(backdrop, body.firstChild);

    var titleNode = document.querySelector("main h1") || document.querySelector("main h2");
    var subtitleNode = document.querySelector("main p");
    var appBar = buildAppBar("EqWell", textFromNode(subtitleNode) || "Mobile Console");
    body.insertBefore(appBar, backdrop.nextSibling);

    function openDrawer() {
      body.classList.add("drawer-open");
    }

    function closeDrawer() {
      body.classList.remove("drawer-open");
    }

    body.addEventListener("click", function (event) {
      var target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      if (target.closest("[data-drawer-open]")) {
        openDrawer();
      }
      if (target.closest("[data-drawer-close]")) {
        closeDrawer();
      }
      if (target.closest("aside nav a")) {
        closeDrawer();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeDrawer();
      }
    });

    if (titleNode && titleNode.textContent) {
      var appbarSub = appBar.querySelector(".mobile-appbar-subtitle");
      if (appbarSub) {
        appbarSub.textContent = String(titleNode.textContent).trim().slice(0, 42);
      }
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupDrawer);
  } else {
    setupDrawer();
  }
})();
