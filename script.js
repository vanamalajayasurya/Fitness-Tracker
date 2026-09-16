const API = "";

const $ = (id) => document.getElementById(id);

/* ----------------------- API Helper ----------------------- */

async function call(path, options = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  const data = await res.json().catch(() => ({}));

  if (!res.ok) throw new Error(data.error || "Server error.");

  return data;
}

/* ----------------------- Messages ----------------------- */

function say(el, text, kind = "") {
  el.textContent = text;
  el.className = "msg" + (kind ? " " + kind : "");

  if (kind === "ok") {
    setTimeout(() => {
      el.textContent = "";
      el.className = "msg";
    }, 2500);
  }
}

/* ----------------------- HTML Escape (FIXED) ----------------------- */

function escapeHtml(text) {
  if (!text) return "";

  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

/* ----------------------- Muscle Groups ----------------------- */

async function loadGroups() {
  try {
    const groups = await call("/muscle-groups");

    $("muscle_group").innerHTML =
      `<option value="">Select Muscle Group</option>` +
      groups.map((g) => `<option value="${g}">${g}</option>`).join("");

    $("filter-group").innerHTML =
      `<option value="All">All</option>` +
      groups.map((g) => `<option value="${g}">${g}</option>`).join("");
  } catch (err) {
    console.error(err);
    say($("workout-msg"), "Unable to load muscle groups.", "err");
  }
}

/* ----------------------- Weekly Stats ----------------------- */

async function loadStats() {
  try {
    const s = await call("/stats");

    // Dashboard Cards
    $("stat-volume").textContent = Number(s.total_reps ?? 0).toLocaleString();
    $("stat-sets").textContent = Number(s.total_sets ?? 0);
    $("stat-sessions").textContent = Number(s.sessions ?? 0);

    $("stat-best").textContent = s.heaviest_lift
      ? `${s.heaviest_lift.weight_kg} kg`
      : "—";

    // Summary Line
    $("week-line").textContent = s.total_entries
      ? `${s.total_entries} workout entries • ${Number(s.total_reps ?? 0).toLocaleString()} reps completed across ${s.sessions} training day${s.sessions === 1 ? "" : "s"}`
      : "Your first workout starts here.";

    // Muscle Group Bars
    const bars = $("group-bars");
    const entries = Object.entries(s.volume_by_group || {});

    if (!entries.length) {
      bars.innerHTML =
        `<p class="empty">No workout data yet. Log your first workout.</p>`;
      return;
    }

    const max = Math.max(...entries.map(([, reps]) => Number(reps)), 1);

    bars.innerHTML = entries
      .sort((a, b) => Number(b[1]) - Number(a[1]))
      .map(([group, reps]) => `
        <div class="bar-row">
          <span>${group}</span>

          <span class="bar-track">
            <span class="bar-fill" style="width:${(Number(reps) / max) * 100}%"></span>
          </span>

          <span class="bar-value">
            ${Number(reps).toLocaleString()} reps
          </span>
        </div>
      `)
      .join("");

  } catch (err) {
    console.error("Stats Error:", err);
  }
}

/* ----------------------- Workout History ----------------------- */

async function loadWorkouts() {
  try {
    const group = $("filter-group").value || "All";

    const list = await call(
      "/workouts?muscle_group=" + encodeURIComponent(group)
    );

    const box = $("log-list");

    if (!list.length) {
      box.innerHTML = `<p class="empty">No workouts found.</p>`;
      return;
    }

    box.innerHTML = list
      .map(
        (w) => `
      <article class="entry">

        <div class="entry-main">
          <div class="entry-name">${escapeHtml(w.exercise)}</div>

          <div class="entry-meta">
            ${w.muscle_group} • ${w.date} • ${w.sets} × ${w.reps} @ ${
          w.weight_kg
        } kg
          </div>

          ${
            w.notes
              ? `<div class="entry-note">${escapeHtml(w.notes)}</div>`
              : ""
          }
        </div>

        <div class="entry-side">
          <span class="entry-volume">
            ${Number(w.total_reps ?? 0).toLocaleString()} reps
          </span>

          <button class="del" data-id="${w.id}">
            Delete
          </button>
        </div>

      </article>
    `
      )
      .join("");
  } catch (err) {
    console.error("Workout Error:", err);
  }
}

/* ----------------------- Save Workout ----------------------- */

$("workout-form").addEventListener("submit", async (event) => {
  event.preventDefault();

  const msg = $("workout-msg");

  if (!$("exercise").value.trim()) {
    say(msg, "Enter exercise name.", "err");
    return;
  }

  if (!$("muscle_group").value) {
    say(msg, "Select a muscle group.", "err");
    return;
  }

  const payload = {
    exercise: $("exercise").value.trim(),
    muscle_group: $("muscle_group").value,
    date: $("date").value,
    sets: Number($("sets").value),
    reps: Number($("reps").value),

    // FIXED (Safer)
    weight_kg: Number($("weight_kg").value || 0),

    notes: $("notes").value.trim(),
  };

  try {
    const saved = await call("/workouts", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    say(msg, `Workout saved! ${saved.total_reps} reps completed.`, "ok");

    // Reset Form
    $("exercise").value = "";
    $("notes").value = "";
    $("sets").value = 3;
    $("reps").value = 10;
    $("weight_kg").value = "";

    await Promise.all([loadStats(), loadWorkouts()]);
  } catch (err) {
    console.error(err);
    say(msg, err.message, "err");
  }
});

/* ----------------------- Delete Workout ----------------------- */

$("log-list").addEventListener("click", async (event) => {
  const button = event.target.closest(".del");

  if (!button) return;

  try {
    await call("/workouts/" + button.dataset.id, {
      method: "DELETE",
    });

    await Promise.all([loadStats(), loadWorkouts()]);
  } catch (err) {
    console.error(err);
    say($("workout-msg"), err.message, "err");
  }
});

/* ----------------------- Filter ----------------------- */

$("filter-group").addEventListener("change", loadWorkouts);

/* ----------------------- BMI Calculator ----------------------- */

$("bmi-form").addEventListener("submit", async (event) => {
  event.preventDefault();

  const msg = $("bmi-msg");

  try {
    const result = await call("/bmi", {
      method: "POST",
      body: JSON.stringify({
        height_cm: Number($("height_cm").value),
        weight_kg: Number($("bmi_weight").value),
      }),
    });

    $("bmi-result").hidden = false;

    $("bmi-value").textContent = result.bmi;
    $("bmi-category").textContent = result.category;
    $("bmi-advice").textContent = result.advice;

    $("bmi-range").textContent =
      `Healthy weight: ${result.healthy_weight_kg.min}–${result.healthy_weight_kg.max} kg`;

    $("bmi-marker").style.left = result.position_pct + "%";

    say(msg, "");
  } catch (err) {
    console.error(err);
    say(msg, err.message, "err");
  }
});

/* ----------------------- Start App ----------------------- */

(async function start() {
  $("date").value = new Date().toISOString().split("T")[0];

  try {
    await loadGroups();
    await Promise.all([loadStats(), loadWorkouts()]);
  } catch (err) {
    console.error(err);

    say(
      $("workout-msg"),
      "Backend not reachable. Start Flask with: python app.py",
      "err"
    );
  }
})();