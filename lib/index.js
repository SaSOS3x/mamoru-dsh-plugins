import { readFileSync, readdirSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { join, sep } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Bundled skill provider for the mamoru-dsh-plugins package.
 *
 * Every directory under `skills/` that holds a `SKILL.md` becomes one skill in the DSH
 * session catalog. The provider registers itself on `ctx.skills` (the same registry the
 * filesystem provider uses), so the skills show up wherever the `skill` tool is mounted.
 *
 * The shapes below follow the provider contract of @deepseek-ai/dsh-skill 0.2.1-rc.5:
 * `list()` returns candidates (with `rank` and `locator`), and `get()` returns the loaded
 * definition: the candidate summary without `rank`/`locator` plus the instruction body.
 *
 * @module mamoru-dsh-plugins
 */

/** Provider name shown in provider diagnostics. */
const PROVIDER_NAME = "mamoru";

/** Bundled skills rank from @deepseek-ai/dsh-skill (BUNDLED_SKILL_RANK, 0.2.1-rc.5). */
const BUNDLED_SKILL_RANK = 600;

/** Skill folder name and frontmatter name must be kebab-case. */
const SKILL_NAME = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

const SKILLS_DIR = fileURLToPath(new URL("../skills/", import.meta.url));

/**
 * Read the small YAML frontmatter this package allows: one `key: value` pair per line with
 * an optional quoted value. It is deliberately not a YAML parser: the skills are checked by
 * check_skills.py, and a YAML dependency would load on every boot.
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
function readSkill(directory) {
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
		provider: PROVIDER_NAME,
		source: "bundled",
		rank: BUNDLED_SKILL_RANK,
		resourceBase: {
			kind: "directory",
			path: directory.split(sep).join("/")
		},
		locator: path
	};
}

/** Skill directories under skills/, sorted by name; a folder without SKILL.md is skipped. */
function readCandidates() {
	const directories = [];
	const entries = readdirSync(SKILLS_DIR, { withFileTypes: true });
	for (const entry of entries) {
		if (!entry.isDirectory()) continue;
		const directory = join(SKILLS_DIR, entry.name);
		try {
			readFileSync(join(directory, "SKILL.md"));
		} catch {
			continue;
		}
		directories.push(directory);
	}
	if (directories.length === 0) {
		throw new Error(`mamoru-dsh-plugins: no skills with SKILL.md under ${SKILLS_DIR}`);
	}
	return directories
		.map(readSkill)
		.sort((left, right) => (left.name < right.name ? -1 : left.name > right.name ? 1 : 0));
}

const candidates = readCandidates();

const provider = {
	name: PROVIDER_NAME,
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

/** Cordis plugin name. */
const name = "mamoru-skills";

/** The skill registry this plugin contributes to. */
const inject = ["skills"];

/**
 * Register the bundled skill provider.
 * @param ctx - Context carrying the skill registry.
 */
function apply(ctx) {
	ctx.skills.registerProvider(() => provider);
}

export { apply, inject, name };
