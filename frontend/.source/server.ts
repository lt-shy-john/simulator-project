// @ts-nocheck
import * as __fd_glob_15 from "../content/docs/tutorial/index.mdx?collection=docs"
import * as __fd_glob_14 from "../content/docs/simulation-setup/topologies.mdx?collection=docs"
import * as __fd_glob_13 from "../content/docs/simulation-setup/stopping.mdx?collection=docs"
import * as __fd_glob_12 from "../content/docs/simulation-setup/simulation-setup-intro.mdx?collection=docs"
import * as __fd_glob_11 from "../content/docs/simulation-setup/scheduler.mdx?collection=docs"
import * as __fd_glob_10 from "../content/docs/simulation-setup/behaviour-module.mdx?collection=docs"
import * as __fd_glob_9 from "../content/docs/simulation-setup/behaviour-expression.mdx?collection=docs"
import * as __fd_glob_8 from "../content/docs/simulation-setup/agents.mdx?collection=docs"
import * as __fd_glob_7 from "../content/docs/simulation/simulation.mdx?collection=docs"
import * as __fd_glob_6 from "../content/docs/simulation/simulation-manage.mdx?collection=docs"
import * as __fd_glob_5 from "../content/docs/index.mdx?collection=docs"
import * as __fd_glob_4 from "../content/docs/faq.mdx?collection=docs"
import { default as __fd_glob_3 } from "../content/docs/tutorial/meta.json?collection=docs"
import { default as __fd_glob_2 } from "../content/docs/simulation-setup/meta.json?collection=docs"
import { default as __fd_glob_1 } from "../content/docs/simulation/meta.json?collection=docs"
import { default as __fd_glob_0 } from "../content/docs/meta.json?collection=docs"
import { server } from 'fumadocs-mdx/runtime/server';
import type * as Config from '../source.config';

const create = server<typeof Config, import("fumadocs-mdx/runtime/types").InternalTypeConfig & {
  DocData: {
  }
}>({"doc":{"passthroughs":["extractedReferences"]}});

export const docs = await create.docs("docs", "content/docs", {"meta.json": __fd_glob_0, "simulation/meta.json": __fd_glob_1, "simulation-setup/meta.json": __fd_glob_2, "tutorial/meta.json": __fd_glob_3, }, {"faq.mdx": __fd_glob_4, "index.mdx": __fd_glob_5, "simulation/simulation-manage.mdx": __fd_glob_6, "simulation/simulation.mdx": __fd_glob_7, "simulation-setup/agents.mdx": __fd_glob_8, "simulation-setup/behaviour-expression.mdx": __fd_glob_9, "simulation-setup/behaviour-module.mdx": __fd_glob_10, "simulation-setup/scheduler.mdx": __fd_glob_11, "simulation-setup/simulation-setup-intro.mdx": __fd_glob_12, "simulation-setup/stopping.mdx": __fd_glob_13, "simulation-setup/topologies.mdx": __fd_glob_14, "tutorial/index.mdx": __fd_glob_15, });