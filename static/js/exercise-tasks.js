let exerciseSolutions = null;
let completionSent = false;

// Ignore letter case and surrounding whitespace while preserving type-aware checks below.
function normalizedAnswer(value) {
	return String(value)
		.normalize("NFC")
		.trim()
		.toLocaleUpperCase("de-CH")
		.normalize("NFC");
}

function checkTask(task) {
	// Each task points to its expected value by index in the answer key sent by the parent.
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
		? task.dataset.correctFeedback || "Richtig. Gut gelöst!"
		: task.dataset.incorrectFeedback || "Noch nicht ganz. Prüfe deine Antwort und versuche es erneut.";
	if (isCorrect) answer.disabled = true;

	completeLessonIfReady();
}

function completeLessonIfReady() {
	const tasks = [...document.querySelectorAll(".exercise-task")];
	const pythonTask = document.querySelector("[data-python-exercise]");
	const completion = document.getElementById("tasksComplete");
	const allTasksSolved = tasks.every((item) => item.dataset.solved === "true")
		&& (!pythonTask || pythonTask.dataset.solved === "true");
	if (completion) completion.hidden = !allTasksSolved;
	if (allTasksSolved && !completionSent && exerciseSolutions) {
		completionSent = true;
		const answers = [];
		for (const item of tasks) {
			const index = Number(item.dataset.solutionIndex);
			const expected = exerciseSolutions[index];
			const value = item.querySelector(".task-answer").value;
			answers[index] = typeof expected === "boolean"
				? value === "true"
				: typeof expected === "number"
					? Number(value)
					: value;
		}
		if (pythonTask?.dataset.solutionIndex !== undefined) {
			answers[Number(pythonTask.dataset.solutionIndex)] = pythonTask.dataset.result;
		}
		parent.postMessage({ type: "exercise-tasks-complete", answers }, "*");
	}
}

window.addEventListener("python-exercise-complete", completeLessonIfReady);

document.querySelectorAll(".exercise-task").forEach((task) => {
	task.querySelector(".check-answer").addEventListener("click", () => checkTask(task));
});

window.addEventListener("message", (event) => {
	// Accept answer keys only from the embedding page, never from another window.
	if (event.source !== parent || event.data?.type !== "exercise-solutions") return;
	exerciseSolutions = Array.isArray(event.data.solutions) ? event.data.solutions : [];
	document.querySelectorAll(".exercise-task").forEach((task) => {
		task.querySelector(".check-answer").disabled =
			Number(task.dataset.solutionIndex) >= exerciseSolutions.length;
	});
		completeLessonIfReady();
});

const shiftControl = document.getElementById("caesarShift");
if (shiftControl) {
	// This interactive example keeps the plaintext alphabet fixed and shifts the cipher row.
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