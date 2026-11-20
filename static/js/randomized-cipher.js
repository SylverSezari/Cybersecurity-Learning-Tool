// Populate randomized Caesar and Vigenère lesson prompts sent by the parent frame.
const taskHeading = document.getElementById("cipherTaskHeading");
const taskStory = document.getElementById("cipherTaskStory");
const cipherText = document.getElementById("cipherText");
const cipherKey = document.getElementById("cipherKey");
const alphabetShiftControl = document.getElementById("caesarShift");

function setAlphabetShift(shift) {
	alphabetShiftControl.value = String(shift);
	alphabetShiftControl.dispatchEvent(new Event("input", { bubbles: true }));
}

// Ignore messages that do not come from the trusted lesson player.
window.addEventListener("message", (event) => {
	if (event.source !== parent || event.data?.type !== "challenge-mode") return;
	const prompt = event.data.prompt;
	if (!prompt) return;

	const action = prompt.operation === "encrypt" ? "verschlüsseln" : "entschlüsseln";
	taskHeading.textContent = `${prompt.cipher}: ${action}`;
	taskStory.textContent = prompt.operation === "encrypt"
		? `Verschlüssle das zufällig ausgewählte 8-Buchstaben-Wort mit dem angegebenen Schlüssel.`
		: `Entschlüssle den Geheimtext mit dem angegebenen Schlüssel.`;
	cipherText.textContent = prompt.text;
	cipherKey.textContent = String(prompt.key);

	const initialShift = prompt.cipher === "Caesar"
		? Number(prompt.key)
		: prompt.cipher === "Vigenère" && typeof prompt.key === "string"
			? prompt.key.charCodeAt(0) - 65
			: null;
	if (initialShift !== null) setAlphabetShift(initialShift);
});
