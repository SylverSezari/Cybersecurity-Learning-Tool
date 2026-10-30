window.addEventListener("message", (event) => {
	if (event.source !== window.parent) {
		return;
	}

	const { type, theme } = event.data ?? {};
	if (type === "theme-change" && (theme === "light" || theme === "dark")) {
		document.documentElement.dataset.theme = theme;
	}
});