const pyodideVersion = "0.27.7";
let pyodideInstancePromise;

function getPyodideInstance() {
	if (!pyodideInstancePromise) {
		const baseUrl = `https://cdn.jsdelivr.net/pyodide/v${pyodideVersion}/full/`;
		pyodideInstancePromise = new Promise((resolve, reject) => {
			const script = document.createElement("script");
			script.src = `${baseUrl}pyodide.js`;
			script.onload = async () => {
				try {
					resolve(await window.loadPyodide({ indexURL: baseUrl }));
				} catch (error) {
					reject(error);
				}
			};
			script.onerror = () => reject(new Error("Pyodide konnte nicht geladen werden. Prüfe deine Internetverbindung."));
			document.head.append(script);
		});
	}
	return pyodideInstancePromise;
}

function removeTemplateIndentation(value) {
	const lines = value.replace(/^\s*\n|\n\s*$/g, "").split("\n");
	const indentation = Math.min(
		...lines.filter((line) => line.trim()).map((line) => line.match(/^\s*/)[0].length),
	);
	return lines.map((line) => line.slice(indentation)).join("\n");
}

function escapeHtml(value) {
	return value.replace(/[&<>"']/g, (character) => ({
		"&": "&amp;",
		"<": "&lt;",
		">": "&gt;",
		'"': "&quot;",
		"'": "&#39;",
	})[character]);
}

function highlightPythonComments(source) {
	return source.split("\n").map((line) => {
		let quote = null;
		let escaped = false;

		for (let index = 0; index < line.length; index += 1) {
			const character = line[index];
			if (quote) {
				if (escaped) escaped = false;
				else if (character === "\\") escaped = true;
				else if (character === quote) quote = null;
			} else if (character === "\"" || character === "'") {
				quote = character;
			} else if (character === "#") {
				return `${escapeHtml(line.slice(0, index))}<span class="python-comment">${escapeHtml(line.slice(index))}</span>`;
			}
		}

		return escapeHtml(line);
	}).join("\n");
}

