// Prints a patch; it never writes application files.
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const { candidates } = require('./audit-translations.cjs');
const root = path.resolve(__dirname, '../src');
const readMap = (file, name) => {
  const source = fs.readFileSync(path.join(root, file), 'utf8');
  const literal = source.match(new RegExp(`const ${name}: Record<string, string> = (\\{[\\s\\S]*?\\});`))[1];
  return JSON.parse(literal.replace(/,\s*}/g, '}'));
};
const dictionary = { ...readMap('lib/i18n/sidebar-copy.ts', 'sidebarArabic'), ...readMap('lib/i18n/operational.ts', 'arabic') };
const known = new Set([...Object.keys(dictionary), ...Object.values(dictionary)]);
const file = path.resolve(root, process.argv[2]);
const { source, ast, result } = candidates(file);
if (!source.includes('"use client"')) { console.log(''); process.exit(0); }
const edits = [];
const owners = new Set();
for (const item of result) {
  if (!known.has(item.text)) continue;
  let owner = item.node;
  while (owner && !(ts.isFunctionDeclaration(owner) && /^[A-Z]/.test(owner.name?.text ?? ''))) owner = owner.parent;
  if (!owner?.body) continue;
  owners.add(owner);
  const original = source.slice(item.start, item.end);
  const replacement = item.kind === 'expression' ? `uiText(${JSON.stringify(item.text)})` : item.kind === 'attribute' ? `{uiText(${JSON.stringify(item.text)})}` : `${original.match(/^\s*/)[0]}{uiText(${JSON.stringify(item.text)})}${original.match(/\s*$/)[0]}`;
  edits.push({ start: item.start, end: item.end, replacement });
}
if (!edits.length) { console.log(''); process.exit(0); }
for (const owner of owners) {
  if (!owner.body.getText(ast).includes('const uiText = useUiText()')) edits.push({ start: owner.body.getStart(ast) + 1, end: owner.body.getStart(ast) + 1, replacement: '\n  const uiText = useUiText();' });
}
if (!source.includes('useOperationalText as useUiText')) {
  const directive = ast.statements[0];
  edits.push({ start: directive.end, end: directive.end, replacement: '\n\nimport { useOperationalText as useUiText } from "@/lib/i18n/operational";' });
}
// Expand edits to complete lines and merge overlapping blocks for apply_patch.
const groups = [];
for (const edit of edits.sort((a,b) => a.start - b.start)) {
  const owner = [...owners].find(o => edit.start === o.body.getStart(ast) + 1);
  const start = source.lastIndexOf('\n', (owner ? owner.getStart(ast) : edit.start) - 1) + 1;
  let end = source.indexOf('\n', edit.end);
  if (end < 0) end = source.length;
  const last = groups.at(-1);
  if (last && start <= last.end) { last.end = Math.max(last.end, end); last.edits.push(edit); }
  else groups.push({ start, end, edits: [edit] });
}
let patch = `*** Begin Patch\n*** Update File: ${file.replaceAll('\\','/')}\n`;
for (const group of groups) {
  const old = source.slice(group.start, group.end);
  let updated = old;
  for (const edit of group.edits.sort((a,b) => b.start-a.start)) updated = updated.slice(0, edit.start-group.start) + edit.replacement + updated.slice(edit.end-group.start);
  patch += '@@\n' + old.split(/\r?\n/).map(x => '-'+x).join('\n') + '\n' + updated.split(/\r?\n/).map(x => '+'+x).join('\n') + '\n';
}
console.log(patch + '*** End Patch');
