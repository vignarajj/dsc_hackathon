export type TextChange = {
  type: "same" | "removed" | "added";
  text: string;
};

const MAX_TOKENS = 1500;

export function textChanges(before: string, after: string): TextChange[] {
  if (before === after) {
    return before ? [{ type: "same", text: before }] : [];
  }
  const left = tokenize(before);
  const right = tokenize(after);
  if (left.length > MAX_TOKENS || right.length > MAX_TOKENS) {
    return compact([
      { type: "removed", text: before },
      { type: "added", text: after },
    ]);
  }
  return compact(diffTokens(left, right));
}

function tokenize(text: string): string[] {
  return text.split(/(\s+)/).filter((token) => token.length > 0);
}

function diffTokens(left: string[], right: string[]): TextChange[] {
  const rows = left.length + 1;
  const columns = right.length + 1;
  const scores: number[][] = Array.from({ length: rows }, () => Array(columns).fill(0));
  for (let i = left.length - 1; i >= 0; i -= 1) {
    for (let j = right.length - 1; j >= 0; j -= 1) {
      scores[i][j] =
        left[i] === right[j]
          ? scores[i + 1][j + 1] + 1
          : Math.max(scores[i + 1][j], scores[i][j + 1]);
    }
  }

  const changes: TextChange[] = [];
  let i = 0;
  let j = 0;
  while (i < left.length && j < right.length) {
    if (left[i] === right[j]) {
      changes.push({ type: "same", text: left[i] });
      i += 1;
      j += 1;
    } else if (scores[i + 1][j] >= scores[i][j + 1]) {
      changes.push({ type: "removed", text: left[i] });
      i += 1;
    } else {
      changes.push({ type: "added", text: right[j] });
      j += 1;
    }
  }
  while (i < left.length) {
    changes.push({ type: "removed", text: left[i] });
    i += 1;
  }
  while (j < right.length) {
    changes.push({ type: "added", text: right[j] });
    j += 1;
  }
  return changes;
}

function compact(changes: TextChange[]): TextChange[] {
  const merged: TextChange[] = [];
  for (const change of changes) {
    const previous = merged.at(-1);
    if (previous && previous.type === change.type) {
      previous.text += change.text;
    } else if (change.text) {
      merged.push({ ...change });
    }
  }
  return merged;
}
