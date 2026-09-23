export function element(tag, { className, text, attrs = {} } = {}, children = []) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  for (const [name, value] of Object.entries(attrs)) {
    if (value !== undefined && value !== null) node.setAttribute(name, String(value));
  }
  node.append(...children);
  return node;
}

export function emptyMessage(text) {
  return element("p", { className: "empty-state", text });
}

export function replace(container, ...children) {
  container.replaceChildren(...children);
}
