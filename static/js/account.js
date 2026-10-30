const accessToken = sessionStorage.getItem("access_token");
const activeList = document.getElementById("activeChapters");
const inactiveList = document.getElementById("inactiveChapters");
const statusMessage = document.getElementById("chapterStatus");
const saveButton = document.getElementById("saveChanges");
const saveHint = document.getElementById("saveHint");
const updateSelect = document.getElementById("updateChapterSelect");
const deleteSelect = document.getElementById("deleteChapterSelect");
const exerciseChapterSelect = document.getElementById("exerciseChapterSelect");
const updateExerciseSelect = document.getElementById("updateExerciseSelect");
const deleteExerciseSelect = document.getElementById("deleteExerciseSelect");
const exerciseStatus = document.getElementById("exerciseStatus");
const accountStatus = document.getElementById("accountsStatus");
const updateAccountSelect = document.getElementById("updateAccountSelect");
const deleteAccountSelect = document.getElementById("deleteAccountSelect");
let chapters = [];
let exercises = [];
let accounts = [];
let savedOrder = "[]";
const apiErrorMessages = new Map([
	["Invalid account", "Ungültiges Benutzerkonto."],
	["Account no longer exists", "Dieses Benutzerkonto existiert nicht mehr."],
	["Chapter not found", "Kapitel nicht gefunden."],
	["Exercise not found", "Übung nicht gefunden."],
	["Exercise is locked", "Diese Übung ist noch gesperrt."],
	["Exercise file not found", "Übungsdatei nicht gefunden."],
	["Account not found", "Benutzerkonto nicht gefunden."],
	["Account with this username exists already", "Ein Benutzerkonto mit diesem Benutzernamen existiert bereits."],
	["Account with this username already exists", "Ein Benutzerkonto mit diesem Benutzernamen existiert bereits."],
	["Invalid username or password", "Benutzername oder Passwort ist falsch."],
	["Chapter with this title exists already", "Ein Kapitel mit diesem Titel existiert bereits."],
	["Chapter with this title already exists", "Ein Kapitel mit diesem Titel existiert bereits."],
	["Assigned chapter positions must be unique", "Die Reihenfolge der Kapitel darf keine doppelten Positionen enthalten."],
	["Include each existing chapter exactly once", "Jedes vorhandene Kapitel muss genau einmal enthalten sein."],
	["Exercise with this title already created", "Eine Übung mit diesem Titel existiert bereits."],
	["Exercise with this filename already created", "Eine Übung mit diesem Dateinamen existiert bereits."],
	["Position already assigned", "Diese Position ist bereits vergeben."],
	["User account required", "Ein Benutzerkonto ist erforderlich."],
	["Invalid or expired authentication token", "Die Sitzung ist ungültig oder abgelaufen."],
	["Admin privileges required", "Administratorrechte erforderlich."],
]);

function createSolutionRow(value = "") {
	const row = document.createElement("div");
	row.className = "solution-row";
	const typeSelect = document.createElement("select");
	typeSelect.className = "solution-type";
	typeSelect.setAttribute("aria-label", "Lösungstyp");
	for (const [label, type] of [["Text", "text"], ["Zahl", "number"], ["Wahrheitswert", "boolean"]]) {
		typeSelect.add(new Option(label, type));
	}
	const valueType = typeof value === "boolean" ? "boolean" : typeof value === "number" ? "number" : "text";
	typeSelect.value = valueType;
	let valueControl = createSolutionValueControl(valueType, value);
	const removeButton = document.createElement("button");
	removeButton.className = "action-button danger-action solution-remove-button";
	removeButton.type = "button";
	removeButton.textContent = "Entfernen";
	removeButton.setAttribute("aria-label", "Lösung entfernen");
	removeButton.addEventListener("click", () => row.remove());
	typeSelect.addEventListener("change", () => {
		const replacement = createSolutionValueControl(typeSelect.value);
		row.replaceChild(replacement, valueControl);
		valueControl = replacement;
	});
	row.append(typeSelect, valueControl, removeButton);
	return row;
}

