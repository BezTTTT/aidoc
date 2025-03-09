function format_date(dateString, time = false) {
  const date = new Date(dateString);
  const thYear = date.getFullYear() + 543;
  return `${('0' + date.getDate()).slice(-2)}/${('0' + (date.getMonth() + 1)).slice(-2)}/${thYear} ${time ? `${('0' + date.getHours()).slice(-2)}:${('0' + date.getMinutes()).slice(-2)}น.` : ''}`;
}

show_risk_oca = function (element, data) {
  console.log(data);
  let date_string = "";
  if (data.latest != "None" && data.latest != "") {
    date_string = `(${format_date(data.latest, time=true)})`;
  }

  element.classList.remove("text-success", "text-warning", "text-danger");

  element.style.display = "inline";
  element.setAttribute("data-displayed", "true");

  let icon = "";
  let tooltipMessage = "";
  
  if (data.risk == 0 && data.risk != "") {
    icon = `✅`;
    tooltipMessage = `ข้อมูล Risk OCA เป็นปัจจุบัน </br>${date_string}`;
  } else if (data.risk == 1 && data.risk != "") {
    icon = `⚠️`;
    tooltipMessage = `ข้อมูล Risk OCA ไม่เป็นปัจจุบัน<br>(มากกว่า 6 เดือน)</br>${date_string}`;
  } else {
    icon = `❌`;
    tooltipMessage = `ไม่มีข้อมูล Risk OCA`;
  }

  element.textContent = icon;

  element.setAttribute("data-toggle", "tooltip");
  element.setAttribute("title", tooltipMessage);

  $(element).tooltip({
    html: true,
    sanitize: false,
  });

  element.addEventListener("mouseenter", () => {
    $(element).tooltip("show");
  });

  element.addEventListener("mouseleave", () => {
    $(element).tooltip("hide");
  });
};

document.addEventListener("DOMContentLoaded", function () {
  $('[data-toggle="tooltip"]').tooltip();
});

function sync_risk_oca(button) {
  button.disabled = true;
  button.textContent = "กำลังซิงค์ข้อมูล...";
  fetch(`/sync_risk_oca`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })
    .then((response) => {
      if (!response.ok) {
        alert("เกิดข้อผิดพลาดในการ Sync Risk OCA");
        return;
      }
      
      response.json().then((data) => {
        load_sync_risk_oca_tooltip(button, data);
      })
    })
    .catch((error) => {
      console.error("Error:", error);
      alert("เกิดข้อผิดพลาดในการ Sync Risk OCA");
    })
    .finally(() => {
      button.textContent = "ซิงค์ข้อมูล Risk OCA";
      button.disabled = false;
    });
}

function load_sync_risk_oca_tooltip(button, sync_data) {
  console.log(sync_data)
  button.classList.add("btn", "btn-outline-primary");
  button.setAttribute("data-bs-toggle", "tooltip");
  button.setAttribute(
    "title",
    `${sync_data.update_date != "None" ? `ซิงค์ล่าสุด: ${format_date(sync_data.update_date, time=true)}` : 'ไม่มีการซิงค์ข้อมูล'} ${sync_data.update_count != "None" ? `จำนวน: ${sync_data.update_count} รายการ` : ''}`
  );
  let tooltip = new bootstrap.Tooltip(button, {
    html: true,
    sanitize: false,
  });
  button.addEventListener("mouseleave", () => {
    tooltip.hide();
  });
}
