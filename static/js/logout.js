for (const buttonId of ["userLogoutButton", "adminLogoutButton"]) {
	const button = document.getElementById(buttonId);
	button?.addEventListener("click", () => {
		sessionStorage.removeItem("access_token");
		sessionStorage.removeItem("token_type");
		window.location.replace("/logout");
	});
}