(function (global) {
  'use strict';

  function isObject(value) {
    return value && typeof value === 'object' && !Array.isArray(value);
  }

  function mergeDeep(base, override) {
    var output = {};
    var key;

    if (isObject(base)) {
      for (key in base) {
        if (Object.prototype.hasOwnProperty.call(base, key)) {
          output[key] = base[key];
        }
      }
    }

    if (!isObject(override)) {
      return output;
    }

    for (key in override) {
      if (!Object.prototype.hasOwnProperty.call(override, key)) {
        continue;
      }
      if (isObject(override[key]) && isObject(output[key])) {
        output[key] = mergeDeep(output[key], override[key]);
      } else {
        output[key] = override[key];
      }
    }

    return output;
  }

  var palette = Object.freeze({
    ink: '#1a1c22',
    muted: '#5f687b',
    slate: '#8f99ad',
    grid: 'rgba(95, 104, 123, 0.14)',
    gridStrong: 'rgba(95, 104, 123, 0.22)',
    blue: '#4f90b7',
    navy: '#355f8e',
    cyan: '#52a7d9',
    mint: '#4ba57a',
    amber: '#e0b54f',
    rose: '#d66a86',
    violet: '#8f74ce',
    green: '#63b27a',
    red: '#d7606f'
  });

  function rgba(hex, alpha) {
    var normalized = String(hex || '').replace('#', '').trim();
    if (normalized.length !== 6) {
      return 'rgba(79, 144, 183, ' + String(alpha) + ')';
    }
    var r = parseInt(normalized.slice(0, 2), 16);
    var g = parseInt(normalized.slice(2, 4), 16);
    var b = parseInt(normalized.slice(4, 6), 16);
    return 'rgba(' + String(r) + ', ' + String(g) + ', ' + String(b) + ', ' + String(alpha) + ')';
  }

  function applyDefaults() {
    if (!global.Chart || global.Chart.__eqwellFigmaThemeApplied) {
      return;
    }

    var Chart = global.Chart;
    Chart.__eqwellFigmaThemeApplied = true;

    Chart.defaults.color = palette.muted;
    Chart.defaults.font.family = 'Inter, Plus Jakarta Sans, sans-serif';
    Chart.defaults.font.size = 12;
    Chart.defaults.font.weight = '600';

    Chart.defaults.plugins.legend.labels.color = palette.ink;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.pointStyle = 'circle';
    Chart.defaults.plugins.legend.labels.boxWidth = 8;
    Chart.defaults.plugins.legend.labels.boxHeight = 8;
    Chart.defaults.plugins.legend.labels.padding = 14;

    Chart.defaults.plugins.tooltip.backgroundColor = '#11131a';
    Chart.defaults.plugins.tooltip.borderColor = '#273042';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.titleColor = '#f4f7fe';
    Chart.defaults.plugins.tooltip.bodyColor = '#d5def5';
    Chart.defaults.plugins.tooltip.padding = 12;
    Chart.defaults.plugins.tooltip.cornerRadius = 10;

    Chart.defaults.elements.line.borderWidth = 3;
    Chart.defaults.elements.line.tension = 0.34;
    Chart.defaults.elements.point.radius = 3;
    Chart.defaults.elements.point.hoverRadius = 5;
    Chart.defaults.elements.point.borderWidth = 2;
    Chart.defaults.elements.bar.borderRadius = 12;
    Chart.defaults.elements.bar.borderSkipped = false;
    Chart.defaults.elements.arc.borderWidth = 0;
  }

  function cartesianOptions(overrides) {
    var base = {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          labels: {
            color: palette.ink,
            font: { family: 'Inter', weight: '700', size: 11 }
          }
        }
      },
      scales: {
        x: {
          ticks: { color: palette.muted },
          grid: { color: palette.grid, drawBorder: false }
        },
        y: {
          beginAtZero: true,
          ticks: { color: palette.muted },
          grid: { color: palette.grid, drawBorder: false }
        }
      }
    };

    return mergeDeep(base, overrides || {});
  }

  function donutOptions(overrides) {
    var base = {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '66%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: palette.ink,
            font: { family: 'Inter', weight: '700', size: 11 }
          }
        }
      }
    };

    return mergeDeep(base, overrides || {});
  }

  function lineDataset(label, data, colorHex) {
    var keyColor = colorHex || palette.blue;
    return {
      label: String(label || ''),
      data: Array.isArray(data) ? data : [],
      borderColor: keyColor,
      backgroundColor: rgba(keyColor, 0.16),
      pointBackgroundColor: keyColor,
      pointBorderColor: '#ffffff',
      fill: true
    };
  }

  function barDataset(label, data, colorHex) {
    var keyColor = colorHex || palette.blue;
    return {
      label: String(label || ''),
      data: Array.isArray(data) ? data : [],
      backgroundColor: rgba(keyColor, 0.88),
      borderRadius: 12,
      borderSkipped: false
    };
  }

  global.EqWellChartTheme = {
    palette: palette,
    rgba: rgba,
    mergeDeep: mergeDeep,
    applyDefaults: applyDefaults,
    cartesianOptions: cartesianOptions,
    donutOptions: donutOptions,
    lineDataset: lineDataset,
    barDataset: barDataset
  };
})(window);