function createSolutionValueControl(type, value = "") {
	if (type === "boolean") {
		const select = document.createElement("select");
		select.className = "solution-value";
		select.setAttribute("aria-label", "Wahrheitswert");
		select.add(new Option("Wahr", "true"));
		select.add(new Option("Falsch", "false"));
		select.value = String(value === true);
		return select;
	}
	const input = document.createElement("input");
	input.className = "solution-value";
	input.type = type === "number" ? "number" : "text";
	input.setAttribute("aria-label", type === "number" ? "Zahlenlösung" : "Textlösung");
	if (type === "number") input.step = "any";
	input.value = value === "" ? "" : String(value);
	input.required = true;
	return input;
}

function setSolutionRows(containerId, solutions = []) {
	const container = document.getElementById(containerId);
	container.replaceChildren(...solutions.map((solution) => createSolutionRow(solution)));
}

function readSolutions(containerId) {
	const solutions = [];
	for (const row of document.getElementById(containerId).querySelectorAll(".solution-row")) {
		const type = row.querySelector(".solution-type").value;
		const control = row.querySelector(".solution-value");
		if (type === "boolean") {
			solutions.push(control.value === "true");
			continue;
		}
		if (!control.value.trim() || !control.reportValidity()) return undefined;
		solutions.push(type === "number" ? control.valueAsNumber : control.value);
	}
	return solutions;
}

document.querySelectorAll("[data-add-solution]").forEach((button) => {
	button.addEventListener("click", () => {
		const containerId = button.dataset.addSolution === "new"
			? "newExerciseSolutions"
			: "updateExerciseSolutions";
		const row = createSolutionRow();
		document.getElementById(containerId).append(row);
		row.querySelector(".solution-value").focus();
	});
});

function setStatus(message) {
	if (statusMessage) statusMessage.textContent = message;
	if (exerciseStatus) exerciseStatus.textContent = message;
	if (accountStatus) accountStatus.textContent = message;
}

function chapterOrder() {
	return JSON.stringify(chapters.map(({ id, active, position }) => ({ id, active, position })));
}

function updateDirtyState() {
	const dirty = chapterOrder() !== savedOrder;
	saveButton.disabled = !dirty;
	saveHint.textContent = dirty
		? "Reihenfolge oder Sichtbarkeit geändert. Speichere, um die Änderungen zu übernehmen."
		: "Änderungen an Reihenfolge und Sichtbarkeit sind noch nicht gespeichert.";
}

function sortedChapters() {
	return [...chapters].sort((first, second) => {
		if (first.active !== second.active) return first.active ? -1 : 1;
		if (first.active) return first.position - second.position || first.id - second.id;
		return first.id - second.id;
	});
}

function reorderDraft() {
	const activeIds = [...activeList.children].map((row) => Number(row.dataset.chapterId));
	const inactiveIds = [...inactiveList.children].map((row) => Number(row.dataset.chapterId));
	const byId = new Map(chapters.map((chapter) => [chapter.id, chapter]));
	chapters = [
		...activeIds.map((id, position) => ({ ...byId.get(id), active: true, position })),
		...inactiveIds.map((id) => ({ ...byId.get(id), active: false, position: -1 })),
	];
	updateDirtyState();
}

function moveChapter(row, offset) {
	const list = row.parentElement;
	const target = list.children[[...list.children].indexOf(row) + offset];
	if (!target) return;
	if (offset < 0) list.insertBefore(row, target);
	else list.insertBefore(target, row);
	reorderDraft();
	row.querySelector("button")?.focus();
}

