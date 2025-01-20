const groupIdContainer = document.getElementById("groupIdContainer");
const supervisorContainer = document.getElementById("supervisorContainer");
const groupListLoadingSpinner = document.getElementById(
  "groupListLoadingSpinner"
);
const groupListContainer = document.getElementById("groupListContainer");
const groupList = document.getElementById("groupList");
const loadingSpinner = document.getElementById("loadingSpinner");
const searchContent = document.getElementById("searchContent");
const resultsContainer = document.getElementById("results");

const groupId = groupIdContainer.dataset.groupId;
const is_user_supervisor = supervisorContainer.dataset.userSupervisor;

let osmUsers = [];
let addedUsers = new Set(); // Tracks already added user IDs

function toggleSpinner(spinner, isLoading) {
  spinner.style.display = isLoading ? "block" : "none";
}

async function fetchGroupList() {
  if (!localStorage.getItem("firstLoadDone")) {
    toggleSpinner(groupListLoadingSpinner, true);
    groupListContainer.style.display = "none";
  }

  try {
    const response = await fetch(`/osm_hierarchy/group/${groupId}`);
    if (!response.ok) throw new Error("Failed to fetch group list");

    const { group_list } = await response.json();
    const fragment = document.createDocumentFragment();
    group_list.forEach((osm) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${osm.name} <span>${osm.surname}</span></td>
        <td>${osm.hospital}</td>
        <td>${osm.province}</td>
        <td>${osm.submission_count ? osm.submission_count : 0} รูป</td>
        ${
          is_user_supervisor == 1
            ? `<td>${
                osm.is_supervisor == 0
                  ? `<button class="btn btn-danger" onclick="removeUserFromGroup(${osm.osm_id}, this)">ลบ</button>`
                  : ""
              }</td>`
            : ""
        }
        `;
      fragment.appendChild(row);
    });

    groupList.innerHTML = ""; // Clear old rows
    groupList.appendChild(fragment);

    toggleSpinner(groupListLoadingSpinner, false);
    groupListContainer.style.display = "table";
    localStorage.setItem("firstLoadDone", "true"); // Mark first load as done
  } catch (error) {
    console.error("Error fetching group users:", error);
    toggleSpinner(groupListLoadingSpinner, false);
  }
}

async function loadAllUsers() {
  const searchModal = new bootstrap.Modal(
    document.getElementById("searchModal")
  );
  searchModal.show();

  toggleSpinner(loadingSpinner, true);
  searchContent.style.display = "none";

  try {
    const response = await fetch("/osm_hierarchy/get_osm_to_search");
    const data = await response.json();
    osmUsers = data.osm_users;

    toggleSpinner(loadingSpinner, false);
    searchContent.style.display = "block";

    document.getElementById("searchInput").value = "";
    searchUsers(); // Initialize results
  } catch (error) {
    console.error("Error fetching OSM users:", error);
    searchModal.hide();
  }
}

function searchUsers() {
  const query = document.getElementById("searchInput").value.toLowerCase();
  resultsContainer.innerHTML = "";

  if (query.length < 1) return;

  const filteredUsers = osmUsers.filter(
    (user) =>
      user.name.toLowerCase().includes(query) ||
      user.surname.toLowerCase().includes(query)
  );

  const fragment = document.createDocumentFragment();

  filteredUsers.forEach((user) => {
    const div = document.createElement("div");
    div.className =
      "d-flex justify-content-between align-items-center list-group-item";
    div.innerHTML = `
      <span>${user.name} ${user.surname}</span>
      <button class="btn btn-sm btn-primary" ${
        addedUsers.has(user.id)
          ? 'disabled style="cursor: not-allowed;"'
          : `onclick="addUserToGroup(${user.id}, this)"`
      }>
          ${addedUsers.has(user.id) ? "เพิ่มแล้ว" : "เพิ่ม"}
      </button>
    `;
    fragment.appendChild(div);
  });

  resultsContainer.appendChild(fragment);

  if (filteredUsers.length === 0) {
    resultsContainer.textContent = "ไม่พบผู้ใช้.";
  }
}

async function addUserToGroup(userId, button) {
  try {
    button.disabled = true;
    button.innerHTML = `
      <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
      กำลังเพิ่ม...
    `;

    const response = await fetch("/osm_hierarchy/add", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ user_id: userId, group_id: groupId }),
    });

    if (response.ok) {
      addedUsers.add(userId);
      button.disabled = true;
      button.textContent = "เพิ่มแล้ว";
      fetchGroupList(); // Refresh list after adding
    } else {
      console.error("Error adding user to group");
    }
  } catch (error) {
    console.error("Error adding user to group:", error);
  }
}

async function removeUserFromGroup(userId, button) {
  try {
    button.disabled = true;
    button.innerHTML = `
      <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
      กำลังลบ...
    `;

    const response = await fetch("/osm_hierarchy/remove", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ user_id: userId, group_id: groupId }),
    });

    if (response.ok) fetchGroupList(); // Refresh list after removing
  } catch (error) {
    console.error("Error removing user from group:", error);
  }
}

document.addEventListener("DOMContentLoaded", function () {
  localStorage.removeItem("firstLoadDone");
  fetchGroupList();
});
