document.addEventListener('DOMContentLoaded', function () {
  const tabletSearchForms = document.querySelectorAll('[data-vm-tablet-search-form]');

  tabletSearchForms.forEach(function (form) {
    const input = form.querySelector('input[name="q"]');
    const resultsBox = form.querySelector('[data-vm-tablet-search-results]');
    if (!input || !resultsBox || !input.dataset.searchUrl) {
      return;
    }

    const searchUrl = input.dataset.searchUrl;
    const placeholderImage = input.dataset.placeholderImage || '';
    let debounceTimer;

    const clearResults = function () {
      resultsBox.innerHTML = '';
      resultsBox.classList.remove('is-open');
    };

    const renderResults = function (items) {
      if (!items.length) {
        resultsBox.innerHTML = '<div class="vm-tablet-alt-search__empty">No products found.</div>';
        resultsBox.classList.add('is-open');
        return;
      }

      resultsBox.innerHTML = items.map(function (item) {
        const imageUrl = item.image_url || placeholderImage;
        return '<a class="vm-tablet-alt-search__item" href="' + item.url + '">' +
          '<img src="' + imageUrl + '" alt="' + item.name + '">' +
          '<span class="vm-tablet-alt-search__meta">' +
          '<span class="vm-tablet-alt-search__name">' + item.name + '</span>' +
          '<span class="vm-tablet-alt-search__price">&#8377;' + item.price_display + '</span>' +
          '</span>' +
          '</a>';
      }).join('');
      resultsBox.classList.add('is-open');
    };

    input.addEventListener('input', function () {
      const query = input.value.trim();
      if (query.length < 2) {
        clearResults();
        return;
      }

      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        fetch(searchUrl + '?q=' + encodeURIComponent(query))
          .then(function (response) { return response.json(); })
          .then(function (data) { renderResults(data.results || []); })
          .catch(function () {
            resultsBox.innerHTML = '<div class="vm-tablet-alt-search__empty">Unable to search right now.</div>';
            resultsBox.classList.add('is-open');
          });
      }, 250);
    });

    document.addEventListener('click', function (event) {
      if (!form.contains(event.target)) {
        clearResults();
      }
    });
  });
});
