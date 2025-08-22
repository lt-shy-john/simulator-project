// source.config.ts
import rehypeKatex from "rehype-katex";
import remarkMath from "remark-math";
import { defineDocs, defineConfig } from "fumadocs-mdx/config";
var source_config_default = defineConfig({
  mdxOptions: {
    remarkPlugins: [remarkMath],
    // Place it at first, it should be executed before the syntax highlighter
    rehypePlugins: (v) => [rehypeKatex, ...v]
  }
});
var docs = defineDocs({
  dir: "content/docs"
});
export {
  source_config_default as default,
  docs
};
