const taskHeading = document.getElementById("cipherTaskHeading");
const taskStory = document.getElementById("cipherTaskStory");
const cipherText = document.getElementById("cipherText");
const cipherKey = document.getElementById("cipherKey");

window.addEventListener("message", (event) => {
	if (event.source !== parent || event.data?.type !== "challenge-mode") return;
	const prompt = event.data.prompt;
	if (!prompt) return;

	const action = prompt.operation === "encrypt" ? "verschlüsseln" : "entschlüsseln";
	taskHeading.textContent = `${prompt.cipher}: ${action}`;
	taskStory.textContent = prompt.operation === "encrypt"
		? `Verschlüssle die zufällig ausgewählten 8 Buchstaben mit dem angegebenen Schlüssel.`
		: `Entschlüssle den Geheimtext mit dem angegebenen Schlüssel.`;
	cipherText.textContent = prompt.text;
	cipherKey.textContent = String(prompt.key);
});
