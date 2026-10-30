window.addEventListener("message", (event) => {
	// The parent page synchronizes its selected theme with the isolated exercise frame.
	if (event.source !== window.parent) {
		return;
	}

	const { type, theme } = event.data ?? {};
	if (type === "theme-change" && (theme === "light" || theme === "dark")) {
		document.documentElement.dataset.theme = theme;
	}
});