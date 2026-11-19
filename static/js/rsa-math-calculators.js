function parseInteger(value) {
	const trimmed = value.trim();
	if (!/^-?\d+$/.test(trimmed)) return null;
	return BigInt(trimmed);
}

document.querySelectorAll("[data-calculator]").forEach((form) => {
	form.addEventListener("submit", (event) => {
		event.preventDefault();
		const result = form.querySelector("[data-result]");
		result.classList.remove("is-error");

		const values = [...form.querySelectorAll("[data-value]")].map((input) =>
			parseInteger(input.value)
		);
		if (values.some((value) => value === null)) {
			result.textContent = "Bitte gib ganze Zahlen ein.";
			result.classList.add("is-error");
			return;
		}

		if (form.dataset.calculator === "multiply") {
			const [left, right] = values;
			result.textContent = `${left} × ${right} = ${left * right}`;
			return;
		}

		const [dividend, modulus] = values;
		if (modulus <= 0n) {
			result.textContent = "Der Modulo muss grösser als 0 sein.";
			result.classList.add("is-error");
			return;
		}
		const remainder = ((dividend % modulus) + modulus) % modulus;
		result.textContent = `${dividend} mod ${modulus} = ${remainder}`;
	});
});
