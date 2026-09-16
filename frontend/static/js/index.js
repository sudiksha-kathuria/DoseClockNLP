/*
 * index.js
 * --------
 * Behaviour for the add-medicine form:
 *   - lets the user add/remove multiple "time of day" rows
 *   - submits the form as JSON to /add_medicine
 *   - shows a small toast + redirects to the clock view on success
 */

const timesList = document.getElementById("times-list");
const addTimeBtn = document.getElementById("add-time-btn");
const form = document.getElementById("medicine-form");
const formError = document.getElementById("form-error");
const toast = document.getElementById("toast");

function showToast(message) {
  toast.textContent = message;
  toast.classList.add("visible");
  setTimeout(() => toast.classList.remove("visible"), 2200);
}

function showFormError(message) {
  if (!message) {
    formError.style.display = "none";
    formError.textContent = "";
    return;
  }
  formError.textContent = message;
  formError.style.display = "block";
}

function makeTimeRow(value) {
  const row = document.createElement("div");
  row.className = "time-row";

  const input = document.createElement("input");
  input.type = "time";
  input.name = "times";
  input.required = true;
  input.value = value || "20:00";

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "remove-time";
  removeBtn.title = "Remove";
  removeBtn.innerHTML = "&times;";
  removeBtn.addEventListener("click", () => {
    // Always keep at least one time row.
    if (timesList.children.length > 1) {
      row.remove();
    }
  });

  row.appendChild(input);
  row.appendChild(removeBtn);
  return row;
}

// Wire the remove button already present on the first row.
timesList.querySelector(".remove-time").addEventListener("click", () => {
  if (timesList.children.length > 1) {
    timesList.children[0].remove();
  }
});

addTimeBtn.addEventListener("click", () => {
  timesList.appendChild(makeTimeRow());
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  showFormError(null);

  const medicineName = document.getElementById("medicine_name").value.trim();
  const days = document.getElementById("days").value;
  const language = document.getElementById("language").value;
  const times = Array.from(timesList.querySelectorAll('input[name="times"]')).map((i) => i.value);

  try {
    const response = await fetch("/add_medicine", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ medicine_name: medicineName, times, days, language }),
    });
    const result = await response.json();

    if (!response.ok) {
      showFormError(result.error || "Something went wrong. Please try again.");
      return;
    }

    showToast("Reminder saved");
    setTimeout(() => {
      window.location.href = "/clock";
    }, 600);
  } catch (err) {
    showFormError("Could not reach the server. Please try again.");
  }
});
