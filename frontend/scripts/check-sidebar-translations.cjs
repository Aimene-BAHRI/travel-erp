const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const { candidates, files } = require('./audit-translations.cjs');
const root = path.resolve(__dirname, '../src');
function dictionary(file, name) {
  const source = fs.readFileSync(path.join(root, file), 'utf8');
  return JSON.parse(source.match(new RegExp(`const ${name}: Record<string, string> = (\\{[\\s\\S]*?\\});`))[1].replace(/,\s*}/g, '}'));
}
const translations = { ...dictionary('lib/i18n/sidebar-copy.ts', 'sidebarArabic'), ...dictionary('lib/i18n/operational.ts', 'arabic') };
const known = new Set([...Object.keys(translations), ...Object.values(translations)]);
const allowed = new Set(['Wakaltcom ERP', 'IST-2026-09', 'KB', 'KB)']);
const shell = fs.readFileSync(path.join(root, 'components/layout/app-shell.tsx'), 'utf8');
const routes = [...shell.matchAll(/href: "(\/[^"]+)"/g)].map(m => m[1]);
assert.equal(routes.length, 14, 'Review the translation inventory when sidebar destinations change.');
for (const route of routes) assert.ok(fs.existsSync(path.join(root, 'app/(erp)', route.slice(1), 'page.tsx')), `Missing sidebar page: ${route}`);
const problems = [];
let count = 0;
for (const file of files(root)) {
  const relative = path.relative(root, file).replaceAll('\\', '/');
  if (!/^(features|components|app\/\(erp\))\//.test(relative) || /(?:^features\/(?:public|auth|partners)\/|^features\/pricing\/quote|^app\/\(erp\)\/(?:quotes|partners)\/|trip-commercial\.tsx$)/.test(relative)) continue;
  const { result, ast, source } = candidates(file);
  count++;
  for (const item of result) if (!allowed.has(item.text)) problems.push(`${relative}: untranslated literal ${JSON.stringify(item.text)}`);
  function walk(node) {
    if (ts.isCallExpression(node) && node.expression.getText(ast) === 'uiText' && ts.isStringLiteral(node.arguments[0]) && !known.has(node.arguments[0].text)) problems.push(`${relative}: missing dictionary entry ${node.arguments[0].text}`);
    if (ts.isJsxElement(node) && node.openingElement.tagName.getText(ast) === 'option' && !node.openingElement.attributes.properties.some(p => p.name?.getText(ast) === 'value') && node.children.some(c => ts.isJsxExpression(c) && c.expression?.getText(ast).includes('uiText('))) problems.push(`${relative}: translated option requires an explicit API value`);
    ts.forEachChild(node, walk);
  }
  if (source.includes('useUiText')) walk(ast);
}
assert.deepEqual(problems, [], problems.join('\n'));
console.log(`Checked ${routes.length} sidebar destinations and ${count} related source files: translated literals, dictionary coverage, and option values passed.`);