function makeChapterRow(chapter, list) {
	const row = document.createElement("li");
	row.className = "chapter-row";
	row.draggable = chapter.active;
	row.dataset.chapterId = chapter.id;
	row.innerHTML = `
		<span class="chapter-row-title"></span>
		<label class="chapter-toggle">
			<input type="checkbox" aria-label="Kapitel aktivieren" ${chapter.active ? "checked" : ""} />
			<span>Aktiv</span>
		</label>
		<div class="chapter-order-controls">
			<button class="move-button" type="button" aria-label="Kapitel nach oben verschieben" title="Nach oben">&#8593;</button>
			<button class="move-button" type="button" aria-label="Kapitel nach unten verschieben" title="Nach unten">&#8595;</button>
			<span class="drag-grip" aria-hidden="true">&#8942;</span>
		</div>`;
	row.querySelector(".chapter-row-title").textContent = chapter.title;
	row.querySelector("input").addEventListener("change", (event) => {
		chapter.active = event.target.checked;
		renderChapters();
		updateDirtyState();
	});
	const [moveUp, moveDown] = row.querySelectorAll(".move-button");
	moveUp.disabled = !chapter.active;
	moveDown.disabled = !chapter.active;
	moveUp.addEventListener("click", () => moveChapter(row, -1));
	moveDown.addEventListener("click", () => moveChapter(row, 1));
	row.addEventListener("dragstart", (event) => {
		row.classList.add("is-dragging");
		event.dataTransfer.setData("text/plain", String(chapter.id));
		event.dataTransfer.effectAllowed = "move";
	});
	row.addEventListener("dragend", () => row.classList.remove("is-dragging"));
	row.addEventListener("dragover", (event) => {
		event.preventDefault();
		event.dataTransfer.dropEffect = "move";
	});
	row.addEventListener("drop", (event) => {
		event.preventDefault();
		const draggedId = Number(event.dataTransfer.getData("text/plain"));
		const draggedRow = document.querySelector(`[data-chapter-id="${draggedId}"]`);
		if (!draggedRow || draggedRow === row || draggedRow.parentElement !== list) return;
		const bounds = row.getBoundingClientRect();
		const insertAfter = event.clientY > bounds.top + bounds.height / 2;
		list.insertBefore(draggedRow, insertAfter ? row.nextSibling : row);
		reorderDraft();
	});
	return row;
}

function updateChapterOptions() {
	for (const select of [updateSelect, deleteSelect]) {
		const selectedId = select.value;
		select.replaceChildren(new Option("Kapitel auswählen", ""));
		for (const chapter of sortedChapters()) {
			select.add(new Option(chapter.title, String(chapter.id)));
		}
		if (chapters.some((chapter) => String(chapter.id) === selectedId)) {
			select.value = selectedId;
		}
		select.disabled = chapters.length === 0;
	}
	const selectedChapter = chapters.find((chapter) => String(chapter.id) === updateSelect.value);
	if (selectedChapter) document.getElementById("updateChapterTitle").value = selectedChapter.title;
		updateExerciseChapterOptions();
		renderExerciseLists();
}

function renderChapters() {
	activeList.replaceChildren();
	inactiveList.replaceChildren();
	const ordered = sortedChapters();
	const activeChapters = ordered.filter((chapter) => chapter.active);
	const inactiveChapters = ordered.filter((chapter) => !chapter.active);
	activeChapters.forEach((chapter) => activeList.append(makeChapterRow(chapter, activeList)));
	inactiveChapters.forEach((chapter) => inactiveList.append(makeChapterRow(chapter, inactiveList)));
	document.getElementById("activeCount").textContent = `Aktiv: ${activeChapters.length}`;
	document.getElementById("inactiveCount").textContent = `Inaktiv: ${inactiveChapters.length}`;
	document.getElementById("activeEmpty").hidden = activeChapters.length > 0;
	document.getElementById("inactiveEmpty").hidden = inactiveChapters.length > 0;
	updateChapterOptions();
}

