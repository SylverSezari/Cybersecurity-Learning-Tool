const loginForm = document.getElementById("loginForm");
const loginError = document.getElementById("loginError");
const loginSubmit = document.getElementById("loginSubmit");

loginForm.addEventListener("submit", async (event) => {
	event.preventDefault();
	loginError.hidden = true;
	loginSubmit.disabled = true;
	loginSubmit.textContent = "Signing in...";

	const formData = new FormData(loginForm);

	try {
		const response = await fetch("/api/accounts/token", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				username: formData.get("username"),
				password: formData.get("password"),
			}),
		});

		if (!response.ok) {
			loginError.textContent = response.status === 401
				? "The username or password is incorrect."
				: "Sign-in failed. Please try again.";
			loginError.hidden = false;
			return;
		}

		const token = await response.json();
		sessionStorage.setItem("access_token", token.access_token);
		sessionStorage.setItem("token_type", token.token_type);
		window.location.assign("/");
	} catch {
		loginError.textContent = "Unable to reach the server. Please try again.";
		loginError.hidden = false;
	} finally {
		loginSubmit.disabled = false;
		loginSubmit.textContent = "Sign in";
	}
});