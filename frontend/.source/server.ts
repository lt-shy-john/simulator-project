// @ts-nocheck
import * as __fd_glob_22 from "../content/docs/simulation-setup/topologies.mdx?collection=docs"
import * as __fd_glob_21 from "../content/docs/simulation-setup/stopping.mdx?collection=docs"
import * as __fd_glob_20 from "../content/docs/simulation-setup/simulation-setup-intro.mdx?collection=docs"
import * as __fd_glob_19 from "../content/docs/simulation-setup/scheduler.mdx?collection=docs"
import * as __fd_glob_18 from "../content/docs/simulation-setup/behaviour-module.mdx?collection=docs"
import * as __fd_glob_17 from "../content/docs/simulation-setup/behaviour-expression.mdx?collection=docs"
import * as __fd_glob_16 from "../content/docs/simulation-setup/agents.mdx?collection=docs"
import * as __fd_glob_15 from "../content/docs/tutorial/index.mdx?collection=docs"
import * as __fd_glob_14 from "../content/docs/simulation/simulation.mdx?collection=docs"
import * as __fd_glob_13 from "../content/docs/simulation/simulation-manage.mdx?collection=docs"
import * as __fd_glob_12 from "../content/docs/reference/topologies.mdx?collection=docs"
import * as __fd_glob_11 from "../content/docs/reference/stopping.mdx?collection=docs"
import * as __fd_glob_10 from "../content/docs/reference/scheduler.mdx?collection=docs"
import * as __fd_glob_9 from "../content/docs/reference/behaviour-module.mdx?collection=docs"
import * as __fd_glob_8 from "../content/docs/reference/behaviour-expression.mdx?collection=docs"
import * as __fd_glob_7 from "../content/docs/reference/agents.mdx?collection=docs"
import * as __fd_glob_6 from "../content/docs/index.mdx?collection=docs"
import * as __fd_glob_5 from "../content/docs/faq.mdx?collection=docs"
import { default as __fd_glob_4 } from "../content/docs/simulation-setup/meta.json?collection=docs"
import { default as __fd_glob_3 } from "../content/docs/simulation/meta.json?collection=docs"
import { default as __fd_glob_2 } from "../content/docs/tutorial/meta.json?collection=docs"
import { default as __fd_glob_1 } from "../content/docs/reference/meta.json?collection=docs"
import { default as __fd_glob_0 } from "../content/docs/meta.json?collection=docs"
import { server } from 'fumadocs-mdx/runtime/server';
import type * as Config from '../source.config';

const create = server<typeof Config, import("fumadocs-mdx/runtime/types").InternalTypeConfig & {
  DocData: {
  }
}>({"doc":{"passthroughs":["extractedReferences"]}});

export const docs = await create.docs("docs", "content/docs", {"meta.json": __fd_glob_0, "reference/meta.json": __fd_glob_1, "tutorial/meta.json": __fd_glob_2, "simulation/meta.json": __fd_glob_3, "simulation-setup/meta.json": __fd_glob_4, }, {"faq.mdx": __fd_glob_5, "index.mdx": __fd_glob_6, "reference/agents.mdx": __fd_glob_7, "reference/behaviour-expression.mdx": __fd_glob_8, "reference/behaviour-module.mdx": __fd_glob_9, "reference/scheduler.mdx": __fd_glob_10, "reference/stopping.mdx": __fd_glob_11, "reference/topologies.mdx": __fd_glob_12, "simulation/simulation-manage.mdx": __fd_glob_13, "simulation/simulation.mdx": __fd_glob_14, "tutorial/index.mdx": __fd_glob_15, "simulation-setup/agents.mdx": __fd_glob_16, "simulation-setup/behaviour-expression.mdx": __fd_glob_17, "simulation-setup/behaviour-module.mdx": __fd_glob_18, "simulation-setup/scheduler.mdx": __fd_glob_19, "simulation-setup/simulation-setup-intro.mdx": __fd_glob_20, "simulation-setup/stopping.mdx": __fd_glob_21, "simulation-setup/topologies.mdx": __fd_glob_22, });