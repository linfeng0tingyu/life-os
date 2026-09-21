import { element, emptyMessage, replace } from "./dom.js";

const IMAGE_PATTERN = /^!\[(.*?)]\((\/api\/journal\/assets\/\d{4}-\d{2}-\d{2}\/[0-9a-f]{32}\.(?:png|jpg|gif|webp))\)$/;

function inlineNodes(text) {
  const fragment = document.createDocumentFragment();
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    if (match.index > cursor) fragment.append(document.createTextNode(text.slice(cursor, match.index)));
    const token = match[0];
    fragment.append(token.startsWith("**")
      ? element("strong", { text: token.slice(2, -2) })
      : element("code", { text: token.slice(1, -1) }));
    cursor = match.index + token.length;
  }
  if (cursor < text.length) fragment.append(document.createTextNode(text.slice(cursor)));
  return fragment;
}

export function renderMarkdownPreview(container, markdown) {
  const content = markdown.trim();
  if (!content) {
    replace(container, emptyMessage("开始记录后，这里会显示标题、列表、图片和正文预览。"));
    return;
  }
  const nodes = [];
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  let list = null;
  const closeList = () => {
    if (list) nodes.push(list);
    list = null;
  };
  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    const image = IMAGE_PATTERN.exec(line.trim());
    const item = /^\s*[-*]\s+(.+)$/.exec(line);
    if (item) {
      if (!list) list = element("ul", { className: "markdown-list" });
      const li = element("li");
      li.append(inlineNodes(item[1]));
      list.append(li);
      continue;
    }
    closeList();
    if (!line.trim()) continue;
    if (heading) {
      const node = element(`h${heading[1].length}`, { className: "markdown-heading" });
      node.append(inlineNodes(heading[2]));
      nodes.push(node);
    } else if (image) {
      nodes.push(element("figure", { className: "markdown-image" }, [
        element("img", { attrs: { src: image[2], alt: image[1], loading: "lazy" } }),
        image[1] ? element("figcaption", { text: image[1] }) : null,
      ].filter(Boolean)));
    } else if (/^>\s?/.test(line)) {
      const node = element("blockquote");
      node.append(inlineNodes(line.replace(/^>\s?/, "")));
      nodes.push(node);
    } else if (/^---+$/.test(line.trim())) {
      nodes.push(element("hr"));
    } else {
      const node = element("p");
      node.append(inlineNodes(line));
      nodes.push(node);
    }
  }
  closeList();
  replace(container, ...nodes);
}
