const exerciseFrame = document.getElementById("exerciseFrame");
const exerciseLoadError = document.getElementById("exerciseLoadError");
const accessToken = sessionStorage.getItem("access_token");
let completionPending = false;

if (exerciseFrame && accessToken) {
	loadExercise();
}

async function loadExercise() {
	// Fetch with the bearer token, then run the returned lesson inside a sandboxed frame.
	try {
		const response = await fetch(exerciseFrame.dataset.exerciseUrl, {
			headers: { Authorization: `Bearer ${accessToken}` },
		});
		if (!response.ok) {
			throw new Error(response.status === 403 ? "Diese Übung ist noch gesperrt." : "Die Übung konnte nicht geladen werden.");
		}

		const documentContent = new DOMParser().parseFromString(
			await response.text(),
			"text/html",
		);
		// Resolve lesson-relative assets from the app root after converting the response to srcdoc.
		const base = documentContent.createElement("base");
		base.href = `${window.location.origin}/`;
		documentContent.head.prepend(base);
		const solutions = JSON.parse(exerciseFrame.dataset.exerciseSolutions || "[]");
		// Deliver the answer key only after the iframe has loaded its lesson script.
		exerciseFrame.addEventListener("load", () => {
			exerciseFrame.contentWindow?.postMessage(
				{ type: "exercise-solutions", solutions },
				"*",
			);
		}, { once: true });
		exerciseFrame.srcdoc = `<!doctype html>${documentContent.documentElement.outerHTML}`;
	} catch (error) {
		exerciseFrame.hidden = true;
		exerciseLoadError.textContent = error.message;
		exerciseLoadError.hidden = false;
	}
}

const completeButton = document.getElementById("completeExercise");

async function submitExerciseCompletion(answers) {
	// The API checks both completion answers and prerequisite locks before persisting progress.
	if (completionPending) return;
	completionPending = true;
	if (completeButton) completeButton.disabled = true;
	const status = document.getElementById("progressStatus");
	const headers = { Authorization: `Bearer ${accessToken}` };
	const request = { method: "POST", headers };
	if (answers !== undefined) {
		headers["Content-Type"] = "application/json";
		request.body = JSON.stringify({ answers });
	}

	try {
		const response = await fetch(
			`/api/progress/exercises/${exerciseFrame?.dataset.exerciseId || completeButton?.dataset.exerciseId}/complete`,
			request,
		);
		if (!response.ok) {
			const result = await response.json();
			const messages = {
				"Exercise not found": "Übung nicht gefunden.",
				"Exercise is locked": "Diese Übung ist noch gesperrt.",
				"Task answers are required": "Diese Übung enthält noch offene Aufgaben.",
				"Task answers are incorrect": "Nicht alle Aufgaben wurden richtig beantwortet.",
			};
			throw new Error(messages[result.detail] || "Der Lernfortschritt konnte nicht gespeichert werden.");
		}
		if (status) {
			status.textContent = "Abgeschlossen";
			status.classList.remove("task-progress-status");
			status.classList.add("task-completed-status");
		}
		completeButton?.remove();
		const currentExerciseName = document.querySelector(
			".task-exercise-link.is-current .task-exercise-name",
		);
		if (currentExerciseName && !currentExerciseName.querySelector("small")) {
			const completionLabel = document.createElement("small");
			completionLabel.textContent = "Abgeschlossen";
			currentExerciseName.append(completionLabel);
		}
		exerciseFrame?.contentWindow?.postMessage(
			{ type: "exercise-completion-saved" },
			"*",
		);
	} catch (error) {
		status.textContent = error.message;
		completionPending = false;
		if (completeButton) completeButton.disabled = false;
	}
}

completeButton?.addEventListener("click", () => submitExerciseCompletion());

window.addEventListener("message", (event) => {
	if (
		!exerciseFrame
		|| event.source !== exerciseFrame.contentWindow
		|| event.data?.type !== "exercise-tasks-complete"
		|| !Array.isArray(event.data.answers)
	) {
		return;
	}
	submitExerciseCompletion(event.data.answers);
});