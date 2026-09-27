if (window.location.pathname !== "/login") {
	const accessToken = sessionStorage.getItem("access_token");

	function redirectToLogin() {
		sessionStorage.removeItem("access_token");
		sessionStorage.removeItem("token_type");
		window.location.replace("/login");
	}

	if (!accessToken) {
		redirectToLogin();
	} else {
		fetch("/api/accounts/session", {
			headers: { Authorization: `Bearer ${accessToken}` },
		})
			.then((response) => {
				if (!response.ok) {
					throw new Error("Session is invalid");
				}
				document.documentElement.removeAttribute("data-auth-pending");
			})
			.catch(redirectToLogin);
	}
}