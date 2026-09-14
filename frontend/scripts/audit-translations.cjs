// Read-only inventory of literal UI copy. API values and stored records are excluded.
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const root = path.resolve(__dirname, '../src');
const attrs = new Set(['title', 'label', 'description', 'hint', 'placeholder', 'aria-label', 'alt', 'emptyMessage']);
function files(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? files(path.join(dir, e.name)) : e.name.endsWith('.tsx') ? [path.join(dir, e.name)] : []);
}
function candidates(file) {
  const source = fs.readFileSync(file, 'utf8');
  const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const result = [];
  function visibleExpression(node) {
    if (!node) return;
    if (ts.isStringLiteral(node) && /[a-zA-Z\u0600-\u06ff]/.test(node.text)) result.push({ start: node.getStart(ast), end: node.end, text: node.text, kind: 'expression', node });
    else if (ts.isConditionalExpression(node) && !/locale|isRtl/.test(node.condition.getText(ast))) { visibleExpression(node.whenTrue); visibleExpression(node.whenFalse); }
    else if (ts.isBinaryExpression(node) && [ts.SyntaxKind.AmpersandAmpersandToken, ts.SyntaxKind.BarBarToken, ts.SyntaxKind.QuestionQuestionToken].includes(node.operatorToken.kind)) visibleExpression(node.right);
    else if (ts.isParenthesizedExpression(node)) visibleExpression(node.expression);
  }
  function walk(node) {
    if (process.argv.includes('--phrases') && ts.isStringLiteral(node) && /^[A-Za-z][A-Za-z0-9 .,;:!?/()&'’“”–…-]* [A-Za-z]/.test(node.text) && !/[#{}=\[\]@]|\b(?:flex|grid|rounded|border|text-|bg-|use client)\b/.test(node.text)) {
      result.push({ start: node.getStart(ast), end: node.end, text: node.text, kind: 'phrase', node });
    }
    if (ts.isJsxExpression(node) && (!ts.isJsxAttribute(node.parent) || attrs.has(node.parent.name.getText(ast)))) visibleExpression(node.expression);
    if (ts.isJsxText(node)) {
      const text = node.text.replace(/\s+/g, ' ').trim();
      if (/[a-zA-Z\u0600-\u06ff]/.test(text)) result.push({ start: node.pos, end: node.end, text, kind: 'text', node });
    }
    if (ts.isJsxAttribute(node) && attrs.has(node.name.getText(ast)) && node.initializer && ts.isStringLiteral(node.initializer)) {
      result.push({ start: node.initializer.getStart(ast), end: node.initializer.end, text: node.initializer.text, kind: 'attribute', node });
    }
    ts.forEachChild(node, walk);
  }
  walk(ast);
  return { source, ast, result };
}
if (require.main === module) {
  const groups = [];
  for (const file of files(root)) {
    if (/features[\\/](public|partners)|features[\\/]pricing[\\/]quote|app[\\/](public|\(auth\))/.test(file)) continue;
    const { result } = candidates(file);
    if (result.length) groups.push({ file: path.relative(root, file), strings: [...new Set(result.map(x => x.text))] });
  }
  console.log(JSON.stringify(groups, null, 2));
}
module.exports = { candidates, files };
