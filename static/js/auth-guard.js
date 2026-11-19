// Keep protected pages hidden until the server confirms the stored token and role.
const currentPath = window.location.pathname;
let sessionRedirectStarted = false;

function clearStoredSession() {
	sessionStorage.removeItem("access_token");
	sessionStorage.removeItem("token_type");
}

function redirectToSessionExpired() {
	if (sessionRedirectStarted) return;
	sessionRedirectStarted = true;
	clearStoredSession();
	window.location.replace("/session-expired");
}

const authenticatedFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
	const response = await authenticatedFetch(...args);
	if (
		response.status === 401
		&& currentPath !== "/login"
		&& currentPath !== "/session-expired"
	) {
		redirectToSessionExpired();
	}
	return response;
};

if (currentPath === "/session-expired") {
	clearStoredSession();
} else if (currentPath !== "/login") {
	const accessToken = sessionStorage.getItem("access_token");
	const adminPage = currentPath === "/account";

	function redirectToLogin() {
		// Remove stale credentials before navigating so the guard cannot loop on them.
		clearStoredSession();
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
				if (response.status === 401) {
					redirectToSessionExpired();
					return;
				}
				if (!response.ok) {
					throw new Error("Die Sitzung ist ungültig.");
				}
				const session = await response.json();
				if (adminPage && session.role !== "admin") {
					window.location.replace("/");
					return;
				}
				if (session.role === "admin") {
					document.getElementById("adminAccountButton")?.removeAttribute("hidden");
				}
				const logoutButtonId = session.role === "admin"
					? "adminLogoutButton"
					: "userLogoutButton";
				document.getElementById(logoutButtonId)?.removeAttribute("hidden");
				document.documentElement.removeAttribute("data-auth-pending");
			})
			.catch(() => {
				if (!sessionRedirectStarted) redirectToLogin();
			});
	}
}