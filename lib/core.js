import { createProvider, skillsDirectory } from "./provider.js";

/**
 * Cordis plugin of the `core` component: workflow and Windows skills that almost every
 * project needs (journal, delegation, skill-forge, audit, tests, shell).
 */

const name = "mamoru-core";

const inject = ["skills"];

function apply(ctx) {
	ctx.skills.registerProvider(() => createProvider("mamoru-core", skillsDirectory("core")));
}

export { apply, inject, name };