async function apiRequest(path, options = {}) {
	const response = await fetch(path, {
		...options,
		headers: {
			Authorization: `Bearer ${accessToken}`,
			...(options.body ? { "Content-Type": "application/json" } : {}),
			...options.headers,
		},
	});
	if (!response.ok) {
		const body = await response.json().catch(() => ({}));
		const message = typeof body.detail === "string"
			? apiErrorMessages.get(body.detail)
			: null;
		throw new Error(message || "Die Anfrage konnte nicht abgeschlossen werden.");
	}
	return response.status === 204 ? null : response.json();
}

async function loadChapters() {
	chapters = await apiRequest("/api/chapters");
	chapters = sortedChapters();
	savedOrder = chapterOrder();
	renderChapters();
	updateDirtyState();
	setStatus(`${chapters.length} Kapitel geladen`);
}

function showError(error) {
	setStatus(error.message);
}

function updateExerciseChapterOptions() {
	const selectedId = exerciseChapterSelect.value;
	exerciseChapterSelect.replaceChildren(new Option("Kapitel auswählen", ""));
	for (const chapter of sortedChapters()) {
		exerciseChapterSelect.add(new Option(chapter.title, String(chapter.id)));
	}
	if (chapters.some((chapter) => String(chapter.id) === selectedId)) {
		exerciseChapterSelect.value = selectedId;
	} else if (chapters.length > 0) {
		exerciseChapterSelect.value = String(sortedChapters()[0].id);
	}
	exerciseChapterSelect.disabled = chapters.length === 0;
}

function makeExerciseRow(exercise, actionLabel, action) {
	const row = document.createElement("li");
	row.className = "exercise-row";
	const details = document.createElement("div");
	details.className = "exercise-row-details";
	const title = document.createElement("span");
	title.className = "exercise-row-title";
	title.textContent = exercise.title;
	const filename = document.createElement("span");
	filename.className = "exercise-row-filename";
	filename.textContent = exercise.html_filename;
	details.append(title, filename);
	row.append(details);
	if (actionLabel) {
		const button = document.createElement("button");
		button.className = "exercise-row-action";
		button.type = "button";
		button.textContent = actionLabel;
		button.addEventListener("click", action);
		row.append(button);
	}
	return row;
}

function renderExerciseLists() {
	if (!exerciseChapterSelect) return;
	const chapterId = Number(exerciseChapterSelect.value);
	const assigned = exercises
		.filter((exercise) => exercise.chapter_id === chapterId)
		.sort((first, second) => (first.position ?? 0) - (second.position ?? 0));
	const unassigned = exercises.filter(
		(exercise) => exercise.chapter_id === -1 || exercise.chapter_id === null,
	);
	const assignedList = document.getElementById("assignedExercises");
	const unassignedList = document.getElementById("unassignedExercises");
	assignedList.replaceChildren();
	unassignedList.replaceChildren();
	for (const exercise of assigned) {
		assignedList.append(makeExerciseRow(exercise, "Zuweisung aufheben", () => assignExercise(exercise.id, -1)));
	}
	for (const exercise of unassigned) {
		unassignedList.append(makeExerciseRow(exercise, "Zuweisen", () => assignExercise(exercise.id, chapterId)));
	}
	document.getElementById("assignedCount").textContent = String(assigned.length);
	document.getElementById("unassignedCount").textContent = String(unassigned.length);
	document.getElementById("assignedEmpty").hidden = assigned.length > 0 || !chapterId;
	document.getElementById("unassignedEmpty").hidden = unassigned.length > 0;
	const allExercises = document.getElementById("allExercises");
	allExercises.replaceChildren();
	for (const exercise of [...exercises].sort((first, second) => first.title.localeCompare(second.title))) {
		const item = document.createElement("li");
		const title = document.createElement("span");
		title.className = "catalog-title";
		title.textContent = exercise.title;
		const metadata = document.createElement("span");
		metadata.className = "catalog-metadata";
		const chapter = chapters.find((item) => item.id === exercise.chapter_id);
		metadata.textContent = [
			chapter ? chapter.title : "Nicht zugewiesen",
			exercise.requires_previous ? "Vorherige Übung erforderlich" : "",
		].filter(Boolean).join(" · ");
		item.append(title, metadata);
		allExercises.append(item);
	}
	document.getElementById("allExercisesEmpty").hidden = exercises.length > 0;
	updateExerciseOptions();
}

