const challengeFrame = document.getElementById("challengeFrame");
const challengeStatus = document.getElementById("challengeAnswerStatus");
const challengeContinue = document.getElementById("challengeContinue");
const challengeLoadError = document.getElementById("challengeLoadError");
const challengeToken = sessionStorage.getItem("access_token");
const adminPractice = document.querySelector("[data-admin-practice]")?.dataset.adminPractice === "true";
let challengeSubmissionPending = false;

if (challengeFrame && challengeToken) {
	loadChallenge();
}

// Load the protected HTML through the API, then isolate it in the sandboxed iframe.
async function loadChallenge() {
	try {
		const response = await fetch(challengeFrame.dataset.challengeUrl, {
			headers: { Authorization: `Bearer ${challengeToken}` },
		});
		if (!response.ok) {
			throw new Error("Die Challenge konnte nicht geladen werden.");
		}

		const documentContent = new DOMParser().parseFromString(
			await response.text(),
			"text/html",
		);
		// srcdoc has no file URL, so this base keeps relative challenge assets resolvable.
		const base = documentContent.createElement("base");
		base.href = `${window.location.origin}/`;
		documentContent.head.prepend(base);
		// Send type hints only; expected values stay on the server for answer checking.
		challengeFrame.addEventListener("load", () => {
			challengeFrame.contentWindow?.postMessage(
				{
					type: "challenge-mode",
					solutionTypes: JSON.parse(challengeFrame.dataset.solutionTypes || "[]"),
					prompt: JSON.parse(challengeFrame.dataset.challengePrompt || "null"),
				},
				"*",
			);
		}, { once: true });
		challengeFrame.srcdoc = `<!doctype html>${documentContent.documentElement.outerHTML}`;
	} catch (error) {
		challengeFrame.hidden = true;
		challengeLoadError.textContent = error.message;
		challengeLoadError.hidden = false;
	}
}

// The parent submits answers to the API and unlocks progression only on success.
async function checkChallengeAnswers(answers) {
	// Ignore repeated clicks until the previous server check has returned.
	if (challengeSubmissionPending) return;
	challengeSubmissionPending = true;
	challengeStatus.textContent = "Antwort wird geprüft …";
	challengeContinue.disabled = true;
	try {
		const response = await fetch(
			`/api/challenges/${challengeFrame.dataset.challengeId}/check`,
			{
				method: "POST",
				headers: {
					Authorization: `Bearer ${challengeToken}`,
					"Content-Type": "application/json",
				},
				body: JSON.stringify({ answers }),
			},
		);
		const result = await response.json();
		if (!response.ok) {
			const messages = {
				"Challenge answers are incorrect": "Die Lösung ist noch nicht richtig.",
				"Challenge is not current": "Diese Challenge ist nicht mehr aktuell.",
				"No active challenge run": "Es läuft keine Challenge.",
			};
			throw new Error(messages[result.detail] || "Die Antwort konnte nicht geprüft werden.");
		}

		challengeStatus.textContent = "Richtig! Du kannst fortfahren.";
		challengeContinue.disabled = false;
		challengeFrame.contentWindow?.postMessage(
			{ type: "challenge-answer-result", correct: true },
			"*",
		);
	} catch (error) {
		if (error.message === "Die Lösung ist noch nicht richtig.") {
			challengeFrame.contentWindow?.postMessage(
				{ type: "challenge-answer-result", correct: false },
				"*",
			);
		} else {
			challengeFrame.contentWindow?.postMessage(
				{ type: "challenge-answer-retry" },
				"*",
			);
		}
		challengeStatus.textContent = error.message;
		challengeContinue.disabled = !adminPractice;
		challengeSubmissionPending = false;
	}
}

window.addEventListener("message", (event) => {
	// Ignore messages from any window other than the challenge iframe.
	if (
		!challengeFrame
		|| event.source !== challengeFrame.contentWindow
		|| event.data?.type !== "challenge-tasks-submit"
		|| !Array.isArray(event.data.answers)
	) {
		return;
	}
	checkChallengeAnswers(event.data.answers);
});

// Leaving the challenge UI cancels the run before navigating to another link.
document.addEventListener("click", async (event) => {
	const anchor = event.target.closest("a[href]");
	if (!anchor || anchor.target || anchor.hasAttribute("download")) return;
	const destination = new URL(anchor.href, window.location.href);
	if (
		destination.origin === window.location.origin
		&& /^\/challenge(?:\/|$)/.test(destination.pathname)
	) {
		return;
	}

	event.preventDefault();
	try {
		const response = await fetch("/api/challenges/run/abandon", {
			method: "POST",
			headers: { Authorization: `Bearer ${challengeToken}` },
			keepalive: true,
		});
		if (!response.ok) {
			throw new Error("Der Lauf konnte nicht abgebrochen werden.");
		}
		window.location.assign(destination.href);
	} catch (error) {
		challengeStatus.textContent = error.message;
	}
});
