const API = "https://ai-powered-code-review-collaboration-yzum.onrender.com";

const form        = document.getElementById("login-form");
const emailInput  = document.getElementById("email");
const passInput   = document.getElementById("password");
const submitBtn   = document.getElementById("submit-btn");
const btnText     = document.getElementById("btn-text");
const btnSpinner  = document.getElementById("btn-spinner");
const formAlert   = document.getElementById("form-alert");

const token = localStorage.getItem("token");

if (token) {
    try {
        const payload = JSON.parse(atob(token.split(".")[1]));

        const currentTime = Date.now() / 1000;

        if (payload.exp > currentTime) {
            const params = new URLSearchParams(window.location.search);
            const next = params.get("next");
            window.location.href = next ? next : "/dashboard";
        } else {
            localStorage.removeItem("token");
            localStorage.removeItem("user");
        }
    } catch {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
    }
}

function setFieldError(fieldId, message) {
  const errEl = document.getElementById(fieldId + "-error");
  if (errEl) errEl.textContent = message;
  const input = document.getElementById(fieldId);
  if (input) {
    if (message) input.classList.add("error");
    else input.classList.remove("error");
  }
}

function clearErrors() {
  setFieldError("email", "");
  setFieldError("password", "");
  hideAlert();
}

function showAlert(message, type = "error") {
  formAlert.textContent = message;
  formAlert.className = "form-alert alert-" + type;
  formAlert.style.display = "block";
}

function hideAlert() {
  formAlert.style.display = "none";
  formAlert.textContent = "";
}

function setLoading(loading) {
  submitBtn.disabled = loading;
  btnText.style.display    = loading ? "none" : "inline";
  btnSpinner.style.display = loading ? "inline-block" : "none";
}

function validate() {
  let valid = true;

  const email    = emailInput.value.trim();
  const password = passInput.value;

  if (!email) {
    setFieldError("email", "Email is required.");
    valid = false;
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    setFieldError("email", "Enter a valid email address.");
    valid = false;
  }

  if (!password) {
    setFieldError("password", "Password is required.");
    valid = false;
  }

  return valid;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearErrors();

  if (!validate()) return;

  setLoading(true);

  const body = new URLSearchParams();
  body.append("username", emailInput.value.trim()); 
  body.append("password", passInput.value);

  try {
    const res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString()
    });

    const data = await res.json();

    if (!res.ok) {
      const detail = data.detail || "Login failed. Check your credentials.";
      showAlert(detail, "error");
      return;
    }

localStorage.setItem("token", data.access_token);

const payload = JSON.parse(
    atob(data.access_token.split(".")[1])
);

const userInfo = {
    user_id: payload.user_id,
    username: payload.username,
    email: payload.email,
    role: payload.role
};

localStorage.setItem(
    "user",
    JSON.stringify(userInfo)
);

console.log("Logged In User:", userInfo);

showAlert(
    "Login successful! Redirecting...",
    "success"
);

setTimeout(() => {
    const params = new URLSearchParams(window.location.search);
    const nextUrl = params.get("next");
    if (nextUrl) {
        window.location.replace(nextUrl);
    } else if (userInfo.role === "admin") {
        window.location.replace("/admin");
    } else {
        window.location.replace("/dashboard");
    }
}, 1000);

  } catch (err) {
    showAlert("Could not connect to the server. Make sure the backend is running.", "error");
  } finally {
    setLoading(false);
  }
});

[emailInput, passInput].forEach(el => {
  el.addEventListener("input", () => {
    setFieldError(el.id, "");
    el.classList.remove("error");
    hideAlert();
  });
});
