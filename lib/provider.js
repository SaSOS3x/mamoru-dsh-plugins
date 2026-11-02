import { readFileSync, readdirSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { join, sep } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Shared code of the component providers: one provider reads one component folder under
 * `skills/` (`skills/core`, `skills/minecraft`, ...). The provider contract is the one of
 * @deepseek-ai/dsh-skill 0.2.1-rc.5: `list()` returns candidates and `get()` returns the
 * definition (candidate without rank/locator plus the instruction body).
 */

/** Skill folder name and frontmatter name must be kebab-case. */
const SKILL_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

/** Bundled skills rank from @deepseek-ai/dsh-skill (BUNDLED_SKILL_RANK, 0.2.1-rc.5). */
const BUNDLED_SKILL_RANK = 600;

/** Absolute path of one component folder, e.g. skillsDirectory("core"). */
export function skillsDirectory(component) {
	return fileURLToPath(new URL(`../skills/${component}/`, import.meta.url));
}

/**
 * Read the small YAML frontmatter this package allows: one `key: value` pair per line with
 * an optional quoted value. Not a YAML parser: skills are checked by check_skills.py.
 */
function readFrontmatter(text, path) {
	const match = /^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/u.exec(text);
	if (match === null) {
		throw new Error(`mamoru-dsh-plugins: ${path} has no YAML frontmatter`);
	}
	const fields = new Map();
	for (const line of match[1].split(/\r?\n/u)) {
		const pair = /^([A-Za-z0-9_-]+):[ \t]*(.*)$/u.exec(line);
		if (pair === null) continue;
		let value = pair[2].trim();
		if (value.length >= 2 && value.startsWith('"') && value.endsWith('"')) {
			value = value.slice(1, -1).replace(/\\"/gu, '"').replace(/\\\\/gu, "\\");
		} else if (value.length >= 2 && value.startsWith("'") && value.endsWith("'")) {
			value = value.slice(1, -1).replace(/''/gu, "'");
		}
		fields.set(pair[1], value);
	}
	return { body: text.slice(match[0].length), fields };
}

/** Parse one skill file and build its catalog candidate. */
function readSkill(directory, providerName) {
	const path = join(directory, "SKILL.md");
	const raw = readFileSync(path, "utf8");
	const { fields } = readFrontmatter(raw, path);
	const name = fields.get("name") ?? "";
	const description = fields.get("description") ?? "";
	if (!SKILL_NAME.test(name)) {
		throw new Error(`mamoru-dsh-plugins: ${path} has an invalid skill name "${name}"`);
	}
	const folder = directory.slice(directory.lastIndexOf(sep) + 1);
	if (name !== folder) {
		throw new Error(`mamoru-dsh-plugins: ${path} declares "${name}", which does not match its folder`);
	}
	if (description.length === 0) {
		throw new Error(`mamoru-dsh-plugins: ${path} has no description`);
	}
	return {
		name,
		description,
		invocation: {
			modelInvocable: true,
			userInvocable: true
		},
		provider: providerName,
		source: "bundled",
		rank: BUNDLED_SKILL_RANK,
		resourceBase: {
			kind: "directory",
			path: directory.split(sep).join("/")
		},
		locator: path
	};
}

/** Skill directories under one component, sorted by name; a folder without SKILL.md is skipped. */
function readCandidates(directory, providerName) {
	if (!directory.endsWith(sep)) directory += sep;
	const directories = [];
	for (const entry of readdirSync(directory, { withFileTypes: true })) {
		if (!entry.isDirectory()) continue;
		const skillDirectory = join(directory, entry.name);
		try {
			readFileSync(join(skillDirectory, "SKILL.md"));
		} catch {
			continue;
		}
		directories.push(skillDirectory);
	}
	if (directories.length === 0) {
		throw new Error(`mamoru-dsh-plugins: no skills with SKILL.md under ${directory}`);
	}
	return directories
		.map((skillDirectory) => readSkill(skillDirectory, providerName))
		.sort((left, right) => (left.name < right.name ? -1 : left.name > right.name ? 1 : 0));
}

/** Build the provider object for one component. */
export function createProvider(providerName, directory) {
	const candidates = readCandidates(directory, providerName);
	return {
		name: providerName,
		list() {
			return Promise.resolve(candidates);
		},
		async get(candidate, options) {
			const { rank: _rank, locator, ...summary } = candidate;
			const raw = await readFile(locator, {
				encoding: "utf8",
				signal: options?.signal
			});
			return {
				...summary,
				content: readFrontmatter(raw, locator).body.trim()
			};
		}
	};
}
