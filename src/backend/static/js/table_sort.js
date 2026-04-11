document.addEventListener("DOMContentLoaded", () => {
    if (performance.navigation.type === performance.navigation.TYPE_BACK_FORWARD) {
      window.location.reload();
    }
    const selectOrderBy = document.getElementById('update_order_by');
    const applyOrderButton = document.getElementById('apply_order_button');

    // Update dropdown value dynamically based on `sort_by`
    const currentSortBy = "{{ sort_by|default:'' }}";
    if (selectOrderBy) {
      [...selectOrderBy.options].forEach(option => {
        if (option.value === currentSortBy) {
          option.selected = true;
        }
      });
    }
    // Handle dropdown change
    selectOrderBy.addEventListener('change', () => {
      console.log('Order selected:', selectOrderBy.value);
      applyOrderButton.click();
    });
  });
