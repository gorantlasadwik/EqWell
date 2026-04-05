(function () {
  var root = document.body;
  var drawer = document.querySelector('[data-mobile-drawer]');
  var openButtons = document.querySelectorAll('[data-mobile-open]');
  var closeButtons = document.querySelectorAll('[data-mobile-close]');

  if (!root || !drawer || !openButtons.length || !closeButtons.length) {
    return;
  }

  var setOpen = function (isOpen) {
    root.classList.toggle('mobile-menu-open', isOpen);
    drawer.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
  };

  openButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      setOpen(true);
    });
  });

  closeButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      setOpen(false);
    });
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      setOpen(false);
    }
  });
})();