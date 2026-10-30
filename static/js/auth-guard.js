// Keep protected pages hidden until the server confirms the stored token and role.
if (window.location.pathname !== "/login") {
	const accessToken = sessionStorage.getItem("access_token");
	const adminPage = window.location.pathname === "/account";

	function redirectToLogin() {
		// Remove stale credentials before navigating so the guard cannot loop on them.
		sessionStorage.removeItem("access_token");
		sessionStorage.removeItem("token_type");
		window.location.replace("/login");
	}

	if (!accessToken) {
		redirectToLogin();
	} else {
		// The server is authoritative: a stored token may be expired or its account deleted.
		fetch("/api/accounts/session", {
			headers: { Authorization: `Bearer ${accessToken}` },
		})
			.then(async (response) => {
				if (!response.ok) {
					throw new Error("Die Sitzung ist ungültig.");
				}
				const session = await response.json();
				if (adminPage && session.role !== "admin") {
					window.location.replace("/");
					return;
				}
			const logoutButtonId = session.role === "admin"
				? "adminLogoutButton"
				: "userLogoutButton";
			document.getElementById(logoutButtonId)?.removeAttribute("hidden");
				document.documentElement.removeAttribute("data-auth-pending");
			})
			.catch(redirectToLogin);
	}
}