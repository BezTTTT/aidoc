const cacheDuration = 10 * 60 * 1000; // 10 minutes

async function get_risk_oca(patient_id) {
  const params = new URLSearchParams({ patient_id });
  const response = await fetch(`/risk_oca?${params}`, {
    method: "GET",
    headers: {
      "Content-Type": "application/json",
    },
  });

  const data = await response.json();
  return { data };
}

async function load_risk_oca(element, patient_id) {
  if (!patient_id || patient_id == "None" || patient_id == "") {
    element.style.display = "none";
    return;
  }

  const cacheKey = `/risk_oca?patient_id=${patient_id}`;
  const cache = await caches.open("risk-oca-cache");

  const cachedResponse = await cache.match(cacheKey);
  if (cachedResponse) {
    const cachedData = await cachedResponse.json();
    show_risk_oca(element, cachedData.data);

    if (Date.now() - cachedData.timestamp > cacheDuration) {
      await cache.delete(cacheKey);
    }
  }

  try {
    const { data } = await get_risk_oca(patient_id);
    if (data.error) {
      element.style.display = "none";
      return;
    }
    show_risk_oca(element, data);

    // Update cache
    const freshData = { data, timestamp: Date.now() };
    const responseToCache = new Response(JSON.stringify(freshData));
    await cache.put(cacheKey, responseToCache);
  } catch (error) {
    if (!element.hasAttribute("data-displayed")) {
      element.style.display = "none";
    }
  }
}

function show_risk_oca(element, data) {
  let date_string = "";
  if (data.latest) {
    date_string = format_date(data.latest);
  }

  element.classList.remove("text-success", "text-warning", "text-danger");

  element.style.display = "inline";
  element.setAttribute("data-displayed", "true");

  if (data.risk === 0) {
    element.textContent = `✅(${date_string})`;
    element.title = `ข้อมูล Risk OCA เป็นปัจจุบัน`;
    element.classList.add("text-success");
  } else if (data.risk === 1) {
    element.textContent = `⚠️(${date_string})`;
    element.title = `ข้อมูล Risk OCA ไม่เป็นปัจจุบัน (มากกว่า 6 เดือน)`;
    element.classList.add("text-warning");
  } else {
    element.textContent = `❌`;
    element.title = `ไม่มีข้อมูล Risk OCA`;
    element.classList.add("text-danger");
  }
}

function format_date(date) {
  return new Date(Date.parse(date)).toISOString().split("T")[0]; // YYYY-MM-DD format
}
