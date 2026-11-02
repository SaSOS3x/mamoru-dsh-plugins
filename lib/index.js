import { createProvider, skillsDirectory } from "./provider.js";

/**
 * Backward-compatible aggregate plugin: registers every component provider at once.
 * The bundle now mounts `mamoru-core` and `mamoru-minecraft` separately (see
 * cordis.patch.yml); this root export stays for profiles that still reference the old
 * `mamoru-skills` id.
 */

const name = "mamoru-skills";

const inject = ["skills"];

function apply(ctx) {
	ctx.skills.registerProvider(() => createProvider("mamoru-core", skillsDirectory("core")));
	ctx.skills.registerProvider(() => createProvider("mamoru-minecraft", skillsDirectory("minecraft")));
}

export { apply, inject, name };
