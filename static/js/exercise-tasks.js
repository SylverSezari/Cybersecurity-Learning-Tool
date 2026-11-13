let exerciseSolutions = null;
let completionSent = false;
// Challenge mode gets types from the parent, but never receives the expected values.
let challengeMode = false;
let challengeSolutionTypes = [];

// Ignore letter case and surrounding whitespace while preserving type-aware checks below.
function normalizedAnswer(value) {
	return String(value)
		.normalize("NFC")
		.trim()
		.toLocaleUpperCase("de-CH")
		.normalize("NFC");
}

function checkTask(task) {
	if (challengeMode) {
		// Use the same task markup while delegating correctness to the server.
		submitChallengeAnswers();
		return;
	}

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

function submitChallengeAnswers() {
	const answers = [];
	const tasks = [...document.querySelectorAll(".exercise-task")];
	// Build one index-aligned answer list and validate client-side representation only.
	for (const task of tasks) {
		const index = Number(task.dataset.solutionIndex);
		const control = task.querySelector(".task-answer");
		const value = control.value;
		const answerType = challengeSolutionTypes[index];
		if (!answerType || !value.trim()) {
			task.querySelector(".task-feedback").textContent =
				"Bitte fülle zuerst alle Antworten aus.";
			return;
		}
		if (answerType === "boolean") {
			if (value !== "true" && value !== "false") {
				task.querySelector(".task-feedback").textContent =
					"Bitte wähle eine gültige Antwort aus.";
				return;
			}
			answers[index] = value === "true";
		} else if (answerType === "number") {
			const numericValue = Number(value);
			if (!Number.isFinite(numericValue)) {
				task.querySelector(".task-feedback").textContent =
					"Bitte gib eine gültige Zahl ein.";
				return;
			}
			answers[index] = numericValue;
		} else {
			answers[index] = value;
		}
	}

	if (
		answers.length !== challengeSolutionTypes.length
		|| challengeSolutionTypes.some((_, index) => answers[index] === undefined)
	) {
		return;
	}
	document.querySelectorAll(".check-answer").forEach((button) => {
		button.disabled = true;
	});
	// The embedded page sends answers upward; the parent makes the authenticated API call.
	parent.postMessage({ type: "challenge-tasks-submit", answers }, "*");
}

function showChallengeAnswerResult(correct) {
	// Reflect the server's decision in all tasks without comparing against a local key.
	const tasks = [...document.querySelectorAll(".exercise-task")];
	for (const task of tasks) {
		task.classList.toggle("is-correct", correct);
		task.classList.toggle("is-incorrect", !correct);
		task.dataset.solved = String(correct);
		task.querySelector(".task-answer").disabled = correct;
		task.querySelector(".check-answer").disabled = correct;
		task.querySelector(".task-feedback").textContent = correct
			? task.dataset.correctFeedback || "Richtig. Gut gelöst!"
			: task.dataset.incorrectFeedback || "Noch nicht ganz. Prüfe deine Antwort und versuche es erneut.";
	}
	const completion = document.getElementById("tasksComplete");
	if (completion) {
		completion.hidden = !correct;
		if (correct) completion.textContent = "Richtig. Du kannst fortfahren.";
	}
}

function completeLessonIfReady() {
	const tasks = [...document.querySelectorAll(".exercise-task")];
	const pythonTasks = [...document.querySelectorAll("[data-python-exercise]")];
	const completion = document.getElementById("tasksComplete");
	const allTasksSolved = tasks.every((item) => item.dataset.solved === "true")
		&& pythonTasks.every((item) => item.dataset.solved === "true");
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
		for (const pythonTask of pythonTasks) {
			if (pythonTask.dataset.solutionIndex !== undefined) {
				answers[Number(pythonTask.dataset.solutionIndex)] = pythonTask.dataset.result;
			}
		}
		parent.postMessage({ type: "exercise-tasks-complete", answers }, "*");
	}
}

window.addEventListener("python-exercise-complete", completeLessonIfReady);

window.addEventListener("message", (event) => {
	if (event.source !== parent || event.data?.type !== "exercise-completion-saved") return;
	const completion = document.getElementById("tasksComplete");
	if (completion) completion.textContent = "Die Übung wurde als abgeschlossen markiert.";
});

window.addEventListener("message", (event) => {
	// Only the embedding page can report whether a challenge answer was accepted.
	if (event.source !== parent) return;
	if (event.data?.type === "challenge-mode") {
		// These hints determine how form values are converted before submission.
		challengeMode = true;
		challengeSolutionTypes = Array.isArray(event.data.solutionTypes)
			? event.data.solutionTypes
			: [];
		document.querySelectorAll(".check-answer").forEach((button) => {
			const task = button.closest(".exercise-task");
			button.disabled = !challengeSolutionTypes[Number(task.dataset.solutionIndex)];
		});
	}
	if (event.data?.type === "challenge-answer-result") {
		showChallengeAnswerResult(event.data.correct === true);
	}
	if (event.data?.type === "challenge-answer-retry") {
		// A temporary API failure allows the learner to retry the same submission.
		document.querySelectorAll(".check-answer").forEach((button) => {
			button.disabled = false;
		});
	}
});

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
	const letterCell = (letter) => {
		const cell = document.createElement("span");
		cell.textContent = letter;
		return cell;
	};

	function shiftText(text, shift) {
		return [...text].map((character) => {
			const code = character.charCodeAt(0);
			if (code < 65 || code > 90) return character;
			return String.fromCharCode(((code - 65 + shift) % 26) + 65);
		}).join("");
	}

	function updateAlphabet() {
		const shift = Number(shiftControl.value);
		plainOutput.replaceChildren(...alphabet.map(letterCell));
		cipherOutput.replaceChildren(...alphabet.map((_, index) => letterCell(alphabet[(index + shift) % 26])));
		shiftOutput.textContent = String(shift);
		shiftOutput.style.gridColumn = `${shift + 1} / span 1`;
		if (exampleOutput) exampleOutput.textContent = `HALLO → ${shiftText("HALLO", shift)}`;
	}

	shiftControl.addEventListener("input", updateAlphabet);
	updateAlphabet();
}