function updateExerciseOptions() {
	for (const select of [updateExerciseSelect, deleteExerciseSelect]) {
		const selectedId = select.value;
		select.replaceChildren(new Option("Übung auswählen", ""));
		for (const exercise of [...exercises].sort((first, second) => first.title.localeCompare(second.title))) {
			select.add(new Option(exercise.title, String(exercise.id)));
		}
		if (exercises.some((exercise) => String(exercise.id) === selectedId)) {
			select.value = selectedId;
		}
		select.disabled = exercises.length === 0;
	}
	fillExerciseUpdateForm();
}

function fillExerciseUpdateForm() {
	const exercise = exercises.find((item) => String(item.id) === updateExerciseSelect.value);
	if (!exercise) return;
	document.getElementById("updateExerciseTitle").value = exercise.title;
	document.getElementById("updateExerciseFilename").value = exercise.html_filename;
	setSolutionRows("updateExerciseSolutions", exercise.solution || []);
	document.getElementById("updateExerciseRequiresPrevious").checked = exercise.requires_previous;
}

async function loadExercises() {
	exercises = await apiRequest("/api/exercises");
	renderExerciseLists();
}

async function assignExercise(exerciseId, chapterId) {
	let position = -1;
	if (chapterId !== -1) {
		const occupied = new Set(
			exercises
				.filter((exercise) => exercise.chapter_id === chapterId)
				.map((exercise) => exercise.position),
		);
		position = 0;
		while (occupied.has(position)) position += 1;
	}
	try {
		await apiRequest(`/api/exercises/assignment?exercise_id=${exerciseId}`, {
			method: "PUT",
			body: JSON.stringify({ chapter_id: chapterId, position }),
		});
		await loadExercises();
		setStatus(chapterId === -1 ? "Übungszuweisung aufgehoben" : "Übung dem Kapitel zugewiesen");
	} catch (error) {
		showError(error);
	}
}

function updateAccountOptions() {
	for (const select of [updateAccountSelect, deleteAccountSelect]) {
		const selectedId = select.value;
		select.replaceChildren(new Option("Benutzerkonto auswählen", ""));
		for (const account of accounts) {
			select.add(new Option(account.username, String(account.id)));
		}
		if (accounts.some((account) => String(account.id) === selectedId)) {
			select.value = selectedId;
		}
		select.disabled = accounts.length === 0;
	}
	fillAccountUpdateForm();
}

function fillAccountUpdateForm() {
	const account = accounts.find((item) => String(item.id) === updateAccountSelect.value);
	if (!account) return;
	document.getElementById("updateAccountUsername").value = account.username;
	document.getElementById("updateAccountPassword").value = "";
}

function renderAccounts() {
	const accountList = document.getElementById("accountList");
	accountList.replaceChildren();
	for (const account of accounts) {
		const item = document.createElement("li");
		const id = document.createElement("span");
		id.className = "account-list-id";
		id.textContent = String(account.id).padStart(3, "0");
		const username = document.createElement("span");
		username.className = "account-list-username";
		username.textContent = account.username;
		item.append(id, username);
		accountList.append(item);
	}
	document.getElementById("accountCount").textContent = `Benutzerkonten: ${accounts.length}`;
	document.getElementById("accountsEmpty").hidden = accounts.length > 0;
	updateAccountOptions();
}

async function loadAccounts() {
	accounts = await apiRequest("/api/accounts");
	accounts.sort((first, second) => first.username.localeCompare(second.username));
	renderAccounts();
	setStatus(`${accounts.length} Benutzerkonten geladen`);
}

