// Provide integer arithmetic and RSA expression calculators for lesson pages.
function parseInteger(value) {
	const trimmed = value.trim();
	if (!/^-?\d+$/.test(trimmed)) return null;
	return BigInt(trimmed);
}

class CalculatorInputError extends Error {}

function evaluateIntegerExpression(source) {
	const tokens = [];
	let remaining = source.trim();
	while (remaining) {
		const whitespace = /^\s+/.exec(remaining);
		if (whitespace) {
			remaining = remaining.slice(whitespace[0].length);
			continue;
		}

		const integer = /^\d+/.exec(remaining);
		if (integer) {
			tokens.push(integer[0]);
			remaining = remaining.slice(integer[0].length);
			continue;
		}

		const operator = /^[()+*/^-]/.exec(remaining);
		if (!operator) {
			throw new CalculatorInputError("Bitte verwende nur ganze Zahlen und Rechenzeichen.");
		}
		tokens.push(operator[0]);
		remaining = remaining.slice(1);
	}

	let position = 0;
	const peek = () => tokens[position];
	const consume = () => tokens[position++];

	// Each parser handles one precedence level; nested calls parse tighter operators.
	function parsePrimary() {
		const token = consume();
		if (token === "(") {
			const value = parseExpression();
			if (consume() !== ")") {
				throw new CalculatorInputError("In der Rechnung fehlt eine schliessende Klammer.");
			}
			return value;
		}
		if (!token || !/^\d+$/.test(token)) {
			throw new CalculatorInputError("Bitte gib eine gültige Rechnung ein.");
		}
		return BigInt(token);
	}

	function parsePower() {
		const base = parsePrimary();
		if (peek() !== "^") return base;
		consume();
		const exponent = parseUnary();
		if (exponent < 0n || exponent > 1000n) {
			throw new CalculatorInputError("Der Exponent muss zwischen 0 und 1000 liegen.");
		}
		return base ** exponent;
	}

	function parseUnary() {
		if (peek() === "+") {
			consume();
			return parseUnary();
		}
		if (peek() === "-") {
			consume();
			return -parseUnary();
		}
		return parsePower();
	}

	function parseTerm() {
		let value = parseUnary();
		while (peek() === "*" || peek() === "/") {
			const operator = consume();
			const right = parseUnary();
			if (operator === "*") {
				value *= right;
			} else {
				if (right === 0n) {
					throw new CalculatorInputError("Eine Division durch 0 ist nicht möglich.");
				}
				if (value % right !== 0n) {
					throw new CalculatorInputError("Die Division muss ein ganzzahliges Ergebnis haben.");
				}
				value /= right;
			}
		}
		return value;
	}

	function parseExpression() {
		let value = parseTerm();
		while (peek() === "+" || peek() === "-") {
			const operator = consume();
			const right = parseTerm();
			value = operator === "+" ? value + right : value - right;
		}
		return value;
	}

	if (tokens.length === 0) {
		throw new CalculatorInputError("Bitte gib eine Rechnung ein.");
	}
	const result = parseExpression();
	if (position !== tokens.length) {
		throw new CalculatorInputError("Bitte gib eine gültige Rechnung ein.");
	}
	return result;
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

document.querySelectorAll("[data-rsa-expression-calculator]").forEach((form) => {
	form.addEventListener("submit", (event) => {
		event.preventDefault();
		const result = form.querySelector("[data-result]");
		result.classList.remove("is-error");

		try {
			const expression = form.querySelector("[data-expression]").value;
			const modulus = parseInteger(form.querySelector("[data-modulus]").value);
			if (modulus === null) {
				throw new CalculatorInputError("Bitte gib einen positiven Modulo ein.");
			}
			if (modulus <= 0n) {
				throw new CalculatorInputError("Der Modulo muss grösser als 0 sein.");
			}

			const calculation = evaluateIntegerExpression(expression);
			const remainder = ((calculation % modulus) + modulus) % modulus;
			result.textContent = `${expression.trim()} mod ${modulus} = ${remainder}`;
		} catch (error) {
			if (!(error instanceof CalculatorInputError)) throw error;
			result.textContent = error.message;
			result.classList.add("is-error");
		}
	});
});
