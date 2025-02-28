async function get_risk_oca(patient_id) {
  const params = new URLSearchParams({ patient_id });
  const response = await fetch(`/risk_oca?${params}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  return await response.json();
}

async function load_risk_oca(element, patient_id) {
  if (!patient_id || patient_id == "None") {
    element.style.display = "none";
    return;
  }

  const data = await get_risk_oca(patient_id);
  if (data.error) {
    element.style.display = "none";
    return;
  }
  date_string = "";
  if (data.latest) {
    date_string = format_date(data.latest);
  }

  if (data.risk == 0) {
    element.style.display = "inline";
    element.textContent = `✅(${date_string})`;
  } else if (data.risk == 1) {
    element.style.display = "inline";
    element.textContent = `⚠️(${date_string})`;
  } else if (data.risk == 2) {
    element.style.display = "inline";
    element.textContent = `❌`;
  } else {
    element.style.display = "none";
  }
}

function format_date(date) {
  const parsedDate = new Date(Date.parse(date));
  const year = parsedDate.getFullYear();
  const month = `0${parsedDate.getMonth() + 1}`.slice(-2);
  const day = `0${parsedDate.getDate()}`.slice(-2);

  return [year, month, day].join("-");
}
