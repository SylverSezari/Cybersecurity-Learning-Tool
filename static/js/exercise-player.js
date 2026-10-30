const exerciseFrame = document.getElementById("exerciseFrame");
const exerciseLoadError = document.getElementById("exerciseLoadError");
const accessToken = sessionStorage.getItem("access_token");

if (exerciseFrame && accessToken) {
	loadExercise();
}

async function loadExercise() {
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
		const base = documentContent.createElement("base");
		base.href = `${window.location.origin}/`;
		documentContent.head.prepend(base);
		const solutions = JSON.parse(exerciseFrame.dataset.exerciseSolutions || "[]");
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
if (completeButton) {
	completeButton.addEventListener("click", async () => {
		completeButton.disabled = true;
		const status = document.getElementById("progressStatus");
		try {
			const response = await fetch(
				`/api/progress/exercises/${completeButton.dataset.exerciseId}/complete`,
				{
					method: "POST",
					headers: { Authorization: `Bearer ${accessToken}` },
				},
			);
			if (!response.ok) {
				const result = await response.json();
				throw new Error(result.detail === "Exercise not found"
					? "Übung nicht gefunden."
					: result.detail === "Exercise is locked"
						? "Diese Übung ist noch gesperrt."
						: "Der Lernfortschritt konnte nicht gespeichert werden.");
			}
			window.location.reload();
		} catch (error) {
			status.textContent = error.message;
			completeButton.disabled = false;
		}
	});
}