document.querySelectorAll(".admin-nav-button").forEach((button) => {
	button.addEventListener("click", () => {
		document.querySelectorAll(".admin-nav-button").forEach((item) => {
			item.classList.toggle("is-selected", item === button);
			if (item === button) item.setAttribute("aria-current", "page");
			else item.removeAttribute("aria-current");
		});
		for (const section of ["chapters", "exercises", "accounts"]) {
			document.getElementById(`${section}Section`).hidden = button.dataset.section !== section;
		}
	});
});

document.getElementById("addChapterForm").addEventListener("submit", async (event) => {
	event.preventDefault();
	const title = document.getElementById("newChapterTitle").value.trim();
	if (!title) return;
	try {
		await apiRequest("/api/chapters", { method: "POST", body: JSON.stringify({ title }) });
		event.target.reset();
		await loadChapters();
		statusMessage.textContent = "Kapitel hinzugefügt und deaktiviert";
	} catch (error) {
		showError(error);
	}
});

document.getElementById("updateChapterForm").addEventListener("submit", async (event) => {
	event.preventDefault();
	const chapterId = updateSelect.value;
	const title = document.getElementById("updateChapterTitle").value.trim();
	if (!chapterId || !title) return;
	try {
		await apiRequest(`/api/chapters/update/${chapterId}`, {
			method: "PUT",
			body: JSON.stringify({ title }),
		});
		await loadChapters();
		statusMessage.textContent = "Kapiteltitel aktualisiert";
	} catch (error) {
		showError(error);
	}
});

document.getElementById("deleteChapterForm").addEventListener("submit", async (event) => {
	event.preventDefault();
	const chapterId = deleteSelect.value;
	const chapter = chapters.find((item) => String(item.id) === chapterId);
	if (!chapter || !window.confirm(`Möchtest du das Kapitel „${chapter.title}“ wirklich löschen?`)) return;
	try {
		await apiRequest(`/api/chapters/delete/${chapterId}`, { method: "DELETE" });
		await loadChapters();
		statusMessage.textContent = "Kapitel gelöscht";
	} catch (error) {
		showError(error);
	}
});

updateSelect.addEventListener("change", updateChapterOptions);
exerciseChapterSelect.addEventListener("change", renderExerciseLists);
updateExerciseSelect.addEventListener("change", fillExerciseUpdateForm);
updateAccountSelect.addEventListener("change", fillAccountUpdateForm);

document.getElementById("addAccountForm").addEventListener("submit", async (event) => {
	event.preventDefault();
	const username = document.getElementById("newAccountUsername").value.trim();
	const password = document.getElementById("newAccountPassword").value;
	if (!username || !password) return;
	try {
		await apiRequest("/api/accounts", {
			method: "POST",
			body: JSON.stringify({ username, password }),
		});
		event.target.reset();
		await loadAccounts();
		setStatus("Benutzerkonto erstellt");
	} catch (error) {
		showError(error);
	}
});

document.getElementById("updateAccountForm").addEventListener("submit", async (event) => {
	event.preventDefault();
	const accountId = updateAccountSelect.value;
	const username = document.getElementById("updateAccountUsername").value.trim();
	const password = document.getElementById("updateAccountPassword").value;
	if (!accountId || !username) return;
	const update = { username };
	if (password) update.password = password;
	try {
		await apiRequest(`/api/accounts/update/${accountId}`, {
			method: "PUT",
			body: JSON.stringify(update),
		});
		await loadAccounts();
		setStatus("Benutzerkonto aktualisiert");
	} catch (error) {
		showError(error);
	}
});

document.getElementById("deleteAccountForm").addEventListener("submit", async (event) => {
	event.preventDefault();
	const accountId = deleteAccountSelect.value;
	const account = accounts.find((item) => String(item.id) === accountId);
	if (!account || !window.confirm(`Möchtest du das Benutzerkonto „${account.username}“ wirklich löschen?`)) return;
	try {
		await apiRequest(`/api/accounts/delete/${accountId}`, { method: "DELETE" });
		await loadAccounts();
		setStatus("Benutzerkonto gelöscht");
	} catch (error) {
		showError(error);
	}
});