document.querySelectorAll("[data-python-exercise]").forEach((pythonExercise) => {
	const editor = pythonExercise.querySelector(".python-code-editor");
	const runButton = pythonExercise.querySelector("[data-python-run]");
	const output = pythonExercise.querySelector("[data-python-output]");
	const editorShell = document.createElement("div");
	const lineNumbers = document.createElement("div");
	const highlightedCode = document.createElement("pre");
	const highlightedCodeContent = document.createElement("code");
	editorShell.className = "python-editor-shell";
	lineNumbers.className = "python-line-numbers";
	lineNumbers.setAttribute("aria-hidden", "true");
	highlightedCode.className = "python-code-highlight";
	highlightedCode.setAttribute("aria-hidden", "true");
	highlightedCode.append(highlightedCodeContent);
	editor.parentNode.insertBefore(editorShell, editor);
	editorShell.append(lineNumbers, highlightedCode, editor);
	const updateEditorPresentation = () => {
		const lines = editor.value.split("\n");
		lineNumbers.textContent = lines.map((_, index) => index + 1).join("\n");
		highlightedCodeContent.innerHTML = `${highlightPythonComments(editor.value)}\n`;
	};
	const starterCode = removeTemplateIndentation(editor.value);
	editor.value = starterCode;
	updateEditorPresentation();

	editor.addEventListener("input", updateEditorPresentation);
	editor.addEventListener("keydown", (event) => {
		const start = editor.selectionStart;
		const end = editor.selectionEnd;
		const pairs = { "(": ")", "[": "]", "{": "}", "'": "'", '"': '"' };

		if (event.key === "Tab" && !event.shiftKey) {
			event.preventDefault();
			editor.setRangeText("    ", start, end, "end");		} else if (event.key === "Enter") {
			event.preventDefault();
			const lineStart = editor.value.lastIndexOf("\n", start - 1) + 1;
			const currentLine = editor.value.slice(lineStart, start);
			const indentation = currentLine.match(/^[\t ]*/)[0];
			const extraIndentation = currentLine.trimEnd().endsWith(":") ? "    " : "";
			editor.setRangeText(`\n${indentation}${extraIndentation}`, start, end, "end");
		} else if (Object.hasOwn(pairs, event.key)) {
			event.preventDefault();
			const selectedText = editor.value.slice(start, end);
			editor.setRangeText(`${event.key}${selectedText}${pairs[event.key]}`, start, end, "end");
			editor.setSelectionRange(start + 1, start + 1 + selectedText.length);
		} else if (
			start === end
			&& Object.values(pairs).includes(event.key)
			&& editor.value[start] === event.key
		) {
			event.preventDefault();
			editor.setSelectionRange(start + 1, start + 1);
			return;
		} else {
			return;
		}

		editor.dispatchEvent(new Event("input", { bubbles: true }));
	});
	editor.addEventListener("scroll", () => {
		lineNumbers.scrollTop = editor.scrollTop;
		highlightedCode.scrollTop = editor.scrollTop;
	});

	pythonExercise.querySelector("[data-python-reset]").addEventListener("click", () => {
		editor.value = starterCode;
		updateEditorPresentation();
		lineNumbers.scrollTop = 0;
		highlightedCode.scrollTop = 0;
		pythonExercise.dataset.solved = "false";
		delete pythonExercise.dataset.result;
		pythonExercise.classList.remove("is-correct", "is-incorrect");
		output.textContent = "Code zurückgesetzt. Ergänze die TODO-Zeilen und starte Python.";
	});

	editor.addEventListener("input", () => {
		if (pythonExercise.dataset.solved === "true") {
			pythonExercise.dataset.solved = "false";
			delete pythonExercise.dataset.result;
			pythonExercise.classList.remove("is-correct");
			output.textContent = "Code geändert. Führe ihn erneut aus, um die Aufgabe abzuschliessen.";
		}
	});

	runButton.addEventListener("click", async () => {
		runButton.disabled = true;
		pythonExercise.classList.remove("is-correct", "is-incorrect");
		output.textContent = "Python wird im Browser gestartet. Beim ersten Start kann das Laden kurz dauern ...";
		const printedLines = [];

		try {
			const pyodide = await getPyodideInstance();
			pyodide.setStdout({ batched: (line) => printedLines.push(line) });
			try {
				await pyodide.runPythonAsync(editor.value);
			} finally {
				pyodide.setStdout({ batched: () => {} });
			}

			const result = printedLines.join("\n").trim();
			pythonExercise.dataset.result = result;
			const normalizeOutput = (value) => value.normalize("NFC").trim().toLocaleUpperCase("de-CH");
			const isCorrect = normalizeOutput(result)
				=== normalizeOutput(pythonExercise.dataset.expectedOutput);
			pythonExercise.classList.toggle("is-correct", isCorrect);
			pythonExercise.classList.toggle("is-incorrect", !isCorrect);
			pythonExercise.dataset.solved = String(isCorrect);
			const feedback = isCorrect
				? pythonExercise.dataset.correctFeedback || "Richtig. Die Python-Aufgabe ist abgeschlossen."
				: pythonExercise.dataset.incorrectFeedback || "Noch nicht richtig. Prüfe deine TODO-Zeilen und versuche es erneut.";
			output.textContent = result
				? `${result}\n\n${feedback}`
				: pythonExercise.dataset.emptyFeedback || "Dein Programm hat nichts ausgegeben. Prüfe, ob die letzte Zeile print(encrypted) noch vorhanden ist.";
			if (isCorrect) {
				window.dispatchEvent(new Event("python-exercise-complete"));
			}
		} catch (error) {
			pythonExercise.dataset.solved = "false";
			pythonExercise.classList.add("is-incorrect");
			const partialOutput = printedLines.join("\n").trim();
			output.textContent = `Python-Fehler:\n${error.message}${partialOutput ? `\n\nAusgabe vor dem Fehler:\n${partialOutput}` : ""}`;
		} finally {
			runButton.disabled = false;
		}
	});
});