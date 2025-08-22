import rehypeKatex from 'rehype-katex';
import remarkMath from 'remark-math';

import { defineDocs, defineConfig } from 'fumadocs-mdx/config';

export default defineConfig({
    mdxOptions: {
        remarkPlugins: [remarkMath],
        // Place it at first, it should be executed before the syntax highlighter
        rehypePlugins: (v) => [rehypeKatex, ...v],
    },
});

export const docs = defineDocs({
    dir: 'content/docs',
});