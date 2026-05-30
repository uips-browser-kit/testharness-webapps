(function () {
  'use strict';

  var PAGE_SIZE = 15;
  var currentPage = 1;

  var metaEl = document.getElementById('list-meta');
  var dataEl = document.getElementById('list-data');
  if (!metaEl || !dataEl) return;

  var meta = JSON.parse(metaEl.textContent);
  var payload = JSON.parse(dataEl.textContent);
  var allRecords = payload.records;
  var allUrls = payload.row_urls || [];
  var columns = meta.columns || [];
  var filterFields = meta.filterable_fields || [];
  var formatters = window.LIST_FORMATTERS || {};

  // Build indexed dataset once so we can always retrieve the original row URL
  var indexed = allRecords.map(function (r, i) { return { r: r, i: i }; });

  // Inject filter inputs
  var filtersEl = document.getElementById('list-filters');
  var filterInputs = {};
  if (filtersEl && filterFields.length) {
    filterFields.forEach(function (field) {
      var label = field.replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
      var input = document.createElement('input');
      input.type = 'text';
      input.placeholder = 'Filter ' + label + '…';
      input.setAttribute('aria-label', 'Filter by ' + label);
      input.style.cssText = [
        'padding:4px 8px',
        'font-size:13px',
        'border:1px solid var(--sol-base01)',
        'background:var(--sol-base02)',
        'color:var(--sol-base1)',
        'border-radius:4px',
        'min-width:160px',
      ].join(';');
      input.addEventListener('input', function () { currentPage = 1; render(); });
      filterInputs[field] = input;
      filtersEl.appendChild(input);
    });
  }

  function applyFilters() {
    var active = Object.keys(filterInputs).map(function (field) {
      return { field: field, value: filterInputs[field].value.trim().toLowerCase() };
    }).filter(function (f) { return f.value !== ''; });

    if (!active.length) return indexed;

    return indexed.filter(function (item) {
      return active.every(function (f) {
        var cell = item.r[f.field];
        return String(cell != null ? cell : '').toLowerCase().indexOf(f.value) !== -1;
      });
    });
  }

  function cellText(r, col) {
    var v = r[col];
    if (formatters[col]) return formatters[col](v);
    return v != null ? String(v) : '';
  }

  function render() {
    var filtered = applyFilters();
    var totalPages = Math.ceil(filtered.length / PAGE_SIZE) || 1;
    if (currentPage > totalPages) currentPage = totalPages;
    var start = (currentPage - 1) * PAGE_SIZE;
    var page = filtered.slice(start, start + PAGE_SIZE);

    var badge = document.getElementById('record-count');
    if (badge) {
      badge.textContent = filtered.length === allRecords.length
        ? allRecords.length + ' records'
        : filtered.length + ' of ' + allRecords.length + ' records';
    }

    var tbody = document.getElementById('list-body');
    if (!tbody) return;
    tbody.innerHTML = '';

    page.forEach(function (item) {
      var tr = document.createElement('tr');
      var url = allUrls[item.i] || '';
      columns.forEach(function (col, ci) {
        var td = document.createElement('td');
        var text = cellText(item.r, col);
        if (ci === 0 && url) {
          var a = document.createElement('a');
          a.href = url;
          a.textContent = text;
          td.appendChild(a);
        } else {
          td.textContent = text;
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });

    renderPagination(totalPages);
  }

  function renderPagination(totalPages) {
    var el = document.getElementById('list-pagination');
    if (!el) return;
    el.innerHTML = '';
    if (totalPages <= 1) return;

    var btn = function (label, disabled, onClick) {
      var b = document.createElement('button');
      b.textContent = label;
      b.disabled = disabled;
      b.style.cssText = 'padding:4px 10px;font-size:13px;cursor:pointer;';
      if (!disabled) b.addEventListener('click', onClick);
      return b;
    };

    el.appendChild(btn('← Prev', currentPage === 1, function () { currentPage--; render(); }));

    var info = document.createElement('span');
    info.textContent = 'Page ' + currentPage + ' of ' + totalPages;
    info.style.cssText = 'margin:0 0.75rem;font-size:13px;color:var(--sol-base1);';
    el.appendChild(info);

    el.appendChild(btn('Next →', currentPage === totalPages, function () { currentPage++; render(); }));
  }

  render();
})();
