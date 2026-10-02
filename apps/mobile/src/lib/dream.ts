/**
 * Dream companies, matched the way the server matches them (careeros/matching/dream.py): whole
 * leading words of the normalised name, so "Amazon" covers "Amazon Web Services" and "NatWest"
 * covers "NatWest Group".
 */
const SUFFIXES =
  /\b(inc|incorporated|llc|l\.l\.c|ltd|limited|pvt|private|corp|corporation|co|company|gmbh|plc|s\.a|sa|ag|bv|b\.v|pte|pty|srl|oy|ab)\b\.?/gi;

function words(name: string): string[] {
  return name
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(SUFFIXES, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

function covers(dreamName: string, company: string): boolean {
  const wanted = words(dreamName);
  const have = words(company);
  return wanted.length > 0 && wanted.every((word, index) => have[index] === word);
}

export function isDreamCompany(company: string, dream: readonly string[]): boolean {
  return dream.some((name) => covers(name, company));
}

/** The list with the company added, or with every entry that covers it removed. */
export function toggleDreamCompany(company: string, dream: readonly string[], on: boolean): string[] {
  if (on) return isDreamCompany(company, dream) ? [...dream] : [...dream, company];
  return dream.filter((name) => !covers(name, company));
}
