import { createProvider, skillsDirectory } from "./provider.js";

/**
 * Cordis plugin of the `minecraft` component: NeoForge 1.21.1, modpack ports, worldgen,
 * KubeJS and TPS skills. Install it without `core` when a machine only edits Minecraft packs.
 */

const name = "mamoru-minecraft";

const inject = ["skills"];

function apply(ctx) {
	ctx.skills.registerProvider(() => createProvider("mamoru-minecraft", skillsDirectory("minecraft")));
}

export { apply, inject, name };
