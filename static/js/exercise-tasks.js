let exerciseSolutions = null;

function normalizedAnswer(value) {
	return String(value).trim().toLocaleUpperCase("de-CH");
}

function checkTask(task) {
	const solutionIndex = Number(task.dataset.solutionIndex);
	const expected = exerciseSolutions?.[solutionIndex];
	const answer = task.querySelector(".task-answer");
	const feedback = task.querySelector(".task-feedback");
	const isCorrect = typeof expected === "boolean"
		? answer.value === String(expected)
		: typeof expected === "number"
			? answer.value !== "" && Number(answer.value) === expected
			: normalizedAnswer(answer.value) === normalizedAnswer(expected);

	task.classList.toggle("is-correct", isCorrect);
	task.classList.toggle("is-incorrect", !isCorrect);
	task.dataset.solved = String(isCorrect);
	feedback.textContent = isCorrect
		? "Richtig. Gut gelöst!"
		: "Noch nicht ganz. Prüfe Schlüssel und Buchstabenwerte und versuche es erneut.";
	if (isCorrect) answer.disabled = true;

	const tasks = [...document.querySelectorAll(".exercise-task")];
	const completion = document.getElementById("tasksComplete");
	if (completion) completion.hidden = !tasks.every((item) => item.dataset.solved === "true");
}

document.querySelectorAll(".exercise-task").forEach((task) => {
	task.querySelector(".check-answer").addEventListener("click", () => checkTask(task));
});

window.addEventListener("message", (event) => {
	if (event.source !== parent || event.data?.type !== "exercise-solutions") return;
	exerciseSolutions = Array.isArray(event.data.solutions) ? event.data.solutions : [];
	document.querySelectorAll(".exercise-task").forEach((task) => {
		task.querySelector(".check-answer").disabled =
			Number(task.dataset.solutionIndex) >= exerciseSolutions.length;
	});
});

const shiftControl = document.getElementById("caesarShift");
if (shiftControl) {
	const alphabet = Array.from({ length: 26 }, (_, index) => String.fromCharCode(65 + index));
	const plainOutput = document.getElementById("plainAlphabet");
	const cipherOutput = document.getElementById("cipherAlphabet");
	const shiftOutput = document.getElementById("shiftValue");
	const exampleOutput = document.getElementById("shiftedExample");

	function shiftText(text, shift) {
		return [...text].map((character) => {
			const code = character.charCodeAt(0);
			if (code < 65 || code > 90) return character;
			return String.fromCharCode(((code - 65 + shift) % 26) + 65);
		}).join("");
	}

	function updateAlphabet() {
		const shift = Number(shiftControl.value);
		plainOutput.textContent = alphabet.join(" ");
		cipherOutput.textContent = alphabet.map((_, index) => alphabet[(index + shift) % 26]).join(" ");
		shiftOutput.value = String(shift);
		exampleOutput.textContent = `HALLO → ${shiftText("HALLO", shift)}`;
	}

	shiftControl.addEventListener("input", updateAlphabet);
	updateAlphabet();
}