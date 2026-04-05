(function () {
  var body = document.body;
  var drawer = document.querySelector('[data-mq-drawer]');
  var openers = document.querySelectorAll('[data-mq-open]');
  var closers = document.querySelectorAll('[data-mq-close]');

  if (!body || !drawer) {
    return;
  }

  function setOpen(open) {
    body.classList.toggle('mq-open', open);
    drawer.setAttribute('aria-hidden', open ? 'false' : 'true');
  }

  openers.forEach(function (button) {
    button.addEventListener('click', function () {
      setOpen(true);
    });
  });

  closers.forEach(function (button) {
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