document.getElementById("addExerciseForm").addEventListener("submit", async (event) => {
	event.preventDefault();
	const title = document.getElementById("newExerciseTitle").value.trim();
	const html_filename = document.getElementById("newExerciseFilename").value.trim();
	const solution = readSolutions("newExerciseSolutions");
	const requires_previous = document.getElementById("newExerciseRequiresPrevious").checked;
	if (!title || !html_filename || solution === undefined) return;
	try {
		await apiRequest("/api/exercises", {
			method: "POST",
			body: JSON.stringify({ title, html_filename, solution, requires_previous }),
		});
		event.target.reset();
		setSolutionRows("newExerciseSolutions");
		await loadExercises();
		setStatus("Übung hinzugefügt und keinem Kapitel zugewiesen");
	} catch (error) {
		showError(error);
	}
});

document.getElementById("updateExerciseForm").addEventListener("submit", async (event) => {
	event.preventDefault();
	const exerciseId = updateExerciseSelect.value;
	if (!exerciseId) return;
	const title = document.getElementById("updateExerciseTitle").value.trim();
	const html_filename = document.getElementById("updateExerciseFilename").value.trim();
	const solution = readSolutions("updateExerciseSolutions");
	const requires_previous = document.getElementById("updateExerciseRequiresPrevious").checked;
	if (!title || !html_filename || solution === undefined) return;
	const submitButton = event.currentTarget.querySelector('button[type="submit"]');
	const originalLabel = submitButton.textContent;
	submitButton.disabled = true;
	submitButton.textContent = "Wird gespeichert …";
	setStatus("Übung wird gespeichert …");
	try {
		await apiRequest(`/api/exercises/update/${exerciseId}`, {
			method: "PUT",
			body: JSON.stringify({ title, html_filename, solution, requires_previous }),
		});
		await loadExercises();
		setStatus("Übung aktualisiert");
	} catch (error) {
		showError(error);
	} finally {
		submitButton.disabled = false;
		submitButton.textContent = originalLabel;
	}
});

document.getElementById("deleteExerciseForm").addEventListener("submit", async (event) => {
	event.preventDefault();
	const exerciseId = deleteExerciseSelect.value;
	const exercise = exercises.find((item) => String(item.id) === exerciseId);
	if (!exercise || !window.confirm(`Möchtest du die Übung „${exercise.title}“ wirklich löschen?`)) return;
	try {
		await apiRequest(`/api/exercises/delete/${exerciseId}`, { method: "DELETE" });
		await loadExercises();
		setStatus("Übung gelöscht");
	} catch (error) {
		showError(error);
	}
});

saveButton.addEventListener("click", async () => {
	const active = [...activeList.children].map((row) => Number(row.dataset.chapterId));
	const inactive = [...inactiveList.children].map((row) => Number(row.dataset.chapterId));
	const activeIds = new Set(active);
	try {
		await apiRequest("/api/chapters/activation/change", {
			method: "PUT",
			body: JSON.stringify({
				chapters: [
					...active.map((chapter_id, position) => ({ chapter_id, position, active: true })),
					...inactive.map((chapter_id) => ({ chapter_id, position: -1, active: false })),
				],
			}),
		});
		chapters = chapters.map((chapter) => ({
			...chapter,
			active: activeIds.has(chapter.id),
			position: activeIds.has(chapter.id) ? active.indexOf(chapter.id) : -1,
		}));
		savedOrder = chapterOrder();
		renderChapters();
		updateDirtyState();
		statusMessage.textContent = "Kapiteländerungen gespeichert";
	} catch (error) {
		showError(error);
	}
});

window.addEventListener("beforeunload", (event) => {
	if (chapterOrder() !== savedOrder) {
		event.preventDefault();
		event.returnValue = "";
	}
});

Promise.all([loadChapters(), loadExercises(), loadAccounts()]).catch(showError);