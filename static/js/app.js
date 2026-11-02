// Business ERP - Modern Interactive JS
document.addEventListener("DOMContentLoaded", () => {
  // 1. Mobile Sidebar Toggle & Safe Navigation
  const sidebar = document.getElementById("appNav");
  const toggleBtn = document.querySelector(".menu-toggle");
  
  if (sidebar && toggleBtn) {
    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      sidebar.classList.toggle("show");
    });

    // Close when clicking outside on mobile
    document.addEventListener("click", (e) => {
      if (window.innerWidth < 992 && sidebar.classList.contains("show")) {
        if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
          sidebar.classList.remove("show");
        }
      }
    });

    // Close sidebar immediately when a link is clicked on mobile so navigation happens cleanly
    sidebar.querySelectorAll("a").forEach(link => {
      link.addEventListener("click", () => {
        if (window.innerWidth < 992) {
          sidebar.classList.remove("show");
        }
      });
    });
  }

  // 2. Invoice Real-time Calculator
  const calculator = document.querySelector('.invoice-calculator');
  if (calculator) {
    const update = () => {
      const getVal = name => parseFloat(calculator.querySelector(`[name="${name}"]`)?.value) || 0;
      const qty = getVal('quantity');
      const price = getVal('unit_price');
      const gst = getVal('gst_percent');
      const subtotal = qty * price;
      const total = subtotal * (1 + gst / 100);
      const totalEl = calculator.querySelector('[data-invoice-total]');
      if (totalEl) {
        totalEl.textContent = `₹${total.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
      }
    };
    calculator.querySelectorAll('.calc-input').forEach(i => i.addEventListener('input', update));
    update();
  }

  // 3. Form Submit Loading Protection
  document.querySelectorAll("form").forEach(form => {
    form.addEventListener("submit", (e) => {
      const button = form.querySelector('button[type="submit"], button:not([type])');
      if (button && !button.dataset.noLoading) {
        button.dataset.originalText = button.innerHTML;
        button.disabled = true;
        button.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span> Saving…';
        // Safety timeout to avoid eternal disabled state if validation fails
        setTimeout(() => {
          if (button.disabled) {
            button.disabled = false;
            button.innerHTML = button.dataset.originalText;
          }
        }, 8000);
      }
    });
  });

  // 4. Global CSV Exporter
  window.exportTableToCSV = function (tableId, filename = "report.csv") {
    const table = document.getElementById(tableId);
    if (!table) return;
    const rows = Array.from(table.querySelectorAll("tr"));
    const csvContent = rows.map(row => {
      const cells = Array.from(row.querySelectorAll("th, td"));
      // filter out action columns with dots or buttons
      return cells
        .filter(c => !c.classList.contains("no-export"))
        .map(c => {
          let text = c.innerText.replace(/"/g, '""').trim();
          return `"${text}"`;
        }).join(",");
    }).join("\n");

    const blob = new Blob(["\ufeff" + csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    link.click();
  };
});
