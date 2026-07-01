const API = "https://ai-powered-code-review-collaboration-yzum.onrender.com";

const form          = document.getElementById("register-form");
const usernameInput = document.getElementById("username");
const emailInput    = document.getElementById("email");
const passwordInput = document.getElementById("password");
const roleSelect    = document.getElementById("role");
const submitBtn     = document.getElementById("submit-btn");
const btnText       = document.getElementById("btn-text");
const btnSpinner    = document.getElementById("btn-spinner");
const formAlert     = document.getElementById("form-alert");

function setFieldError(id, msg) {
  const errEl = document.getElementById(id + "-error");
  if (errEl) errEl.textContent = msg;
  const input = document.getElementById(id);
  if (input) input.classList.toggle("error", !!msg);
}

function clearErrors() {
  ["username", "email", "password", "role"].forEach(id => setFieldError(id, ""));
  hideAlert();
}

function showAlert(msg, type = "error") {
  formAlert.textContent   = msg;
  formAlert.className     = "form-alert alert-" + type;
  formAlert.style.display = "block";
}

function hideAlert() {
  formAlert.style.display = "none";
  formAlert.textContent   = "";
}

function setLoading(on) {
  submitBtn.disabled       = on;
  btnText.style.display    = on ? "none"         : "inline";
  btnSpinner.style.display = on ? "inline-block" : "none";
}

function validate() {
  let ok = true;

  const username = usernameInput.value.trim();
  const email    = emailInput.value.trim();
  const password = passwordInput.value;
  const role     = roleSelect.value;

  if (!username) {
    setFieldError("username", "Username is required.");
    ok = false;
  } else if (username.length < 3) {
    setFieldError("username", "Username must be at least 3 characters.");
    ok = false;
  }

  if (!email) {
    setFieldError("email", "Email is required.");
    ok = false;
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    setFieldError("email", "Enter a valid email address.");
    ok = false;
  }

  if (!password) {
    setFieldError("password", "Password is required.");
    ok = false;
  } else if (password.length < 6) {
    setFieldError("password", "Password must be at least 6 characters.");
    ok = false;
  }

  if (!role) {
    setFieldError("role", "Please select a role.");
    ok = false;
  }

  return ok;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearErrors();
  if (!validate()) return;

  setLoading(true);

  const payload = {
    username: usernameInput.value.trim(),
    email:    emailInput.value.trim(),
    password: passwordInput.value,
    role:     roleSelect.value
  };

  try {
    const res = await fetch(`${API}/auth/register`, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok) {
      showAlert(data.detail || "Registration failed. Please try again.", "error");
      return;
    }

    if (data.role === "admin") {
      showAlert(
        "Admin account created! You are the platform administrator. Redirecting to login…",
        "success"
      );
    } else {
      showAlert("Account created successfully! Redirecting to login…", "success");
    }
    
localStorage.removeItem("token");
localStorage.removeItem("user");

form.reset();

setTimeout(() => {
    window.location.href = "/login";
}, 1600);

  } catch (err) {
    showAlert("Could not connect to the server. Make sure the backend is running.", "error");
  } finally {
    setLoading(false);
  }
});

[usernameInput, emailInput, passwordInput, roleSelect].forEach(el => {
  el.addEventListener("input", () => {
    setFieldError(el.id, "");
    el.classList.remove("error");
    hideAlert();
  });
});
