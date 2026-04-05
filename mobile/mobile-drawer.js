(function () {
  function setupMobileDrawer() {
    var body = document.body;
    var drawer = document.querySelector("[data-mobile-drawer]");
    if (!drawer) {
      return;
    }

    var openTriggers = Array.prototype.slice.call(document.querySelectorAll("[data-mobile-open]"));
    var closeTriggers = Array.prototype.slice.call(document.querySelectorAll("[data-mobile-close]"));

    function syncDrawerState(isOpen) {
      body.classList.toggle("mobile-menu-open", isOpen);
      drawer.setAttribute("aria-hidden", isOpen ? "false" : "true");
      body.style.overflow = isOpen ? "hidden" : "";
    }

    function openDrawer() {
      syncDrawerState(true);
    }

    function closeDrawer() {
      syncDrawerState(false);
    }

    openTriggers.forEach(function (trigger) {
      trigger.addEventListener("click", openDrawer);
    });

    closeTriggers.forEach(function (trigger) {
      trigger.addEventListener("click", closeDrawer);
    });

    drawer.addEventListener("click", function (event) {
      var target = event.target;
      if (!(target instanceof Element)) {
        return;
      }
      if (target.closest("a")) {
        closeDrawer();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeDrawer();
      }
    });

    syncDrawerState(false);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupMobileDrawer);
  } else {
    setupMobileDrawer();
  }
})();
