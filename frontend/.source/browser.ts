// @ts-nocheck
import { browser } from 'fumadocs-mdx/runtime/browser';
import type * as Config from '../source.config';

const create = browser<typeof Config, import("fumadocs-mdx/runtime/types").InternalTypeConfig & {
  DocData: {
  }
}>();
const browserCollections = {
  docs: create.doc("docs", {"faq.mdx": () => import("../content/docs/faq.mdx?collection=docs"), "index.mdx": () => import("../content/docs/index.mdx?collection=docs"), "simulation/simulation-manage.mdx": () => import("../content/docs/simulation/simulation-manage.mdx?collection=docs"), "simulation/simulation.mdx": () => import("../content/docs/simulation/simulation.mdx?collection=docs"), "tutorial/index.mdx": () => import("../content/docs/tutorial/index.mdx?collection=docs"), }),
};
export default browserCollections;