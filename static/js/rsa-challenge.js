// Fill randomized RSA task values sent by the parent challenge player.
window.addEventListener("message", (event) => {
	// Accept prompts only from the parent frame that loaded this challenge.
	if (event.source !== parent || event.data?.type !== "challenge-mode") return;
	const prompt = event.data.prompt;
	if (!prompt) return;
	const values = {
		rsaP: prompt.p,
		rsaQ: prompt.q,
		rsaE: prompt.e,
		rsaN: prompt.n,
		rsaD: prompt.d,
		rsaMessage: prompt.message,
		rsaCiphertext: prompt.ciphertext,
	};
	for (const [id, value] of Object.entries(values)) {
		const element = document.getElementById(id);
		if (element && value !== undefined) element.textContent = String(value);
	}
});
